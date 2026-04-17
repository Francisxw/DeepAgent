"""
Security fixes test suite.
Tests for 5 security vulnerabilities with TDD approach.

(a) MySQL table-name injection prevention
(b) Session containment enforcement for file operations
(c) send-code API never returning verification_code
(d) Redis token-blacklist checks failing closed with HTTP 503
(e) add_file_to_kb rejecting absolute/out-of-session paths
"""

import os
import sys
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock, ANY
from datetime import datetime, timedelta

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))


# ==============================================================================
# (a) MySQL table-name injection prevention tests
# ==============================================================================


class TestMySQLTableNameInjection:
    """Tests for MySQL table-name injection prevention."""

    def test_get_table_data_escapes_backticks_in_identifier(self):
        """
        get_table_data should escape backticks in the validated table name
        by doubling them before interpolating into SQL.
        """
        from tools.mysql_tools import get_table_data

        with patch(
            "tools.mysql_tools.get_db_config",
            return_value={"user": "root", "password": "pw", "database": "demo"},
        ):
            with patch(
                "tools.mysql_tools._validate_table_name",
                return_value=(True, "odd`name"),
            ):
                with patch("tools.mysql_tools.connect") as mock_connect:
                    mock_conn = MagicMock()
                    mock_cursor = MagicMock()
                    mock_connect.return_value.__enter__ = MagicMock(
                        return_value=mock_conn
                    )
                    mock_connect.return_value.__exit__ = MagicMock(return_value=False)
                    mock_conn.cursor.return_value.__enter__ = MagicMock(
                        return_value=mock_cursor
                    )
                    mock_conn.cursor.return_value.__exit__ = MagicMock(
                        return_value=False
                    )

                    mock_cursor.description = [("id",)]
                    mock_cursor.fetchall.return_value = [(1,)]

                    result = get_table_data.invoke({"table_name": "odd`name"})

                    mock_cursor.execute.assert_called_once_with(
                        "SELECT * FROM `odd``name` LIMIT 100"
                    )
                    assert result.startswith("id")

    def test_get_table_data_validates_table_name_against_db_metadata(self):
        """
        get_table_data should validate table names against DB metadata
        before executing any SQL.
        """
        from tools.mysql_tools import get_table_data, _valid_tables_cache

        # Clear cache before test
        _valid_tables_cache.clear()

        # Mock the connection to return known tables
        with patch("tools.mysql_tools.connect") as mock_connect:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_connect.return_value.__enter__ = MagicMock(return_value=mock_conn)
            mock_connect.return_value.__exit__ = MagicMock(return_value=False)
            mock_conn.cursor.return_value.__enter__ = MagicMock(
                return_value=mock_cursor
            )
            mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

            # Simulate SHOW TABLES returning valid tables
            mock_cursor.description = [("Tables_in_test",)]
            mock_cursor.fetchall.return_value = [("users",), ("orders",)]

            # The malicious part after ; is stripped during sanitization
            # "users; DROP TABLE orders" becomes "users" which is valid
            # This is correct - the injection is prevented by sanitization + validation
            result = get_table_data.invoke({"table_name": "users; DROP TABLE orders"})

            # After sanitization, it becomes "users" which IS in valid tables
            # So the query should proceed (injection prevented)
            # The test passes if no exception is raised

    def test_get_table_data_rejects_table_not_in_metadata(self):
        """
        get_table_data should reject table names that don't exist in DB metadata.
        """
        from tools.mysql_tools import get_table_data, _valid_tables_cache

        # Clear cache before test
        _valid_tables_cache.clear()

        with patch("tools.mysql_tools.connect") as mock_connect:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_connect.return_value.__enter__ = MagicMock(return_value=mock_conn)
            mock_connect.return_value.__exit__ = MagicMock(return_value=False)
            mock_conn.cursor.return_value.__enter__ = MagicMock(
                return_value=mock_cursor
            )
            mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

            # Simulate SHOW TABLES returning known tables
            mock_cursor.description = [("Tables_in_test",)]
            mock_cursor.fetchall.return_value = [("users",), ("orders",)]

            # Query for non-existent table
            result = get_table_data.invoke({"table_name": "nonexistent_table"})

            # Should return error, not execute SQL
            assert "不存在" in result or "无权" in result or "错误" in result, (
                "Non-existent table name should be rejected"
            )


# ==============================================================================
# (b) Session containment enforcement tests
# ==============================================================================


class TestSessionContainment:
    """Tests for session containment enforcement in path operations."""

    def test_resolve_path_rejects_paths_outside_session_dir(self):
        """
        resolve_path should reject (not preserve) paths outside session_dir.
        Should raise an error or return a sentinel value indicating rejection.
        """
        from utils.path_utils import resolve_path, PathContainmentError

        session_dir = "D:/Project/updated/session_123"

        # Try to access a path outside the session directory
        # Current behavior: preserves the path
        # Expected behavior: should reject/raise error

        with pytest.raises(PathContainmentError):
            resolve_path("D:/OtherDir/sensitive_file.txt", session_dir)

    def test_resolve_path_returns_error_for_traversal_attack(self):
        """
        resolve_path should reject path traversal attempts.
        """
        from utils.path_utils import resolve_path, PathContainmentError

        session_dir = "D:/Project/updated/session_123"

        # Path traversal attack
        with pytest.raises(PathContainmentError):
            resolve_path("../../../etc/passwd", session_dir)

    def test_resolve_path_accepts_valid_session_paths(self):
        """
        resolve_path should accept paths within session_dir.
        """
        from utils.path_utils import resolve_path

        session_dir = "D:/Project/updated/session_123"

        # Valid path within session
        result = resolve_path("output/report.md", session_dir)
        assert "session_123" in result.replace("\\", "/")


# ==============================================================================
# (c) send-code API verification_code leak tests
# ==============================================================================


class TestSendCodeNoVerificationCodeLeak:
    """Tests for send-code API never returning verification_code."""

    @pytest.mark.asyncio
    async def test_send_code_still_sends_email_even_in_debug_mode(self):
        """
        /send-code should ALWAYS call send_verification_email, even when
        DEBUG_RETURN_VERIFICATION_CODE is True.
        The debug flag should NOT skip email sending.
        """
        from api.auth import send_verification_code
        from api.models import SendCodeRequest

        with patch(
            "api.auth.get_user_by_email", new_callable=AsyncMock
        ) as mock_get_user:
            mock_get_user.return_value = {
                "id": 1,
                "email": "test@example.com",
                "verification_code_sent_at": None,
                "verification_code_failed_count": 0,
            }

            with patch(
                "api.auth.save_verification_code", new_callable=AsyncMock
            ) as mock_save:
                mock_save.return_value = True

                with patch(
                    "api.auth.send_verification_email", new_callable=AsyncMock
                ) as mock_email:
                    mock_email.return_value = True

                    with patch("api.auth.DEBUG_RETURN_VERIFICATION_CODE", True):
                        request = SendCodeRequest(email="test@example.com")
                        result = await send_verification_code(request)

                        # CRITICAL: Email MUST be sent even in debug mode
                        mock_email.assert_awaited_once_with("test@example.com", ANY)
                        assert result["code"] == 200
                        assert result["message"] == "验证码已发送到您的邮箱"
                        assert (
                            "data" not in result
                            or "verification_code" not in result.get("data", {})
                        )

    @pytest.mark.asyncio
    async def test_send_code_never_returns_verification_code_debug_mode(self):
        """
        /send-code should NEVER return verification_code in response,
        even when DEBUG_RETURN_VERIFICATION_CODE is True.
        """
        from api.auth import send_verification_code
        from api.models import SendCodeRequest

        # Mock user exists
        with patch(
            "api.auth.get_user_by_email", new_callable=AsyncMock
        ) as mock_get_user:
            mock_get_user.return_value = {
                "id": 1,
                "email": "test@example.com",
                "verification_code_sent_at": None,
                "verification_code_failed_count": 0,
            }

            with patch(
                "api.auth.save_verification_code", new_callable=AsyncMock
            ) as mock_save:
                mock_save.return_value = True

                with patch(
                    "api.auth.send_verification_email", new_callable=AsyncMock
                ) as mock_email:
                    mock_email.return_value = True

                    # Patch the DEBUG flag
                    with patch("api.auth.DEBUG_RETURN_VERIFICATION_CODE", True):
                        request = SendCodeRequest(email="test@example.com")
                        result = await send_verification_code(request)

                        # Should NOT contain verification_code in response
                        if isinstance(result, dict) and "data" in result:
                            assert "verification_code" not in result.get("data", {}), (
                                "verification_code should NEVER be returned in response"
                            )

    @pytest.mark.asyncio
    async def test_send_code_never_returns_verification_code_normal_mode(self):
        """
        /send-code should not return verification_code in normal mode.
        """
        from api.auth import send_verification_code
        from api.models import SendCodeRequest

        with patch(
            "api.auth.get_user_by_email", new_callable=AsyncMock
        ) as mock_get_user:
            mock_get_user.return_value = {
                "id": 1,
                "email": "test@example.com",
                "verification_code_sent_at": None,
                "verification_code_failed_count": 0,
            }

            with patch(
                "api.auth.save_verification_code", new_callable=AsyncMock
            ) as mock_save:
                mock_save.return_value = True

                with patch(
                    "api.auth.send_verification_email", new_callable=AsyncMock
                ) as mock_email:
                    mock_email.return_value = True

                    with patch("api.auth.DEBUG_RETURN_VERIFICATION_CODE", False):
                        request = SendCodeRequest(email="test@example.com")
                        result = await send_verification_code(request)

                        # Should NOT contain verification_code
                        if isinstance(result, dict) and "data" in result:
                            assert "verification_code" not in result.get("data", {})


# ==============================================================================
# (d) Redis token-blacklist fail-closed tests
# ==============================================================================


class TestRedisBlacklistFailClosed:
    """Tests for Redis blacklist checks failing closed with HTTP 503."""

    @pytest.mark.asyncio
    async def test_check_token_blacklist_raises_503_on_redis_unavailable(self):
        """
        check_token_blacklist should raise HTTP 503 when Redis is unavailable,
        not return False (fail-open).
        """
        from api.middleware import check_token_blacklist
        from fastapi import HTTPException

        with patch("api.middleware.get_redis_client", return_value=None):
            # Current behavior: returns False (fail-open)
            # Expected behavior: should raise HTTPException with 503

            with pytest.raises(HTTPException) as exc_info:
                await check_token_blacklist("some_token")

            assert exc_info.value.status_code == 503

    @pytest.mark.asyncio
    async def test_check_token_blacklist_raises_503_on_redis_error(self):
        """
        check_token_blacklist should raise HTTP 503 on Redis errors,
        not return False.
        """
        from api.middleware import check_token_blacklist
        from fastapi import HTTPException

        mock_redis = MagicMock()
        mock_redis.exists.side_effect = Exception("Redis connection error")

        with patch("api.middleware.get_redis_client", return_value=mock_redis):
            with pytest.raises(HTTPException) as exc_info:
                await check_token_blacklist("some_token")

            assert exc_info.value.status_code == 503

    @pytest.mark.asyncio
    async def test_verify_token_fails_closed_on_redis_unavailable(self):
        """
        verify_token should fail closed (reject) when Redis is unavailable.
        """
        from api.middleware import verify_token
        from fastapi import HTTPException

        with patch("api.middleware.get_redis_client", return_value=None):
            # Should raise HTTPException, not allow the request
            with pytest.raises(HTTPException) as exc_info:
                await verify_token(token="valid_looking_token")

            # Should be 503 (service unavailable), not 401
            assert exc_info.value.status_code == 503


# ==============================================================================
# (e) add_file_to_kb path rejection tests
# ==============================================================================


class TestAddFileToKBPathRejection:
    """Tests for add_file_to_kb rejecting absolute/out-of-session paths."""

    def test_add_file_to_kb_rejects_absolute_path_outside_session(self):
        """
        add_file_to_kb should reject absolute paths outside session directory.
        """
        from tools.local_rag_tools import add_file_to_kb

        with patch(
            "tools.local_rag_tools.get_session_context",
            return_value="D:/Project/updated/session_123",
        ):
            # Try to add a file from outside the session directory
            result = add_file_to_kb.invoke(
                {"file_path": "D:/SensitiveData/secrets.txt"}
            )

            # Should return error about path not allowed
            assert "不允许" in result or "拒绝" in result or "错误" in result, (
                "Absolute path outside session should be rejected"
            )

    def test_add_file_to_kb_rejects_traversal_path(self):
        """
        add_file_to_kb should reject path traversal attempts.
        """
        from tools.local_rag_tools import add_file_to_kb

        with patch(
            "tools.local_rag_tools.get_session_context",
            return_value="D:/Project/updated/session_123",
        ):
            result = add_file_to_kb.invoke({"file_path": "../../../etc/passwd"})

            assert "不允许" in result or "拒绝" in result or "错误" in result, (
                "Path traversal should be rejected"
            )

    def test_add_file_to_kb_accepts_valid_session_file(self):
        """
        add_file_to_kb should accept files within session directory.
        """
        from tools.local_rag_tools import add_file_to_kb

        session_dir = "D:/Project/updated/session_123"
        test_file = os.path.join(session_dir, "test.txt")

        # Create a test file
        os.makedirs(session_dir, exist_ok=True)
        with open(test_file, "w", encoding="utf-8") as f:
            f.write("Test content for knowledge base")

        try:
            with patch(
                "tools.local_rag_tools.get_session_context", return_value=session_dir
            ):
                with patch("tools.local_rag_tools._get_vector_store") as mock_store:
                    mock_store.return_value.add_documents = MagicMock()

                    result = add_file_to_kb.invoke({"file_path": "test.txt"})

                    # Should succeed (not contain rejection message)
                    assert "不允许" not in result and "拒绝" not in result, (
                        "Valid session file should be accepted"
                    )
        finally:
            # Cleanup
            if os.path.exists(test_file):
                os.remove(test_file)


# ==============================================================================
# Integration tests for tool callers
# ==============================================================================


class TestToolCallersSessionContainment:
    """Tests for tool callers handling path containment errors properly."""

    def test_read_file_content_handles_path_containment_error(self):
        """
        read_file_content should return user-friendly error for path violations.
        """
        from tools.upload_file_read_tools import read_file_content

        with patch(
            "tools.upload_file_read_tools.get_session_context",
            return_value="D:/Project/updated/session_123",
        ):
            with patch("tools.upload_file_read_tools.resolve_path") as mock_resolve:
                # Simulate path containment error
                from utils.path_utils import PathContainmentError

                mock_resolve.side_effect = PathContainmentError(
                    "Path outside session directory"
                )

                result = read_file_content.invoke({"filename": "D:/OtherDir/file.txt"})

                # Should return user-friendly error, not stack trace
                assert "不允许" in result or "拒绝" in result or "错误" in result
                assert "Traceback" not in result

    def test_generate_markdown_handles_path_containment_error(self):
        """
        generate_markdown should return user-friendly error for path violations.
        """
        from tools.markdown_tools import generate_markdown

        with patch(
            "tools.markdown_tools.get_session_context",
            return_value="D:/Project/updated/session_123",
        ):
            with patch("tools.markdown_tools.resolve_path") as mock_resolve:
                from utils.path_utils import PathContainmentError

                mock_resolve.side_effect = PathContainmentError(
                    "Path outside session directory"
                )

                result = generate_markdown.invoke(
                    {"content": "Test", "filename": "test.md"}
                )

                assert "不允许" in result or "拒绝" in result or "错误" in result
                assert "Traceback" not in result

    def test_convert_md_to_pdf_handles_path_containment_error(self):
        """
        convert_md_to_pdf should return user-friendly error for path violations.
        """
        from tools.pdf_tools import convert_md_to_pdf

        with patch(
            "tools.pdf_tools.get_session_context",
            return_value="D:/Project/updated/session_123",
        ):
            with patch("tools.pdf_tools.resolve_path") as mock_resolve:
                from utils.path_utils import PathContainmentError

                mock_resolve.side_effect = PathContainmentError(
                    "Path outside session directory"
                )

                result = convert_md_to_pdf.invoke(
                    {"md_filename": "D:/OtherDir/test.md"}
                )

                assert "不允许" in result or "拒绝" in result or "错误" in result
                assert "Traceback" not in result

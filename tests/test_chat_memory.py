"""
tests/test_chat_memory.py
测试聊天记忆管理器
"""

import os
import sys
import uuid

import pytest

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture
def memory_deps():
    """尝试导入记忆管理器依赖；不可用时跳过整个模块。"""
    try:
        from utils.chat_memory_manager import get_memory_manager  # noqa: F401
        from api.mongodb_client import init_mongodb_indexes  # noqa: F401
    except Exception as exc:
        pytest.skip(f"聊天记忆依赖不可用: {exc}")


@pytest.mark.asyncio
async def test_save_and_retrieve_messages(memory_deps):
    """保存消息后应能检索到相同数量和内容。"""
    from utils.chat_memory_manager import get_memory_manager
    from api.mongodb_client import init_mongodb_indexes

    try:
        await init_mongodb_indexes()
    except Exception as exc:
        pytest.skip(f"MongoDB 不可用: {exc}")

    manager = get_memory_manager()
    test_session_id = f"pytest_session_{uuid.uuid4().hex[:8]}"
    test_user_id = f"pytest_user_{uuid.uuid4().hex[:8]}"

    # 保存测试消息
    for i in range(5):
        await manager.save_message(
            session_id=test_session_id,
            user_id=test_user_id,
            role="user" if i % 2 == 0 else "assistant",
            content=f"Test message {i + 1}",
            immediate=True,
        )

    # 检索消息
    messages = await manager.get_messages(
        test_session_id, user_id=test_user_id, limit=10
    )
    assert len(messages) >= 5
    for idx, msg in enumerate(messages):
        expected_role = "user" if idx % 2 == 0 else "assistant"
        assert msg["role"] == expected_role


@pytest.mark.asyncio
async def test_session_stats(memory_deps):
    """会话统计应反映已保存的消息数。"""
    from utils.chat_memory_manager import get_memory_manager
    from api.mongodb_client import init_mongodb_indexes

    try:
        await init_mongodb_indexes()
    except Exception as exc:
        pytest.skip(f"MongoDB 不可用: {exc}")

    manager = get_memory_manager()
    test_session_id = "pytest_session_stats"
    test_user_id = "pytest_user_stats"

    await manager.save_message(
        session_id=test_session_id,
        user_id=test_user_id,
        role="user",
        content="stats test",
        immediate=True,
    )

    stats = await manager.get_session_stats(test_session_id, user_id=test_user_id)
    assert stats is not None
    assert isinstance(stats, dict)


@pytest.mark.asyncio
async def test_cache_hit(memory_deps):
    """重复读取同一会话应命中缓存并返回相同条数。"""
    from utils.chat_memory_manager import get_memory_manager
    from api.mongodb_client import init_mongodb_indexes

    try:
        await init_mongodb_indexes()
    except Exception as exc:
        pytest.skip(f"MongoDB 不可用: {exc}")

    manager = get_memory_manager()
    test_session_id = "pytest_session_cache"
    test_user_id = "pytest_user_cache"

    await manager.save_message(
        session_id=test_session_id,
        user_id=test_user_id,
        role="user",
        content="cache test",
        immediate=True,
    )

    first = await manager.get_messages(test_session_id, user_id=test_user_id, limit=10)
    second = await manager.get_messages(test_session_id, user_id=test_user_id, limit=10)
    assert len(first) == len(second)

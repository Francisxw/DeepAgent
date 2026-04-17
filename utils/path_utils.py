import os
from pathlib import Path
from typing import Optional


class PathContainmentError(Exception):
    """
    Exception raised when a path resolves outside the allowed session directory.
    This is a security error that should be handled by rejecting the operation.
    """

    pass


def resolve_path(filename: str, session_dir: Optional[str] = None) -> str:
    """
    统一的文件路径解析工具方法。

    核心功能：
    1. 清洗虚拟路径前缀 (/workspace, /mnt/data, /home/user)
    2. 结合 session_dir 处理相对/绝对路径，保证路径隔离
    3. 防止路径嵌套 (session_id/session_id)
    4. 拒绝解析到会话目录外的路径（安全强制）

    重要设计原则：
    - 所有相对路径都拼接到 session_dir 下，确保文件隔离在会话目录内
    - output/ 前缀的相对路径同样拼接到 session_dir（如 output/report.md → session_dir/output/report.md）
    - 当提供了 session_dir 时，拒绝解析到会话目录外的绝对路径

    Security:
    - 当 session_dir 提供时，任何解析后超出 session_dir 的路径都会触发 PathContainmentError
    - 这防止了路径遍历攻击和未授权文件访问

    Args:
        filename (str): 输入的文件名或路径
        session_dir (str, optional): 会话上下文目录

    Returns:
        str: 解析后的绝对路径

    Raises:
        PathContainmentError: 当路径解析后在 session_dir 外时抛出
    """
    path = Path(filename)
    path_str = filename.replace("\\", "/")  # 统一处理字符串匹配

    # 1. 虚拟路径清洗
    virtual_prefixes = ["/workspace", "/mnt/data", "/home/user"]
    for prefix in virtual_prefixes:
        if path_str.startswith(prefix):
            # 去掉前缀
            cleaned = path_str[len(prefix) :].lstrip("/")
            path = Path(cleaned)
            path_str = str(path).replace("\\", "/")
            break

    # 2. 检查是否是完整的 Windows 绝对路径（如 D:/.../...）
    is_full_abs_path = (
        len(path_str) > 2 and path_str[1] == ":" and path_str[0].isalpha()
    )

    # 如果是完整绝对路径，直接解析
    if is_full_abs_path:
        full_path = path.resolve()

        # 如果提供了 session_dir，必须验证路径在会话目录内
        if session_dir:
            session_path = Path(session_dir).resolve()
            session_name = session_path.name

            try:
                # 检查是否在会话目录内
                if session_path in full_path.parents or full_path == session_path:
                    # 检查嵌套 (例如 .../session_abc/session_abc/file.txt)
                    parts = full_path.parts
                    for i in range(len(parts) - 1):
                        if parts[i] == session_name and parts[i + 1] == session_name:
                            # 发现嵌套，修正为 session_dir / filename
                            return str(session_path / full_path.name)
                    return str(full_path)
                else:
                    # 绝对路径在会话目录外 - 拒绝访问
                    raise PathContainmentError(
                        f"路径 '{filename}' 解析后在会话目录外，访问被拒绝"
                    )
            except PathContainmentError:
                raise
            except Exception:
                # 其他异常也视为安全违规
                raise PathContainmentError(
                    f"路径 '{filename}' 安全验证失败，访问被拒绝"
                )

        return str(full_path)

    if not session_dir:
        return str(path.resolve())

    session_path = Path(session_dir).resolve()
    session_name = session_path.name

    # 3. 结合 Session Context

    # 检测 Unix 风格绝对路径 (以 / 开头)
    is_unix_abs = path_str.startswith("/")

    # 如果是绝对路径 (Windows带盘符 或 Unix/开头)
    if path.is_absolute() or (os.name == "nt" and is_unix_abs):
        # Windows 特殊情况：以 / 开头但无盘符，视为相对路径
        if os.name == "nt" and is_unix_abs and not path.drive:
            full_path = session_path / path_str.lstrip("/")
        else:
            full_path = path.resolve()

        # 检查是否在 session 目录内
        try:
            # 判断 full_path 是否是 session_path 的子路径
            if session_path in full_path.parents or full_path == session_path:
                # 检查嵌套 (例如 .../session_abc/session_abc/file.txt)
                # 检查路径部分中是否有连续重复的 session_name
                parts = full_path.parts
                for i in range(len(parts) - 1):
                    if parts[i] == session_name and parts[i + 1] == session_name:
                        # 发现嵌套，修正为 session_dir / filename
                        return str(session_path / full_path.name)
                return str(full_path)
            else:
                # 绝对路径在会话目录外 - 拒绝访问
                raise PathContainmentError(
                    f"路径 '{filename}' 解析后在会话目录外，访问被拒绝"
                )
        except PathContainmentError:
            raise
        except Exception:
            raise PathContainmentError(f"路径 '{filename}' 安全验证失败，访问被拒绝")

    else:
        # 相对路径处理
        parts = path.parts

        # 检查是否包含 session_name (避免重复)
        if session_name in parts:
            result = session_path / path.name
            # 验证结果仍在会话目录内
            result_resolved = result.resolve()
            if (
                session_path not in result_resolved.parents
                and result_resolved != session_path
            ):
                raise PathContainmentError(
                    f"路径 '{filename}' 解析后在会话目录外，访问被拒绝"
                )
            return str(result)

        # 默认：拼接到 session_dir（保留 output/ 等子目录结构）
        result = session_path / path

        # 最终安全验证：确保解析后的路径仍在会话目录内
        # 这可以防止路径遍历攻击（如 ../../../etc/passwd）
        try:
            result_resolved = result.resolve()
            if (
                session_path not in result_resolved.parents
                and result_resolved != session_path
            ):
                raise PathContainmentError(
                    f"路径 '{filename}' 解析后在会话目录外，访问被拒绝"
                )
        except PathContainmentError:
            raise
        except Exception:
            raise PathContainmentError(f"路径 '{filename}' 安全验证失败，访问被拒绝")

        return str(result)

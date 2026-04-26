# config.py - 共享配置模块（单一数据源）
import os
import secrets
from typing import List

# =========================================================================================
# JWT 配置
# =========================================================================================
# 生产环境务必通过环境变量设置 JWT_SECRET_KEY，不要使用默认值。

SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", secrets.token_urlsafe(32))
ALGORITHM: str = os.getenv("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
REFRESH_TOKEN_EXPIRE_MINUTES: int = int(
    os.getenv("REFRESH_TOKEN_EXPIRE_MINUTES", "10080")
)  # 7天

# =========================================================================================
# 调试配置
# =========================================================================================
# 为 True 时，发送验证码接口直接返回验证码明文，方便本地调试。
DEBUG_RETURN_VERIFICATION_CODE: bool = (
    os.getenv("DEBUG_RETURN_VERIFICATION_CODE", "false").lower() == "true"
)

# =========================================================================================
# CORS 配置
# =========================================================================================
# 逗号分隔的允许来源列表；未设置时默认允许本地开发地址。
_CORS_ORIGINS_RAW: str = os.getenv(
    "CORS_ORIGINS", f"http://127.0.0.1:{os.getenv('API_PORT', '8000')},http://localhost:{os.getenv('API_PORT', '8000')}"
)
CORS_ORIGINS: List[str] = [
    origin.strip() for origin in _CORS_ORIGINS_RAW.split(",") if origin.strip()
]

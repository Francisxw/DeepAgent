import os
import sys
from dotenv import load_dotenv

# 加载 .env 文件
load_dotenv()

import uuid
import asyncio
import re as _re
from urllib.parse import quote

# 获取项目根目录（api/server.py 的父目录的父目录）
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# 将项目根目录加入模块搜索路径，以便直接运行 `python api/server.py` 时能正确解析 `import api.xxx`
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import uvicorn
import logging
from fastapi import (
    FastAPI,
    WebSocket,
    WebSocketDisconnect,
    UploadFile,
    File,
    Form,
    HTTPException,
    Header,
    Depends,
    Request,
)
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from pydantic import BaseModel
from typing import List, Dict, Optional
import shutil
from api.mongodb_client import init_mongodb_indexes, close_mongodb_connection
from utils.chat_memory_manager import get_memory_manager
from api.middleware import get_current_user
from api.config import CORS_ORIGINS

# Import agent runner and monitor
# 注意：agent.main_agent 导入时会初始化 main_agent，这可能需要几秒钟
from agent.main_agent import run_deep_agent
from api.monitor import monitor

# Import authentication router
from api.auth import auth_router

# Import database initialization
from api.database import initialize_tables, test_connection
from api.redis_client import RedisClient
from api.mongodb_client import get_async_client

logger = logging.getLogger(__name__)

API_HOST = os.getenv("API_HOST", "127.0.0.1")
API_PORT = int(os.getenv("API_PORT", "8000"))


# 定义 lifespan 上下文管理器
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup 事件
    logger.info("Application starting up...")
    
    # 初始化 MongoDB 索引
    await init_mongodb_indexes()
    logger.info("MongoDB indexes initialized")

    # 初始化本地知识库（移至 lifespan 中，避免导入时执行导致 reload 循环）
    try:
        from tools.local_rag_tools import init_knowledge_base
        init_knowledge_base()
        logger.info("本地知识库初始化成功")
    except Exception as e:
        logger.warning("本地知识库初始化失败: %s", e)

    # 设置 WebSocket 管理器（不再需要手动绑定 loop）
    monitor.set_websocket_manager(manager)
    logger.info("WebSocket manager initialized")
    
    yield
    
    # Shutdown 事件
    logger.info("Application shutting down...")
    
    # 优雅关闭所有 WebSocket 连接
    await manager.close_all()
    
    # 刷新所有记忆缓冲区
    memory_manager = get_memory_manager()
    await memory_manager.flush_all()
    logger.info("Memory buffers flushed")
    
    # 关闭 MongoDB 连接
    await close_mongodb_connection()
    logger.info("MongoDB connection closed")
    logger.info("Application shutdown complete")


# 创建连接管理器对象（在 lifespan 之前定义，以便 lifespan 可以访问）
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        # 延迟绑定 loop，防止初始化时 loop 不一致（改为私有属性）
        self._loop: asyncio.AbstractEventLoop | None = None
        # 线程安全锁（用于保护 active_connections 字典访问）
        self._lock = asyncio.Lock()

    def get_loop(self) -> asyncio.AbstractEventLoop:
        """lazy 获取主事件循环"""
        if self._loop is None or self._loop.is_closed():
            try:
                self._loop = asyncio.get_running_loop()
            except RuntimeError:
                raise RuntimeError(
                    "No running event loop found. "
                    "ConnectionManager must be used within the main FastAPI async context."
                )
        return self._loop

    def set_loop(self, loop):
        """设置事件循环（保持向后兼容，但现在推荐使用 get_loop()）"""
        self._loop = loop
        monitor.set_websocket_manager(self)

    async def connect(self, websocket: WebSocket, thread_id: str):
        await websocket.accept()
        async with self._lock:
            self.active_connections[thread_id] = websocket
        logger.info("Client connected: %s", thread_id)

    async def disconnect(self, thread_id: str):
        """断开连接并关闭 WebSocket"""
        websocket = None
        async with self._lock:
            if thread_id in self.active_connections:
                websocket = self.active_connections.pop(thread_id)
        if websocket:
            try:
                await websocket.close(code=1000, reason="Client disconnected normally")
            except Exception:
                pass  # 连接可能已关闭
            logger.info("Client disconnected: %s", thread_id)

    async def send_personal_message(self, message: str, websocket: WebSocket):
        await websocket.send_text(message)

    async def send_to_thread(self, message: dict, thread_id: str):
        """向指定线程发送消息（在主事件循环中调用）"""
        if thread_id not in self.active_connections:
            logger.warning("Thread %s not connected", thread_id)
            return

        try:
            await self.active_connections[thread_id].send_json(message)
        except Exception as e:
            logger.error("Failed to send to thread %s: %s", thread_id, e)
            await self.disconnect(thread_id)

    def send_to_thread_safe(self, message: dict, thread_id: str):
        """供 ToolMonitor 从任意线程（线程池）安全调用"""
        if not thread_id:
            return
        
        try:
            loop = self.get_loop()
            asyncio.run_coroutine_threadsafe(
                self.send_to_thread(message, thread_id), 
                loop
            )
        except Exception as e:
            logger.warning("Failed to schedule WebSocket message: %s", e)

    async def close_all(self):
        """优雅关闭所有连接（shutdown 时调用）"""
        async with self._lock:
            if not self.active_connections:
                return
            connections = list(self.active_connections.items())
            self.active_connections.clear()

        logger.info("Closing %d WebSocket connections...", len(connections))
        for thread_id, websocket in connections:
            try:
                await websocket.close(code=1001, reason="Server shutting down")
            except Exception:
                pass  # 连接可能已关闭
        logger.info("All WebSocket connections closed.")


# 全局 manager 实例
manager = ConnectionManager()


class MemoryStatsResponse(BaseModel):
    """记忆统计响应"""

    session_id: str
    total_messages: int
    first_message: Optional[str] = None
    last_message: Optional[str] = None


class ClearSessionRequest(BaseModel):
    """清空会话请求"""

    session_id: str


# 使用 lifespan 创建 FastAPI 应用
app = FastAPI(
    title="DeepAgents API",
    description="Deep Agents API with JWT Authentication",
    version="1.0.0",  # 指定应用当前版本号
    lifespan=lifespan,  # 指定应用的生命周期管理器
    # 配置 OpenAPI 安全方案
    openapi_components={
        "securitySchemes": {
            "BearerAuth": {
                "type": "http",
                "scheme": "bearer",
                "bearerFormat": "JWT",
                "description": "JWT Bearer Token 认证。请先调用 /api/auth/login 获取 token，格式: Bearer <token>",
            }
        }
    },
)

# 挂载输出目录已被移除——文件下载统一走 /api/download（需认证），
# 不再通过 /outputs 公开暴露文件系统。
# 输出目录仍然保留，用于后端写入：
output_dir = os.path.join(project_root, "updated")
if not os.path.exists(output_dir):
    os.makedirs(output_dir)

# UI 目录路径
ui_dir = os.path.join(project_root, "ui")

# 定义上传目录 updated
updated_dir = os.path.join(project_root, "updated")
if not os.path.exists(updated_dir):
    os.makedirs(updated_dir)

# 配置 CORS（必须在路由定义之前）
# 使用 api.config 中显式定义的允许来源，而非通配符 + credentials 的不安全组合
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(CORS_ORIGINS),
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 包含认证路由（必须在静态文件挂载之前）
app.include_router(auth_router)


# ---------------------------------------------------------------------------
# 健康检查端点
# ---------------------------------------------------------------------------


@app.get("/health", tags=["Health"], summary="服务健康检查")
async def health_check():
    """
    返回服务及依赖组件的健康状态。
    任何依赖不可用时返回 degraded 状态而非假装健康。
    """
    checks = {}
    overall = "healthy"

    # MySQL
    try:
        mysql_ok = test_connection()
        checks["mysql"] = {
            "status": "ok" if mysql_ok else "error",
            "detail": None if mysql_ok else "connection failed",
        }
        if not mysql_ok:
            overall = "degraded"
    except Exception as exc:
        checks["mysql"] = {"status": "error", "detail": str(exc)}
        overall = "degraded"

    # Redis
    try:
        redis_client = RedisClient.get_client()
        if redis_client is not None:
            redis_client.ping()
            checks["redis"] = {"status": "ok"}
        else:
            checks["redis"] = {"status": "error", "detail": "client not available"}
            overall = "degraded"
    except Exception as exc:
        checks["redis"] = {"status": "error", "detail": str(exc)}
        overall = "degraded"

    # MongoDB
    try:
        client = await get_async_client()
        await client.admin.command("ping")
        checks["mongodb"] = {"status": "ok"}
    except Exception as exc:
        checks["mongodb"] = {"status": "error", "detail": str(exc)}
        overall = "degraded"

    return {"status": overall, "checks": checks}


# 根路由重定向到 auth.html
@app.get("/")
async def root():
    """根路径重定向到认证页面"""
    return FileResponse(os.path.join(ui_dir, "auth.html"))


# UI 路由处理 - 使用路由代替静态文件挂载，避免自动返回 index.html


@app.get("/ui")
async def ui_root():
    """UI路径重定向到认证页面"""
    return FileResponse(os.path.join(ui_dir, "auth.html"))


@app.get("/ui/")
async def ui_root_with_slash():
    """UI路径重定向到认证页面（带斜杠）"""
    return FileResponse(os.path.join(ui_dir, "auth.html"))


@app.get("/ui/auth.html")
async def auth_page():
    """认证页面"""
    return FileResponse(os.path.join(ui_dir, "auth.html"))


@app.get("/ui/index.html")
async def index_page():
    """主页面"""
    return FileResponse(os.path.join(ui_dir, "index.html"))


# 挂载静态资源目录（css, js, assets）到独立的路径 /assets/
# 注意：使用独立路径避免与 /ui/ 路由冲突
if os.path.exists(ui_dir):
    # 挂载 ui 目录到 /assets，然后通过 /assets/ 访问
    # 例如：/assets/css/style.css -> ui/css/style.css
    app.mount("/assets", StaticFiles(directory=ui_dir), name="assets")

# 挂载 /ui 路径的静态文件（css, js, assets）
# 前端HTML中引用的 /ui/css/... 和 /ui/js/... 需要这个挂载
if os.path.exists(ui_dir):
    app.mount("/ui", StaticFiles(directory=ui_dir), name="ui_static")


class TaskRequest(BaseModel):
    query: str
    thread_id: str | None = None


# /api/task接口：接收用户提示词，启动 Agent 运行
@app.post("/api/task", tags=["Agent"], summary="接收用户提示词,启动一个新的 Agent 任务")
async def run_task(
    task_request: TaskRequest, current_user: Dict = Depends(get_current_user)
):
    """
    启动一个新的 Agent 任务
    """
    thread_id = task_request.thread_id or str(uuid.uuid4())
    user_id = current_user["sub"]  # 从 token 中提取用户标识（email）

    # 异步运行 Agent，不阻塞主线程
    # 注意：run_deep_agent 现在是异步函数，直接在主事件循环中运行
    # 在生产环境中建议使用 Celery 或其他任务队列
    asyncio.create_task(run_deep_agent(task_request.query, thread_id, user_id))

    return {"status": "started", "thread_id": thread_id}


@app.options("/api/task")
async def run_task_options():
    """处理 OPTIONS 请求（CORS 预检）"""
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# 路径安全工具
# ---------------------------------------------------------------------------


def ensure_path_under_base(base_dir: str, target_path: str) -> str:
    """
    Resolve *target_path* and verify it resides under *base_dir*.

    Returns the canonical absolute path on success.
    Raises HTTPException(403) on traversal / out-of-root attempts.
    """
    base_real = os.path.realpath(base_dir)
    target_real = os.path.realpath(target_path)
    try:
        os.path.commonpath((base_real, target_real))
    except ValueError:
        raise HTTPException(
            status_code=403, detail="Access denied: path outside allowed directory"
        )
    if not os.path.commonpath((base_real,)) == os.path.commonpath(
        (base_real, target_real)
    ):
        raise HTTPException(
            status_code=403, detail="Access denied: path traversal detected"
        )
    # Simpler & reliable check:
    if not target_real.startswith(base_real + os.sep) and target_real != base_real:
        raise HTTPException(
            status_code=403, detail="Access denied: path outside allowed directory"
        )
    return target_real


# ---------------------------------------------------------------------------
# 文件操作路由（均需认证）
# ---------------------------------------------------------------------------


# 上传文件接口
@app.post("/api/upload", tags=["File"], summary="用户文件上传接口")
async def upload_files(
    files: List[UploadFile] = File(...),
    thread_id: str = Form(...),
    current_user: Dict = Depends(get_current_user),
):
    """
    上传文件到 updated/session_{thread_id} 目录
    """
    # Conservative thread_id validation: alphanumeric + hyphens/underscores only
    if not _re.fullmatch(r"[A-Za-z0-9_\-]+", thread_id):
        raise HTTPException(status_code=400, detail="Invalid thread_id")

    target_dir = os.path.join(updated_dir, f"session_{thread_id}")
    # Ensure target_dir is under updated_dir
    ensure_path_under_base(updated_dir, target_dir)
    if not os.path.exists(target_dir):
        os.makedirs(target_dir)

    saved_files = []
    for file in files:
        # Sanitize filename to prevent path traversal
        safe_name = os.path.basename(file.filename or "unnamed")
        file_path = os.path.join(target_dir, safe_name)
        # Final safety: ensure resolved path is still under target_dir
        ensure_path_under_base(target_dir, file_path)
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        saved_files.append(safe_name)

    return {"status": "uploaded", "files": saved_files}


# 下载文件接口
@app.get("/api/download", tags=["File"], summary="文件下载接口")
async def download_file(
    path: str,
    current_user: Dict = Depends(get_current_user),
):
    """
    下载指定文件（需认证）
    path: 绝对路径或相对于 updated 目录的相对路径
    """
    # 路径解析：如果是相对路径，基于 output_dir（即 updated 目录）解析
    if not os.path.isabs(path):
        abs_path = os.path.abspath(os.path.join(output_dir, path))
    else:
        abs_path = os.path.abspath(path)

    # 安全检查：确保解析后的路径在 output_dir 下
    abs_path = ensure_path_under_base(output_dir, abs_path)

    if not os.path.exists(abs_path):
        raise HTTPException(status_code=404, detail="File not found")

    if not os.path.isfile(abs_path):
        raise HTTPException(status_code=400, detail="Not a file")

    return FileResponse(abs_path, filename=os.path.basename(abs_path))


@app.get("/api/files", tags=["File"], summary="列出指定目录下的文件")
async def list_files(
    path: str,
    current_user: Dict = Depends(get_current_user),
):
    """
    列出指定目录下的文件（需认证）
    path: 相对于 output 目录的路径
    """
    # 如果是相对路径，相对于 output_dir 解析
    if not os.path.isabs(path):
        abs_path = os.path.abspath(os.path.join(output_dir, path))
    else:
        abs_path = os.path.abspath(path)

    # 安全检查
    abs_path = ensure_path_under_base(output_dir, abs_path)

    if not os.path.exists(abs_path):
        raise HTTPException(status_code=404, detail="Path not found")

    files = []
    try:
        for root, dirs, filenames in os.walk(abs_path):
            for filename in filenames:
                file_path = os.path.join(root, filename)

                # 计算相对于 output_dir 的路径，用于生成 URL
                rel_path = os.path.relpath(file_path, output_dir)
                # 使用 /api/download 而非已移除的 /outputs
                url_path = rel_path.replace("\\", "/")
                # URL-encode the path to handle special characters safely
                encoded_path = quote(url_path, safe="/")

                files.append(
                    {
                        "name": filename,
                        "type": "file",
                        "path": url_path,
                        "url": f"/api/download?path={encoded_path}",
                        "size": os.path.getsize(file_path),
                        "mtime": os.path.getmtime(file_path),
                    }
                )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    # 按时间倒序排列
    files.sort(key=lambda x: x.get("mtime", 0), reverse=True)
    return {"files": files}


@app.post("/api/memory/stats", response_model=MemoryStatsResponse)
async def get_memory_stats(
    session_id: str, current_user: Dict = Depends(get_current_user)
):
    """获取会话记忆统计信息（用户级隔离）"""
    user_id = current_user["sub"]
    memory_manager = get_memory_manager()
    stats = await memory_manager.get_session_stats(session_id, user_id)
    return MemoryStatsResponse(**stats)


@app.post("/api/memory/clear")
async def clear_session_memory(
    request: ClearSessionRequest, current_user: Dict = Depends(get_current_user)
):
    """清空会话记忆（用户级隔离）"""
    user_id = current_user["sub"]
    memory_manager = get_memory_manager()
    success = await memory_manager.clear_session(request.session_id, user_id)

    if success:
        return {"code": 200, "message": "Session memory cleared successfully"}
    else:
        return {"code": 500, "message": "Failed to clear session memory"}


@app.post("/api/memory/cleanup")
async def cleanup_old_memories(days: int = 30):
    """手动清理过期记忆"""
    memory_manager = get_memory_manager()
    deleted_count = await memory_manager.cleanup_old_sessions(days)

    return {
        "code": 200,
        "message": f"Cleaned up {deleted_count} old messages",
        "deleted_count": deleted_count,
    }


# 这个接口是一个兼容性处理机制，用于强制要求旧版客户端升级到新的连接方式
@app.websocket("/ws")
async def websocket_legacy(websocket: WebSocket):
    await websocket.accept()
    await websocket.send_json(
        {"type": "error", "message": "Client outdated. Please refresh page."}
    )
    await websocket.close(code=1000, reason="Client outdated")


# WebSocket连接不会出现在swagger文档中，但是实际运行时，会自动生成
@app.websocket("/ws/{thread_id}")
async def websocket_endpoint(websocket: WebSocket, thread_id: str):
    await manager.connect(websocket, thread_id)
    try:
        while True:
            # 保持连接活跃，并可以接收前端指令
            # 目前只作为简单的保活 echo
            data = await websocket.receive_text()
            await websocket.send_json({"type": "pong", "message": f"received: {data}"})
    except WebSocketDisconnect:
        await manager.disconnect(thread_id)
    except Exception as e:
        logger.error("WebSocket Error: %s", e)
        await manager.disconnect(thread_id)


if __name__ == "__main__":
    # 初始化数据库表结构
    logger.info("初始化数据库...")
    if test_connection():
        if initialize_tables():
            logger.info("数据库表结构初始化成功!")
        else:
            logger.error("数据库表结构初始化失败!")
    else:
        logger.error("数据库连接失败，请检查配置!")
    uvicorn.run("api.server:app", host=API_HOST, port=API_PORT, reload=(sys.platform != "win32"))
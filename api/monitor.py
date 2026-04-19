import datetime
import asyncio
import logging
from typing import Any, Dict, Optional
from api.context import get_thread_context

logger = logging.getLogger(__name__)

# 尝试导入全局运行时（用于脚本模式下的流式输出）
try:
    import builtins
except ImportError:
    builtins = None


class ToolMonitor:
    """
    工具监控类，用于在工具执行过程中上报进度和状态。
    设计为单例模式，可在任何工具中直接导入使用。
    兼容 FastAPI WebSocket 和 脚本运行时的 stream_writer。

    使用示例:
    from api.monitor import monitor

    def my_tool(arg1):
        monitor.report_start("my_tool", {"arg1": arg1})
        ...
        monitor.report_running("my_tool", "正在处理数据...", progress=0.5)
        ...
        monitor.report_end("my_tool", result)
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ToolMonitor, cls).__new__(cls)
            cls._instance.websocket_manager = None  # 预留给 FastAPI WebSocketManager
        return cls._instance

    def set_websocket_manager(self, manager):
        """设置 FastAPI 的 WebSocket 管理器"""
        self.websocket_manager = manager

    def _emit(
        self, event_type: str, message: str, data: Optional[Dict[str, Any]] = None
    ):
        """内部发送方法"""
        payload = {
            "type": "monitor_event",
            "event": event_type,
            "message": message,
            "data": data or {},
            "timestamp": datetime.datetime.now().isoformat(),
        }

        # 1. 优先尝试通过 FastAPI WebSocket 发送 (定向推送)
        if self.websocket_manager:
            thread_id = get_thread_context()
            if thread_id:
                try:
                    # 使用线程安全的发送方法（不再直接访问 loop）
                    self.websocket_manager.send_to_thread_safe(payload, thread_id)
                except Exception as e:
                    logger.warning("WebSocket send failed: %s", e)

        # 2. 尝试通过全局 runtime 输出 (DeepAgents 脚本模式)
        # 这使得 simple_agents.py 中的 MockRuntime 能接收到数据
        if (
            builtins
            and hasattr(builtins, "runtime")
            and hasattr(builtins.runtime, "stream_writer")
        ):
            try:
                builtins.runtime.stream_writer(payload)
            except Exception:
                pass

        # 3. 日志保底输出（替代 console print）
        logger.info("[Monitor:%s] %s", event_type, message)

    # _emit()函数基于WebSocket协议与前端交互，反馈任务执行进度和结果
    def report_tool(self, tool_name: str, args: Dict[str, Any] = None):
        """推送工具执行信息"""
        self._emit(
            "tool_start",
            f"开始执行工具: {tool_name}",
            {"tool_name": tool_name, "args": args},
        )

    def report_assistant(self, assistant_name: str, args: Dict[str, Any] = None):
        """推送正在调用的子智能体进度"""
        self._emit(
            "assistant_call",
            f"正在调用助手: {assistant_name}",
            {"assistant_name": assistant_name, "args": args},
        )

    def report_task_result(self, result: str):
        """推送任务最终结果"""
        self._emit("task_result", "任务执行完成", {"result": result})

    def report_session_dir(self, path: str):
        """推送任务工作目录"""
        self._emit("session_created", f"工作目录已创建: {path}", {"path": path})


# 全局单例实例
monitor = ToolMonitor()

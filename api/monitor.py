"""
改进版监控模块 (monitor_v2.py)

主要改进:
1. 使用 Enum 定义事件类型，避免字符串硬编码
2. 使用 dataclass 定义事件结构，提供类型安全
3. 提取消息模板到配置类，支持动态修改
4. 支持 progress 参数
5. 添加 WebSocket 抽象接口，提高可测试性
6. 添加事件过滤和采样机制
7. 完全向后兼容，支持渐进式迁移

使用方法:
    # 向后兼容（旧代码无需修改）
    from api.monitor_v2 import monitor
    monitor.report_tool("my_tool", {"arg": 1})

    # 新 API（推荐）
    from api.monitor_v2 import monitor, MonitorEventType
    monitor.emit_event(
        event_type=MonitorEventType.TOOL_START,
        message="开始处理",
        data={"tool_name": "my_tool"},
        progress=0.5
    )
"""

import os
import sys

# Add project root to path for imports
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import datetime
import asyncio
import logging
import random
from enum import Enum, auto
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, Optional, Callable, List, Set, Protocol, runtime_checkable
from abc import ABC, abstractmethod

from api.context import get_thread_context

logger = logging.getLogger(__name__)

# =============================================================================
# 1. 事件类型枚举
# =============================================================================

class MonitorEventType(str, Enum):
    """监控事件类型枚举

    使用枚举代替字符串，提供：
    - 类型安全（IDE 自动补全、拼写检查）
    - 集中管理所有事件类型
    - 易于扩展和重构
    """
    # 工具相关
    TOOL_START = "tool_start"
    TOOL_RUNNING = "tool_running"
    TOOL_END = "tool_end"
    TOOL_ERROR = "tool_error"

    # 子智能体相关
    ASSISTANT_CALL = "assistant_call"
    ASSISTANT_RETURN = "assistant_return"

    # 任务相关
    TASK_START = "task_start"
    TASK_RESULT = "task_result"
    TASK_ERROR = "task_error"

    # 会话相关
    SESSION_CREATED = "session_created"
    SESSION_ENDED = "session_ended"

    # 进度更新
    PROGRESS_UPDATE = "progress_update"

    # 系统事件
    ERROR_OCCURRED = "error_occurred"
    WARNING = "warning"
    INFO = "info"


class PayloadType(str, Enum):
    """Payload 类型枚举"""
    MONITOR_EVENT = "monitor_event"
    SYSTEM_EVENT = "system_event"


# =============================================================================
# 2. 消息模板系统
# =============================================================================

@dataclass(frozen=True)
class MessageTemplate:
    """消息模板

    支持两种格式化方式：
    1. 字符串模板: "开始执行工具: {tool_name}"
    2. 自定义格式化函数
    """
    template: str
    formatter: Optional[Callable[..., str]] = None

    def format(self, **kwargs) -> str:
        """格式化消息"""
        if self.formatter:
            return self.formatter(**kwargs)
        try:
            return self.template.format(**kwargs)
        except KeyError as e:
            logger.warning(f"Message template missing key: {e}")
            return self.template


class MonitorTemplates:
    """监控消息模板配置

    所有消息模板集中管理，支持：
    - 运行时修改（国际化、动态文案）
    - 模板覆盖（自定义特定事件的消息）
    """

    # 工具相关
    TOOL_START = MessageTemplate("开始执行工具: {tool_name}")
    TOOL_RUNNING = MessageTemplate("工具 {tool_name} 正在执行: {message}")
    TOOL_END = MessageTemplate("工具 {tool_name} 执行完成")
    TOOL_ERROR = MessageTemplate("工具 {tool_name} 执行出错: {error}")

    # 子智能体相关
    ASSISTANT_CALL = MessageTemplate("正在调用助手: {assistant_name}")
    ASSISTANT_RETURN = MessageTemplate("助手 {assistant_name} 返回结果")

    # 任务相关
    TASK_START = MessageTemplate("任务开始执行")
    TASK_RESULT = MessageTemplate("任务执行完成")
    TASK_ERROR = MessageTemplate("任务执行失败: {error}")

    # 会话相关
    SESSION_CREATED = MessageTemplate("工作目录已创建: {path}")
    SESSION_ENDED = MessageTemplate("会话已结束")

    # 进度更新
    PROGRESS_UPDATE = MessageTemplate("进度更新: {progress}% - {message}")

    # 存储覆盖配置
    _overrides: Dict[str, MessageTemplate] = {}

    @classmethod
    def get(cls, event_type: MonitorEventType) -> MessageTemplate:
        """获取模板，支持覆盖"""
        # 先检查覆盖配置
        if event_type.value in cls._overrides:
            return cls._overrides[event_type.value]

        # 否则返回默认模板
        template_name = event_type.name
        if hasattr(cls, template_name):
            return getattr(cls, template_name)

        # 兜底返回空模板
        return MessageTemplate(f"[{event_type.value}]")

    @classmethod
    def set_template(cls, event_type: MonitorEventType, template: str):
        """动态设置模板"""
        cls._overrides[event_type.value] = MessageTemplate(template)

    @classmethod
    def set_formatter(cls, event_type: MonitorEventType, formatter: Callable[..., str]):
        """设置自定义格式化函数"""
        cls._overrides[event_type.value] = MessageTemplate("", formatter=formatter)

    @classmethod
    def reset(cls, event_type: Optional[MonitorEventType] = None):
        """重置模板配置"""
        if event_type:
            cls._overrides.pop(event_type.value, None)
        else:
            cls._overrides.clear()


# =============================================================================
# 3. Payload 数据类
# =============================================================================

@dataclass
class MonitorEvent:
    """监控事件数据结构

    标准化的监控事件结构，包含完整的类型信息和可选字段。
    自动处理时间戳和转换为字典。
    """
    event: str  # 事件类型（建议使用 MonitorEventType 枚举）
    message: str
    data: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.datetime.now().isoformat())
    progress: Optional[float] = None
    type: str = PayloadType.MONITOR_EVENT.value

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典，自动过滤 None 值"""
        return {k: v for k, v in asdict(self).items() if v is not None}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MonitorEvent":
        """从字典创建事件"""
        # 过滤掉不在字段中的键
        valid_keys = {f.name for f in cls.__dataclass_fields__.values()}
        filtered_data = {k: v for k, v in data.items() if k in valid_keys}
        return cls(**filtered_data)


# =============================================================================
# 4. 事件发布器抽象接口
# =============================================================================

class EventPublisher(ABC):
    """事件发布器抽象基类

    定义统一的事件发布接口，便于：
    - 单元测试（MockPublisher）
    - 切换实现（WebSocket -> SSE -> Log）
    - 组合多个发布器（MultiPublisher）
    """

    @abstractmethod
    async def send_to_thread(self, payload: Dict[str, Any], thread_id: str) -> bool:
        """发送事件到指定线程

        Args:
            payload: 事件数据
            thread_id: 目标线程ID

        Returns:
            是否发送成功
        """
        pass

    @abstractmethod
    def send_to_thread_safe(self, payload: Dict[str, Any], thread_id: str) -> None:
        """线程安全的发送方法（非阻塞）"""
        pass


class WebSocketPublisher(EventPublisher):
    """WebSocket 事件发布器"""

    def __init__(self, manager: Any):
        self._manager = manager

    async def send_to_thread(self, payload: Dict[str, Any], thread_id: str) -> bool:
        try:
            await self._manager.send_to_thread(payload, thread_id)
            return True
        except Exception as e:
            logger.warning(f"WebSocket send failed: {e}")
            return False

    def send_to_thread_safe(self, payload: Dict[str, Any], thread_id: str) -> None:
        self._manager.send_to_thread_safe(payload, thread_id)


class LoggingPublisher(EventPublisher):
    """日志事件发布器（用于测试/调试）"""

    async def send_to_thread(self, payload: Dict[str, Any], thread_id: str) -> bool:
        logger.info(f"[Event to {thread_id}] {payload}")
        return True

    def send_to_thread_safe(self, payload: Dict[str, Any], thread_id: str) -> None:
        logger.info(f"[Event to {thread_id}] {payload}")


class MultiPublisher(EventPublisher):
    """组合多个发布器"""

    def __init__(self, publishers: List[EventPublisher]):
        self._publishers = publishers

    async def send_to_thread(self, payload: Dict[str, Any], thread_id: str) -> bool:
        results = []
        for pub in self._publishers:
            try:
                result = await pub.send_to_thread(payload, thread_id)
                results.append(result)
            except Exception as e:
                logger.warning(f"Publisher failed: {e}")
                results.append(False)
        return any(results)  # 至少一个成功

    def send_to_thread_safe(self, payload: Dict[str, Any], thread_id: str) -> None:
        for pub in self._publishers:
            try:
                pub.send_to_thread_safe(payload, thread_id)
            except Exception as e:
                logger.warning(f"Publisher failed: {e}")


# =============================================================================
# 5. 配置类
# =============================================================================

@dataclass
class MonitorConfig:
    """监控配置

    集中管理所有可配置项，支持运行时修改。
    """
    # 事件过滤
    enabled_events: Optional[Set[str]] = None  # 白名单，None 表示全部启用
    disabled_events: Set[str] = field(default_factory=set)  # 黑名单

    # 采样配置 {event_type: rate}
    sampling_rates: Dict[str, float] = field(default_factory=dict)

    # 日志级别映射 {event_type: logging_level}
    event_log_levels: Dict[str, int] = field(default_factory=lambda: {
        MonitorEventType.TOOL_START.value: logging.INFO,
        MonitorEventType.TOOL_RUNNING.value: logging.DEBUG,
        MonitorEventType.ASSISTANT_CALL.value: logging.INFO,
        MonitorEventType.TASK_RESULT.value: logging.INFO,
        MonitorEventType.SESSION_CREATED.value: logging.DEBUG,
        MonitorEventType.PROGRESS_UPDATE.value: logging.DEBUG,
    })
    default_log_level: int = logging.INFO

    # 时间戳配置
    use_utc: bool = False
    timestamp_format: str = "iso"  # "iso", "unix", "custom"
    custom_timestamp_format: Optional[str] = None

    # 上下文卸载配置
    max_retries: int = 3
    retry_delay: float = 0.1


# =============================================================================
# 6. 流写入器支持
# =============================================================================

@runtime_checkable
class RuntimeStreamWriter(Protocol):
    """流写入器协议"""
    def stream_writer(self, payload: Dict[str, Any]) -> None:
        ...


class StreamWriterRegistry:
    """流写入器注册表

    替代直接访问 builtins.runtime，提供更清晰的注册机制。
    """

    def __init__(self):
        self._writers: List[Callable[[Dict[str, Any]], None]] = []
        self._init_builtin_writer()

    def _init_builtin_writer(self):
        """自动检测并注册内置流写入器"""
        try:
            import builtins
            runtime = getattr(builtins, "runtime", None)
            if runtime and isinstance(runtime, RuntimeStreamWriter):
                self.add_writer(runtime.stream_writer)
                logger.debug("Registered builtin runtime stream writer")
        except ImportError:
            pass

    def add_writer(self, writer: Callable[[Dict[str, Any]], None]):
        """注册流写入器"""
        self._writers.append(writer)

    def remove_writer(self, writer: Callable[[Dict[str, Any]], None]):
        """移除流写入器"""
        if writer in self._writers:
            self._writers.remove(writer)

    def emit(self, payload: Dict[str, Any]):
        """发送给所有流写入器"""
        for writer in self._writers:
            try:
                writer(payload)
            except Exception as e:
                logger.debug(f"Stream writer failed: {e}")


# =============================================================================
# 7. 核心监控类
# =============================================================================

class ToolMonitor:
    """改进版工具监控类

    特性:
    - 单例模式（与 v1 兼容）
    - 类型安全的事件系统
    - 可配置的模板和过滤
    - 支持进度上报
    - 向后兼容的 API

    使用示例:
        # 旧 API（向后兼容）
        monitor.report_tool("search", {"query": "AI"})
        monitor.report_assistant("search_agent")

        # 新 API（推荐）
        monitor.emit_event(
            event_type=MonitorEventType.TOOL_START,
            message="开始搜索",
            data={"query": "AI"},
            progress=0.0
        )
    """

    _instance: Optional["ToolMonitor"] = None

    def __new__(cls) -> "ToolMonitor":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialize()
        return cls._instance

    def _initialize(self):
        """初始化（在 __new__ 中调用）"""
        self._publisher: Optional[EventPublisher] = None
        self._websocket_manager: Optional[Any] = None  # 向后兼容
        self._config = MonitorConfig()
        self._stream_registry = StreamWriterRegistry()

    # -------------------------------------------------------------------------
    # 配置方法
    # -------------------------------------------------------------------------

    def set_publisher(self, publisher: EventPublisher):
        """设置事件发布器（新 API）"""
        self._publisher = publisher

    def set_websocket_manager(self, manager: Any):
        """设置 WebSocket 管理器（向后兼容）"""
        self._websocket_manager = manager
        self._publisher = WebSocketPublisher(manager)

    def set_config(self, config: MonitorConfig):
        """更新配置"""
        self._config = config

    def get_config(self) -> MonitorConfig:
        """获取当前配置"""
        return self._config

    # -------------------------------------------------------------------------
    # 核心事件发射
    # -------------------------------------------------------------------------

    def emit_event(
        self,
        event_type: MonitorEventType,
        message: str,
        data: Optional[Dict[str, Any]] = None,
        progress: Optional[float] = None,
        payload_type: PayloadType = PayloadType.MONITOR_EVENT,
    ) -> bool:
        """发射监控事件（新 API，推荐使用）

        Args:
            event_type: 事件类型
            message: 消息内容
            data: 附加数据
            progress: 进度值 (0.0 - 1.0)
            payload_type: payload 类型

        Returns:
            是否成功发送
        """
        event = MonitorEvent(
            event=event_type.value,
            message=message,
            data=data or {},
            progress=progress,
            type=payload_type.value,
        )
        return self._emit(event)

    def _emit(self, event: MonitorEvent) -> bool:
        """内部发射方法"""
        event_type = event.event
        payload = event.to_dict()

        # 1. 检查事件过滤
        if not self._should_emit(event_type):
            return False

        # 2. 发送给 WebSocket（如果配置了）
        sent = False
        if self._publisher:
            thread_id = get_thread_context()
            if thread_id:
                try:
                    self._publisher.send_to_thread_safe(payload, thread_id)
                    sent = True
                except Exception as e:
                    self._log_event(event_type, f"WebSocket send failed: {e}", level=logging.WARNING)

        # 3. 发送给流写入器（脚本模式）
        self._stream_registry.emit(payload)

        # 4. 日志保底
        self._log_event(event_type, event.message)

        return sent

    def _should_emit(self, event_type: str) -> bool:
        """判断是否应发送事件"""
        cfg = self._config

        # 白名单检查
        if cfg.enabled_events is not None:
            if event_type not in cfg.enabled_events:
                return False

        # 黑名单检查
        if event_type in cfg.disabled_events:
            return False

        # 采样检查
        rate = cfg.sampling_rates.get(event_type, 1.0)
        if rate < 1.0 and random.random() > rate:
            return False

        return True

    def _log_event(self, event_type: str, message: str, level: Optional[int] = None):
        """记录事件日志"""
        if level is None:
            level = self._config.event_log_levels.get(
                event_type, self._config.default_log_level
            )
        logger.log(level, f"[Monitor:{event_type}] {message}")

    # -------------------------------------------------------------------------
    # 向后兼容的 API
    # -------------------------------------------------------------------------

    def report_tool(
        self,
        tool_name: str,
        args: Optional[Dict[str, Any]] = None,
        progress: Optional[float] = None,
    ):
        """推送工具开始执行（向后兼容 + 新 progress 参数）"""
        self.emit_event(
            event_type=MonitorEventType.TOOL_START,
            message=MonitorTemplates.TOOL_START.format(tool_name=tool_name),
            data={"tool_name": tool_name, "args": args},
            progress=progress,
        )

    def report_tool_running(
        self,
        tool_name: str,
        message: str,
        progress: Optional[float] = None,
        data: Optional[Dict[str, Any]] = None,
    ):
        """推送工具执行进度（新 API）"""
        merged_data = {"tool_name": tool_name}
        if data:
            merged_data.update(data)

        self.emit_event(
            event_type=MonitorEventType.TOOL_RUNNING,
            message=MonitorTemplates.TOOL_RUNNING.format(tool_name=tool_name, message=message),
            data=merged_data,
            progress=progress,
        )

    def report_tool_end(
        self,
        tool_name: str,
        result: Optional[Any] = None,
        data: Optional[Dict[str, Any]] = None,
    ):
        """推送工具执行完成（新 API）"""
        merged_data = {"tool_name": tool_name}
        if result is not None:
            merged_data["result"] = result
        if data:
            merged_data.update(data)

        self.emit_event(
            event_type=MonitorEventType.TOOL_END,
            message=MonitorTemplates.TOOL_END.format(tool_name=tool_name),
            data=merged_data,
        )

    def report_tool_error(
        self,
        tool_name: str,
        error: str,
        data: Optional[Dict[str, Any]] = None,
    ):
        """推送工具执行错误（新 API）"""
        merged_data = {"tool_name": tool_name, "error": error}
        if data:
            merged_data.update(data)

        self.emit_event(
            event_type=MonitorEventType.TOOL_ERROR,
            message=MonitorTemplates.TOOL_ERROR.format(tool_name=tool_name, error=error),
            data=merged_data,
        )

    def report_assistant(
        self,
        assistant_name: str,
        args: Optional[Dict[str, Any]] = None,
        progress: Optional[float] = None,
    ):
        """推送子智能体调用（向后兼容 + 新 progress 参数）"""
        self.emit_event(
            event_type=MonitorEventType.ASSISTANT_CALL,
            message=MonitorTemplates.ASSISTANT_CALL.format(assistant_name=assistant_name),
            data={"assistant_name": assistant_name, "args": args},
            progress=progress,
        )

    def report_task_result(
        self,
        result: str,
        data: Optional[Dict[str, Any]] = None,
    ):
        """推送任务结果（向后兼容 + 新 data 参数）"""
        merged_data = {"result": result}
        if data:
            merged_data.update(data)

        self.emit_event(
            event_type=MonitorEventType.TASK_RESULT,
            message=MonitorTemplates.TASK_RESULT.format(),
            data=merged_data,
        )

    def report_task_error(
        self,
        error: str,
        data: Optional[Dict[str, Any]] = None,
    ):
        """推送任务错误（新 API）"""
        merged_data = {"error": error}
        if data:
            merged_data.update(data)

        self.emit_event(
            event_type=MonitorEventType.TASK_ERROR,
            message=MonitorTemplates.TASK_ERROR.format(error=error),
            data=merged_data,
        )

    def report_session_dir(
        self,
        path: str,
    ):
        """推送会话目录创建（向后兼容）"""
        self.emit_event(
            event_type=MonitorEventType.SESSION_CREATED,
            message=MonitorTemplates.SESSION_CREATED.format(path=path),
            data={"path": path},
        )

    def report_progress(
        self,
        message: str,
        progress: float,
        data: Optional[Dict[str, Any]] = None,
    ):
        """推送通用进度更新（新 API）"""
        self.emit_event(
            event_type=MonitorEventType.PROGRESS_UPDATE,
            message=MonitorTemplates.PROGRESS_UPDATE.format(progress=int(progress * 100), message=message),
            data=data,
            progress=progress,
        )


# =============================================================================
# 8. 全局单例实例
# =============================================================================

# 全局单例，与 v1 保持相同的导入方式
monitor = ToolMonitor()


# =============================================================================
# 9. 便捷函数
# =============================================================================

def set_monitor_config(config: MonitorConfig):
    """设置全局监控配置"""
    monitor.set_config(config)


def enable_events(*event_types: MonitorEventType):
    """启用指定事件（白名单模式）"""
    config = monitor.get_config()
    if config.enabled_events is None:
        config.enabled_events = set()
    config.enabled_events.update(e.value for e in event_types)


def disable_events(*event_types: MonitorEventType):
    """禁用指定事件（黑名单）"""
    config = monitor.get_config()
    config.disabled_events.update(e.value for e in event_types)


def set_event_sampling(event_type: MonitorEventType, rate: float):
    """设置事件采样率"""
    config = monitor.get_config()
    config.sampling_rates[event_type.value] = rate


# =============================================================================
# 10. __all__ 定义
# =============================================================================

__all__ = [
    # 核心类
    "ToolMonitor",
    "monitor",
    "MonitorEvent",

    # 枚举
    "MonitorEventType",
    "PayloadType",

    # 模板
    "MonitorTemplates",
    "MessageTemplate",

    # 发布器
    "EventPublisher",
    "WebSocketPublisher",
    "LoggingPublisher",
    "MultiPublisher",

    # 配置
    "MonitorConfig",
    "set_monitor_config",
    "enable_events",
    "disable_events",
    "set_event_sampling",

    # 流写入器
    "StreamWriterRegistry",
]


# =============================================================================
# 11. 测试代码
# =============================================================================

if __name__ == "__main__":
    import asyncio

    async def test_monitor():
        print("=" * 60)
        print("测试 monitor_v2.py")
        print("=" * 60)

        # 1. 测试向后兼容 API
        print("\n[1] 测试向后兼容 API:")
        monitor.report_tool("test_tool", {"arg": 1})
        monitor.report_assistant("test_agent")
        monitor.report_session_dir("/tmp/session_123")
        monitor.report_task_result("任务完成")

        # 2. 测试新 API
        print("\n[2] 测试新 API:")
        monitor.emit_event(
            event_type=MonitorEventType.TOOL_START,
            message="新 API 测试",
            data={"test": True},
            progress=0.5,
        )

        # 3. 测试模板定制
        print("\n[3] 测试模板定制:")
        MonitorTemplates.set_template(MonitorEventType.TOOL_START, "🚀 工具启动: {tool_name}")
        monitor.report_tool("custom_tool", {})
        MonitorTemplates.reset(MonitorEventType.TOOL_START)  # 恢复

        # 4. 测试事件过滤
        print("\n[4] 测试事件过滤:")
        disable_events(MonitorEventType.TOOL_START)
        print("禁用 TOOL_START 后:")
        monitor.report_tool("filtered_tool", {})  # 应该不会发送
        enable_events(MonitorEventType.TOOL_START)
        print("启用后:")
        monitor.report_tool("enabled_tool", {})  # 应该会发送

        # 5. 测试采样
        print("\n[5] 测试采样 (采样率 0.5, 10 次调用):")
        set_event_sampling(MonitorEventType.PROGRESS_UPDATE, 0.5)
        sent_count = 0
        for i in range(10):
            # 注意：这里只是测试采样逻辑，实际需要 WebSocket 才能看到效果
            sent = monitor._should_emit(MonitorEventType.PROGRESS_UPDATE.value)
            if sent:
                sent_count += 1
        print(f"采样结果: {sent_count}/10 被发送 (预期约 5)")

        # 6. 测试进度上报
        print("\n[6] 测试进度上报:")
        monitor.report_progress("处理中", 0.25)
        monitor.report_tool_running("my_tool", "正在计算", 0.5)

        print("\n" + "=" * 60)
        print("测试完成!")
        print("=" * 60)

    asyncio.run(test_monitor())

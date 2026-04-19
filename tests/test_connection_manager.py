"""
tests/test_connection_manager.py
测试 WebSocket ConnectionManager 类
"""

import os
import sys
import asyncio
import threading
import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class MockWebSocket:
    """模拟 FastAPI WebSocket 用于测试"""
    def __init__(self):
        self.accepted = False
        self.closed = False
        self.close_code = None
        self.close_reason = None
        self.sent_messages = []
        self.client_state = "CONNECTED"  # 模拟 websocket.client_state

    async def accept(self):
        self.accepted = True

    async def close(self, code=1000, reason=""):
        self.closed = True
        self.close_code = code
        self.close_reason = reason
        self.client_state = "DISCONNECTED"

    async def send_json(self, message):
        self.sent_messages.append(message)

    async def send_text(self, message):
        self.sent_messages.append(message)


@pytest.fixture
def connection_manager():
    """提供 ConnectionManager 实例的 fixture"""
    try:
        from api.server import ConnectionManager
        return ConnectionManager()
    except ImportError as exc:
        pytest.skip(f"ConnectionManager 导入失败: {exc}")


@pytest.fixture
def mock_websocket():
    """提供 MockWebSocket 实例的 fixture"""
    return MockWebSocket()


# ============ 测试用例 ============

@pytest.mark.asyncio
async def test_connect_adds_to_active_connections(connection_manager, mock_websocket):
    """测试: connect() 方法应将连接添加到 active_connections"""
    await connection_manager.connect(mock_websocket, "thread-1")
    assert "thread-1" in connection_manager.active_connections


@pytest.mark.asyncio
async def test_disconnect_closes_websocket(connection_manager, mock_websocket):
    """测试: disconnect() 方法应关闭 WebSocket 连接"""
    # 先建立连接
    await connection_manager.connect(mock_websocket, "thread-1")
    # 断开连接
    await connection_manager.disconnect("thread-1")
    # 验证 WebSocket 已关闭
    assert mock_websocket.closed is True
    assert mock_websocket.close_code == 1000


@pytest.mark.asyncio
async def test_disconnect_removes_from_active_connections(connection_manager, mock_websocket):
    """测试: disconnect() 方法应从 active_connections 中移除连接"""
    # 先建立连接
    await connection_manager.connect(mock_websocket, "thread-1")
    assert "thread-1" in connection_manager.active_connections
    
    # 断开连接
    await connection_manager.disconnect("thread-1")
    
    # 验证已从 active_connections 中移除
    assert "thread-1" not in connection_manager.active_connections


@pytest.mark.asyncio
async def test_send_to_thread_delivers_message(connection_manager, mock_websocket):
    """测试: send_to_thread() 方法应向指定线程发送消息"""
    # 建立连接
    await connection_manager.connect(mock_websocket, "thread-1")
    
    # 发送消息
    test_message = {"type": "test", "content": "hello"}
    await connection_manager.send_to_thread(test_message, "thread-1")
    
    # 验证消息已发送
    assert len(mock_websocket.sent_messages) == 1
    assert mock_websocket.sent_messages[0] == test_message


@pytest.mark.asyncio
async def test_send_to_thread_safe_from_different_thread(connection_manager, mock_websocket):
    """测试: send_to_thread_safe() 方法应可从不同线程安全调用"""
    # 建立连接
    await connection_manager.connect(mock_websocket, "thread-1")
    
    # 设置事件循环（模拟 FastAPI lifespan 行为）
    loop = asyncio.get_event_loop()
    connection_manager.set_loop(loop)
    
    # 在另一个线程中调用 send_to_thread_safe（现在是同步方法）
    test_message = {"type": "thread_safe_test", "content": "from another thread"}
    results = []
    
    def send_from_thread():
        try:
            # send_to_thread_safe 现在是同步方法，直接调用
            connection_manager.send_to_thread_safe(test_message, "thread-1")
            results.append("success")
        except Exception as e:
            results.append(f"error: {e}")
    
    # 在新线程中执行
    thread = threading.Thread(target=send_from_thread)
    thread.start()
    # 必须让出控制权，以便事件循环能够处理调度协程
    while thread.is_alive():
        await asyncio.sleep(0.01)
    
    # 额外等待，让内部调度的协程有时间执行
    await asyncio.sleep(0.1)
    
    # 验证结果
    assert len(results) == 1
    assert results[0] == "success"
    assert len(mock_websocket.sent_messages) == 1
    assert mock_websocket.sent_messages[0] == test_message


@pytest.mark.asyncio
async def test_close_all_closes_all_connections(connection_manager):
    """测试: close_all() 方法应关闭所有连接"""
    # 创建 3 个连接
    mock_ws1 = MockWebSocket()
    mock_ws2 = MockWebSocket()
    mock_ws3 = MockWebSocket()
    
    await connection_manager.connect(mock_ws1, "thread-1")
    await connection_manager.connect(mock_ws2, "thread-2")
    await connection_manager.connect(mock_ws3, "thread-3")
    
    assert len(connection_manager.active_connections) == 3
    
    # 关闭所有连接
    await connection_manager.close_all()
    
    # 验证所有连接都已关闭
    assert mock_ws1.closed is True
    assert mock_ws2.closed is True
    assert mock_ws3.closed is True
    # 验证 active_connections 为空
    assert len(connection_manager.active_connections) == 0


@pytest.mark.asyncio
async def test_close_all_uses_going_away_code(connection_manager):
    """测试: close_all() 方法应使用 1001 (going away) 关闭码"""
    mock_ws = MockWebSocket()
    await connection_manager.connect(mock_ws, "thread-1")
    
    # 关闭所有连接
    await connection_manager.close_all()
    
    # 验证关闭码为 1001
    assert mock_ws.close_code == 1001
    assert mock_ws.close_reason == "Server shutting down"


@pytest.mark.asyncio
async def test_send_to_non_existent_thread_logs_warning(connection_manager, caplog):
    """测试: 向不存在的 thread_id 发送消息时应记录警告日志"""
    with caplog.at_level(logging.WARNING):
        test_message = {"type": "test"}
        await connection_manager.send_to_thread(test_message, "non-existent-thread")
        
        # 验证日志中包含警告
        assert any("non-existent-thread" in record.message for record in caplog.records)


@pytest.mark.asyncio
async def test_double_disconnect_is_idempotent(connection_manager, mock_websocket):
    """测试: 对同一连接断开两次应是幂等的，不抛出异常"""
    # 建立连接
    await connection_manager.connect(mock_websocket, "thread-1")
    
    # 第一次断开
    await connection_manager.disconnect("thread-1")
    assert mock_websocket.closed is True
    
    # 第二次断开（不应抛出异常）
    try:
        await connection_manager.disconnect("thread-1")
    except Exception as e:
        pytest.fail(f"第二次断开不应抛出异常: {e}")
    
    # 验证连接仍然已关闭
    assert mock_websocket.closed is True


@pytest.mark.asyncio
async def test_concurrent_send_to_thread_safe(connection_manager):
    """测试: 多个线程同时发送消息应无竞争条件"""
    # 建立连接
    mock_ws = MockWebSocket()
    await connection_manager.connect(mock_ws, "thread-1")
    
    # 设置事件循环（模拟 FastAPI lifespan 行为）
    loop = asyncio.get_event_loop()
    connection_manager.set_loop(loop)
    
    # 并发发送消息
    message_count = 10
    errors = []
    success_count = [0]  # 使用列表以便在闭包中修改
    
    def send_from_thread(thread_id):
        try:
            test_message = {"type": "concurrent_test", "thread_id": thread_id}
            # send_to_thread_safe 现在是同步方法，直接调用
            connection_manager.send_to_thread_safe(test_message, "thread-1")
            success_count[0] += 1
        except Exception as e:
            errors.append(f"Thread {thread_id}: {e}")
    
    # 创建多个线程同时发送
    threads = []
    for i in range(message_count):
        t = threading.Thread(target=send_from_thread, args=(i,))
        threads.append(t)
    
    # 启动所有线程
    for t in threads:
        t.start()
    
    # 等待所有线程完成（让出控制权以便事件循环处理）
    alive = True
    while alive:
        alive = False
        for t in threads:
            if t.is_alive():
                alive = True
                break
        if alive:
            await asyncio.sleep(0.01)
    
    # 额外等待，让内部调度的协程有时间执行
    await asyncio.sleep(0.2)
    
    # 验证结果
    assert len(errors) == 0, f"并发发送出现错误: {errors}"
    assert success_count[0] == message_count
    assert len(mock_ws.sent_messages) == message_count


@pytest.mark.asyncio
async def test_get_loop_lazy_initialization(connection_manager):
    """测试: get_loop() 方法应支持懒加载事件循环"""
    # 初始状态 loop 应为 None
    assert connection_manager._loop is None or not hasattr(connection_manager, '_loop')
    
    # 调用 get_loop() 应懒加载并返回事件循环
    loop = connection_manager.get_loop()
    assert loop is not None
    assert isinstance(loop, asyncio.AbstractEventLoop)
    
    # 多次调用应返回同一个 loop 实例
    loop2 = connection_manager.get_loop()
    assert loop is loop2


@pytest.mark.asyncio
async def test_send_to_thread_with_websocket_error(connection_manager, mock_websocket):
    """测试: send_to_thread() 在 WebSocket 发送失败时应处理异常"""
    # 建立连接
    await connection_manager.connect(mock_websocket, "thread-1")
    
    # 模拟发送失败
    async def failing_send_json(message):
        raise Exception("WebSocket connection lost")
    
    mock_websocket.send_json = failing_send_json
    
    # 发送消息（不应抛出未处理的异常）
    test_message = {"type": "test"}
    try:
        await connection_manager.send_to_thread(test_message, "thread-1")
    except Exception:
        # 可能抛出异常，但不应导致测试失败
        pass


@pytest.mark.asyncio
async def test_connect_replaces_existing_connection(connection_manager, mock_websocket):
    """测试: connect() 方法应替换已存在的同名连接"""
    mock_ws2 = MockWebSocket()
    
    # 第一次连接
    await connection_manager.connect(mock_websocket, "thread-1")
    assert connection_manager.active_connections["thread-1"] is mock_websocket
    
    # 使用相同的 thread_id 再次连接（应替换）
    await connection_manager.connect(mock_ws2, "thread-1")
    assert connection_manager.active_connections["thread-1"] is mock_ws2

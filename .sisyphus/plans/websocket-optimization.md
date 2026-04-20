# WebSocket ConnectionManager 优化

## TL;DR

> **Quick Summary**: 重构 WebSocket ConnectionManager，移除不必要的 set_loop，添加线程安全发送、优雅关闭、并改为异步 disconnect。采用 TDD 方法确保行为正确。
> 
> **Deliverables**:
> - 重构后的 `ConnectionManager` 类（新增 get_loop、send_to_thread_safe、close_all 方法）
> - 重构后的 `ToolMonitor._emit()` 方法
> - 更新后的 `lifespan` 函数
> - 更新后的 WebSocket 端点
> - 完整的测试套件 `tests/test_connection_manager.py`
> 
> **Estimated Effort**: Medium
> **Parallel Execution**: NO - sequential (TDD requires tests first)
> **Critical Path**: T1(TDD tests) → T2(ConnectionManager) → T3(ToolMonitor) → T4(lifespan) → T5(endpoint) → F1-F4(final verification)

---

## Context

### Original Request
用户指出当前 WebSocket ConnectionManager 实现存在以下问题：
1. `set_loop` 不必要 - 现代 FastAPI + Uvicorn 不需要手动绑定 loop
2. Shutdown 阶段没有优雅关闭活跃的 WebSocket 连接
3. `disconnect` 是同步方法，应该改为异步并主动关闭 WebSocket
4. `send_to_thread` 缺少错误处理和日志

### Interview Summary
**Key Discussions**:
- **set_loop 处理**: 用户选择 Lazy 初始化方案，通过 `get_loop()` 方法延迟获取事件循环
- **disconnect 行为**: 确认需要主动调用 `await websocket.close(code=1000)`
- **测试策略**: 确认使用 TDD（测试先行）
- **线程安全**: Metis 指出 `active_connections` 需要 `asyncio.Lock` 保护

**Research Findings**:
- 当前 `ConnectionManager` 在 `api/server.py:80-110`
- `ToolMonitor._emit()` 使用 `run_coroutine_threadsafe()` 需要目标 loop
- `lifespan` 在 `api/server.py:57-76`
- WebSocket 端点在 `api/server.py:509-522`

### Metis Review
**Identified Gaps** (addressed):
- **线程安全**: 添加 `asyncio.Lock` 保护 `active_connections` 字典访问
- **关闭码策略**: disconnect 用 1000，close_all 用 1001
- **超时策略**: close_all 需要 5 秒超时
- **边缘情况处理**: 双重关闭、发送中断开、loop 已关闭等
- **测试覆盖**: 需要并发测试、边缘情况测试、集成测试

---

## Work Objectives

### Core Objective
重构 WebSocket ConnectionManager，使其更健壮、线程安全，并支持优雅关闭。

### Concrete Deliverables
- `api/server.py` - 重构后的 ConnectionManager、lifespan、websocket_endpoint
- `api/monitor.py` - 重构后的 ToolMonitor._emit()
- `tests/test_connection_manager.py` - 完整的测试套件

### Definition of Done
- [ ] 所有测试通过：`pytest tests/test_connection_manager.py -v`
- [ ] 应用启动成功，WebSocket 连接正常
- [ ] Shutdown 时所有 WebSocket 连接优雅关闭
- [ ] 无线程安全警告或错误

### Must Have
- `get_loop()` 方法实现 lazy 事件循环获取
- `send_to_thread_safe()` 方法支持跨线程安全调用
- `close_all()` 方法实现优雅关闭所有连接
- `disconnect()` 改为异步并调用 `websocket.close()`
- `asyncio.Lock` 保护 `active_connections` 字典
- 完整的测试覆盖

### Must NOT Have (Guardrails)
- 不要添加重试逻辑（超出范围）
- 不要添加心跳/ping-pong 机制（超出范围）
- 不要添加指标收集（超出范围）
- 不要修改 ToolMonitor 公共 API 签名
- 不要修改 WebSocket 消息载荷结构
- 不要添加配置选项（超时硬编码为 5 秒）

---

## Verification Strategy (MANDATORY)

### Test Decision
- **Infrastructure exists**: YES (pytest)
- **Automated tests**: TDD (测试先行)
- **Framework**: pytest + pytest-asyncio

### QA Policy
Every task includes agent-executed QA scenarios.
Evidence saved to `.sisyphus/evidence/task-{N}-{scenario-slug}.{ext}`.

---

## Execution Strategy

### Parallel Execution Waves

```
Wave 1 (TDD - 先写测试):
└── Task 1: 编写 ConnectionManager 测试套件 [quick]

Wave 2 (实现 - 按依赖顺序):
├── Task 2: 重构 ConnectionManager 类 [deep]
├── Task 3: 重构 ToolMonitor._emit() [quick]
├── Task 4: 更新 lifespan 函数 [quick]
└── Task 5: 更新 WebSocket 端点 [quick]

Wave FINAL (验证):
├── Task F1: Plan compliance audit (oracle)
├── Task F2: Code quality review (unspecified-high)
├── Task F3: Real manual QA (unspecified-high)
└── Task F4: Scope fidelity check (deep)
```

### Dependency Matrix

- **1**: - - 2
- **2**: 1 - 3, 4, 5
- **3**: 2 - F3
- **4**: 2 - F1, F3
- **5**: 2 - F3
- **F1-F4**: 2, 3, 4, 5 - user okay

### Agent Dispatch Summary

- **Wave 1**: T1 → `quick`
- **Wave 2**: T2 → `deep`, T3-T5 → `quick`
- **FINAL**: F1 → `oracle`, F2-F3 → `unspecified-high`, F4 → `deep`

---

## TODOs

- [x] 1. **编写 ConnectionManager 测试套件 (TDD)**

  **What to do**:
  - 创建 `tests/test_connection_manager.py`
  - 编写测试用例：
    - `test_connect_adds_to_active_connections` - 连接添加到 active_connections
    - `test_disconnect_closes_websocket` - disconnect 调用 websocket.close(code=1000)
    - `test_disconnect_removes_from_active_connections` - disconnect 移除连接
    - `test_send_to_thread_delivers_message` - send_to_thread 发送消息
    - `test_send_to_thread_safe_from_different_thread` - 跨线程安全发送
    - `test_close_all_closes_all_connections` - close_all 关闭所有连接
    - `test_close_all_uses_going_away_code` - close_all 使用 1001 关闭码
    - `test_send_to_non_existent_thread_logs_warning` - 发送到不存在的 thread 记录警告
    - `test_double_disconnect_is_idempotent` - 双重 disconnect 是幂等的
    - `test_concurrent_send_to_thread_safe` - 并发发送测试
  - 创建 MockWebSocket 辅助类

  **Must NOT do**:
  - 不要实现实际代码（TDD 先写测试）
  - 不要跳过任何测试用例

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: 编写测试代码是标准化的任务
  - **Skills**: []
    - 不需要特殊技能

  **Parallelization**:
  - **Can Run In Parallel**: NO (TDD 需要先有测试)
  - **Parallel Group**: Sequential
  - **Blocks**: Task 2, 3, 4, 5
  - **Blocked By**: None

  **References**:
  - `api/server.py:80-110` - 当前 ConnectionManager 实现
  - `api/server.py:509-522` - WebSocket 端点使用方式
  - `tests/test_chat_memory.py` - 项目现有测试模式参考

  **Acceptance Criteria**:
  - [ ] 测试文件创建：`tests/test_connection_manager.py`
  - [ ] pytest 收集到至少 10 个测试用例
  - [ ] 所有测试初始状态为 FAIL（TDD 红灯阶段）

  **QA Scenarios**:
  ```
  Scenario: 测试文件存在且可运行
    Tool: Bash (pytest)
    Steps:
      1. pytest tests/test_connection_manager.py --collect-only
      2. 验证输出包含至少 10 个测试函数
    Expected Result: "10 tests collected"
    Evidence: .sisyphus/evidence/task-1-tests-collected.txt
  ```

  **Commit**: YES
  - Message: `test(websocket): add ConnectionManager test suite`
  - Files: `tests/test_connection_manager.py`

- [x] 2. **重构 ConnectionManager 类**

  **What to do**:
  - 添加 `self._lock = asyncio.Lock()` 到 `__init__`
  - 添加 `self._loop: asyncio.AbstractEventLoop | None = None` 替代 `self.loop`
  - 实现 `get_loop()` 方法（lazy 获取事件循环，检查 `is_closed()`）
  - 实现 `send_to_thread_safe()` 方法（供 ToolMonitor 跨线程调用）
  - 实现 `close_all()` 方法（优雅关闭所有连接，使用 1001 码，5 秒超时）
  - 修改 `disconnect()` 为异步方法，调用 `websocket.close(code=1000)`
  - 增强 `send_to_thread()` 错误处理和日志
  - 使用 `asyncio.Lock` 保护所有 `active_connections` 访问
  - 添加 `websocket.client_state` 检查避免重复关闭

  **Must NOT do**:
  - 不要删除 `send_to_thread()` 方法（保持向后兼容）
  - 不要添加重试逻辑
  - 不要添加配置选项

  **Recommended Agent Profile**:
  - **Category**: `deep`
    - Reason: 涉及线程安全、异步锁、边缘情况处理，需要深入理解
  - **Skills**: []
    - 不需要特殊技能

  **Parallelization**:
  - **Can Run In Parallel**: NO (依赖 Task 1)
  - **Parallel Group**: Sequential
  - **Blocks**: Task 3, 4, 5
  - **Blocked By**: Task 1

  **References**:
  - `api/server.py:80-110` - 当前 ConnectionManager 实现
  - 用户提供的优化方案代码
  - Metis 审查建议（线程安全、关闭码、超时）

  **Acceptance Criteria**:
  - [ ] 所有 Task 1 的测试通过
  - [ ] `pytest tests/test_connection_manager.py -v` → PASS
  - [ ] `get_loop()` 在无事件循环时抛出 RuntimeError
  - [ ] `send_to_thread_safe()` 可从任意线程调用
  - [ ] `close_all()` 关闭所有连接并清空 `active_connections`

  **QA Scenarios**:
  ```
  Scenario: 测试全部通过
    Tool: Bash (pytest)
    Steps:
      1. pytest tests/test_connection_manager.py -v
      2. 验证输出显示所有测试通过
    Expected Result: "X passed, 0 failed"
    Evidence: .sisyphus/evidence/task-2-tests-pass.txt

  Scenario: 服务器启动成功
    Tool: Bash (timeout + python)
    Steps:
      1. timeout 10 python api/server.py
      2. 验证日志显示 "Application starting up"
    Expected Result: 无启动错误
    Evidence: .sisyphus/evidence/task-2-server-start.txt
  ```

  **Commit**: YES
  - Message: `refactor(websocket): implement thread-safe ConnectionManager with graceful shutdown`
  - Files: `api/server.py`
  - Pre-commit: `pytest tests/test_connection_manager.py`

- [x] 3. **重构 ToolMonitor._emit()**

  **What to do**:
  - 修改 `_emit()` 方法使用 `send_to_thread_safe()` 替代直接访问 `loop`
  - 移除对 `websocket_manager.loop` 的直接依赖
  - 保持现有错误处理模式（try/except/log）

  **Must NOT do**:
  - 不要修改公共 API（report_tool, report_assistant 等）
  - 不要修改消息载荷结构
  - 不要添加重试逻辑

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: 简单的方法修改
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO (依赖 Task 2)
  - **Parallel Group**: Sequential
  - **Blocks**: None
  - **Blocked By**: Task 2

  **References**:
  - `api/monitor.py:45-93` - 当前 `_emit()` 实现
  - 用户提供的优化方案代码

  **Acceptance Criteria**:
  - [ ] `_emit()` 不再直接访问 `websocket_manager.loop`
  - [ ] 使用 `send_to_thread_safe()` 进行跨线程发送
  - [ ] 现有功能保持不变（日志、builtins.runtime 回退）

  **QA Scenarios**:
  ```
  Scenario: ToolMonitor 可正常发送消息
    Tool: Bash (python)
    Steps:
      1. 创建测试脚本验证 monitor.report_tool() 正常工作
      2. 验证无 AttributeError 或 RuntimeError
    Expected Result: 消息成功发送或优雅降级
    Evidence: .sisyphus/evidence/task-3-monitor-works.txt
  ```

  **Commit**: YES
  - Message: `refactor(monitor): use send_to_thread_safe for cross-thread calls`
  - Files: `api/monitor.py`

- [x] 4. **更新 lifespan 函数**

  **What to do**:
  - 移除 `manager.set_loop(loop)` 调用
  - 添加 `monitor.set_websocket_manager(manager)` 到 startup
  - 添加 `await manager.close_all()` 到 shutdown（在 flush_all 之前）
  - 保持现有初始化逻辑（MongoDB 索引等）

  **Must NOT do**:
  - 不要修改现有的 MongoDB 初始化逻辑
  - 不要修改现有的 memory_manager.flush_all() 逻辑
  - 不要添加新的依赖注入

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: 简单的启动/关闭逻辑修改
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO (依赖 Task 2)
  - **Parallel Group**: Sequential
  - **Blocks**: None
  - **Blocked By**: Task 2

  **References**:
  - `api/server.py:57-76` - 当前 lifespan 实现

  **Acceptance Criteria**:
  - [ ] 不再调用 `manager.set_loop()`
  - [ ] shutdown 时调用 `await manager.close_all()`
  - [ ] 应用启动成功，无错误

  **QA Scenarios**:
  ```
  Scenario: 应用启动和关闭正常
    Tool: Bash (timeout + python)
    Steps:
      1. timeout 5 python api/server.py
      2. 观察启动日志
      3. Ctrl+C 触发关闭
      4. 验证日志显示 "Closing X WebSocket connections"
    Expected Result: 启动和关闭都成功
    Evidence: .sisyphus/evidence/task-4-lifespan.txt
  ```

  **Commit**: YES
  - Message: `refactor(lifespan): remove set_loop, add close_all on shutdown`
  - Files: `api/server.py`

- [x] 5. **更新 WebSocket 端点**

  **What to do**:
  - 将 `manager.disconnect(websocket, thread_id)` 改为 `await manager.disconnect(thread_id)`
  - 移除不再需要的 `websocket` 参数
  - 更新所有调用点（exception handlers）

  **Must NOT do**:
  - 不要修改 WebSocket 协议逻辑
  - 不要添加新的消息类型
  - 不要修改现有的心跳/保活逻辑

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: 简单的调用方式更新
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO (依赖 Task 2)
  - **Parallel Group**: Sequential
  - **Blocks**: None
  - **Blocked By**: Task 2

  **References**:
  - `api/server.py:509-522` - 当前 WebSocket 端点

  **Acceptance Criteria**:
  - [ ] 所有 `manager.disconnect()` 调用添加 `await`
  - [ ] 移除 `websocket` 参数
  - [ ] WebSocket 连接/断开正常工作

  **QA Scenarios**:
  ```
  Scenario: WebSocket 连接和断开正常
    Tool: Bash (websocat 或 python websocket client)
    Steps:
      1. 启动服务器
      2. 连接 ws://127.0.0.1:8000/ws/test-thread-1
      3. 发送测试消息
      4. 断开连接
      5. 检查服务器日志显示正常断开
    Expected Result: 连接成功，消息收到，断开正常
    Evidence: .sisyphus/evidence/task-5-websocket.txt
  ```

  **Commit**: YES
  - Message: `fix(websocket): await disconnect in exception handlers`
  - Files: `api/server.py`

---

## Final Verification Wave (MANDATORY)

- [x] F1. **Plan Compliance Audit** — `oracle`
  验证所有 "Must Have" 已实现，所有 "Must NOT Have" 未引入。

- [x] F2. **Code Quality Review** — `unspecified-high`
  运行 `tsc --noEmit` + linter + `pytest`。检查代码质量。

- [x] F3. **Real Manual QA** — `unspecified-high`
  启动服务器，测试 WebSocket 连接/断开/shutdown 行为。

- [x] F4. **Scope Fidelity Check** — `deep`
  验证实现与计划一致，无范围蔓延。

---

## Commit Strategy

- **1**: `test(websocket): add ConnectionManager test suite`
- **2**: `refactor(websocket): implement thread-safe ConnectionManager with graceful shutdown`
- **3**: `refactor(monitor): use send_to_thread_safe for cross-thread calls`
- **4**: `refactor(lifespan): remove set_loop, add close_all on shutdown`
- **5**: `fix(websocket): await disconnect in exception handlers`

---

## Success Criteria

### Verification Commands
```bash
# 运行所有测试
pytest tests/test_connection_manager.py -v

# 启动服务器验证 WebSocket
python api/server.py

# 检查代码质量
ruff check api/server.py api/monitor.py
```

### Final Checklist
- [ ] 所有测试通过
- [ ] WebSocket 连接正常工作
- [ ] Shutdown 时优雅关闭所有连接
- [ ] 无线程安全问题
- [ ] 代码符合项目规范

# Python SDK

本文说明 AgentNet Python SDK 的真实能力与用法。SDK 源码位于
`packages/python-sdk`，实现了 `Client`、`Agent`、`TaskContext`、
`AgentWebSocket`、`SessionStore`、`IdempotencyCache` 六个模块。

## 安装

要求 Python 3.11+，依赖 `httpx` 和 `websockets`：

```powershell
python -m pip install -e packages/python-sdk
```

## 模块总览

| 模块 | 作用 |
| --- | --- |
| `Client` | 同步 REST 客户端。管理智能体、任务、审批、API key。 |
| `Agent` | 智能体运行时。连接 WebSocket 并把任务分发给处理函数。 |
| `TaskContext` | 单个任务的上下文。提供 accept、progress、result、fail 等方法。 |
| `AgentWebSocket` | WebSocket 客户端。自动 ack、心跳、断线重连、会话恢复。 |
| `SessionStore` | 本地会话状态，持久化到 JSON 文件。 |
| `IdempotencyCache` | 按 message_id 去重的内存缓存，重启后仍可去重。 |

## REST 客户端

`Client` 用 API key 认证，凭证走 `Authorization` header：

```python
from agentnet import Client, AgentNetError

client = Client.from_env()  # 读 AGENTNET_BASE_URL 与 AGENTNET_API_KEY

# 创建智能体，返回结果包含 agent_token（只显示一次）
agent = client.create_agent(
    name="my-agent",
    runtime="python",
    inbound_policy="request_approval",
)
print(agent["agent_number"], agent["agent_token"])

# 投递任务（带幂等键，重复投递不会创建重复任务）
task = client.create_task(
    assigned_to="AN-GLOBAL-BB05A89F32-ZQ",
    payload={"message": "hello"},
    idempotency_key="run-001",
)

# 轮询状态与进度
updated = client.get_task(task["task_id"])
progress = client.get_task_progress(task["task_id"])
for entry in progress.get("entries", []):
    print(entry["seq"], entry.get("message"), entry.get("progress_pct"))
```

错误以 `AgentNetError` 抛出，带协议错误码、消息和状态码：

```python
try:
    client.create_task(assigned_to="AN-GLOBAL-NoNumber")
except AgentNetError as exc:
    print(exc.code, exc.message, exc.status_code)
```

`Client` 常用方法：

- 智能体：`create_agent`、`get_agent`、`list_agents`、`rotate_token`、`delete_agent`
- 任务：`create_task`、`get_task`、`list_tasks`、`get_task_messages`、`get_task_progress`
- 审批：`list_approvals`、`accept_approval`、`reject_approval`
- API key：`list_api_keys`、`create_api_key`、`revoke_api_key`

## 智能体运行时

`Agent` 负责长连接运行。环境变量：

- `AGENTNET_BASE_URL`：中继地址，默认 `http://localhost:8000`
- `AGENTNET_WS_URL`：WebSocket 地址，默认由 base URL 推导
- `AGENTNET_AGENT_TOKEN`：智能体 token，必须以 `agt_sk_` 开头
- `AGENTNET_SESSION_FILE`：会话文件路径，默认 `./agentnet_session.json`

```python
from agentnet import Agent, TaskContext

agent = Agent.from_env()

@agent.task_handler
async def handle_echo(ctx: TaskContext):
    await ctx.accept()
    await ctx.progress("echoing", progress_pct=50)
    await ctx.result({"echo": ctx.payload})

agent.run()  # 阻塞运行
```

注意：token 通过 `Authorization` header 发送，不放在 URL 参数里。

## TaskContext 生命周期

处理函数收到 `TaskContext` 后，可以调用：

- `await ctx.accept()`：接受任务，状态进入 running
- `await ctx.progress("Running", progress_pct=50)`：上报进度
- `await ctx.result({"output": "done"})`：上报成功结果
- `await ctx.fail("Something went wrong")`：上报失败
- `await ctx.request_approval("shell", "rm -rf /tmp/x", risk_level="high")`：
  请求人工审批高风险动作，任务进入 awaiting_approval

如果处理函数抛异常且任务没有进入终态，SDK 会自动上报 `task.failed`。

默认行为说明：

- 收到 `connection.request` 时，SDK 默认自动拒绝，回发
  `connection.rejected`。
- 收到 `approval.request` 时，SDK 只记录日志，不自动同意。需要自动
  处理的场景请直接扩展 `AgentWebSocket` 的处理器。

## 连接可靠性

`AgentWebSocket` 内置：

- 自动 ack：收到消息后回发 `ack`
- 心跳：每 15 秒发送 `presence.heartbeat`
- 任务心跳：每 20 秒发送 `task.heartbeat`
- 断线重连：指数退避，从 0.5 秒到 60 秒，带 30% 抖动
- 会话恢复：重连时发送 `session.resume`，并重放未确认的消息
- 消息去重：`IdempotencyCache` 按 message_id 去重，容量 10000 条，
  TTL 3600 秒，去重记录写入会话文件，重启后仍然有效

会话文件保存 `session_id`、`last_message_id` 和运行中的任务列表，
`Agent` 启动时会用它们恢复状态。

## 示例

仓库提供两个可运行示例：

- `packages/python-sdk/examples/echo_agent.py`：回声智能体，收到任务后
  回传 payload
- `packages/python-sdk/examples/send_task.py`：创建任务并轮询结果

运行方式见 `docs/sdk-python-quickstart.md`。

## 与协议的关系

SDK 内部使用 ARP v0.1 信封。`version` 取 `arp-0.1`，消息类型见
`MessageType`（如 `task.request`、`task.progress`），任务状态见
`TaskStatus`。协议规范见 `docs/protocol.md`，JSON Schema 见
`packages/protocol/schemas`。

E2EE 字段在协议层预留但未实现。设置 `security.mode = e2ee` 会被业务
校验拒绝，返回 `E2EE_NOT_IMPLEMENTED`。

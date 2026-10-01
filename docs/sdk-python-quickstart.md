# Python SDK 快速上手

本文用最小路径跑通 AgentNet Python SDK：创建智能体、投递任务、
接收任务并回传结果。

## 1. 安装

要求 Python 3.11+：

```powershell
python -m pip install -e packages/python-sdk
```

在仓库根目录执行。SDK 依赖 `httpx` 和 `websockets`，安装时会自动
拉取。

## 2. 启动本地中继

```powershell
docker compose -f infra/docker-compose.yml up -d postgres redis
cd apps/api
alembic upgrade head
uvicorn app.main:app --reload
cd ../..
```

## 3. 拿到凭证

需要两个凭证：

- API key（`ak_` 开头）：用 `Client` 走 REST
- 智能体 token（`agt_sk_` 开头）：用 `Agent` 走 WebSocket

用 CLI 创建用户和智能体最省事：

```powershell
python -m pip install -e packages/cli
agentnet login --base-url http://localhost:8000
agentnet agent create --name echo --runtime python
```

`agent create` 的输出包含 `agent_number` 和 `agent_token`。
token 只显示一次，请立即保存。

也可以走 REST，见 `docs/api-examples.md`。

## 4. 发送任务（REST）

设好环境变量：

```powershell
set AGENTNET_BASE_URL=http://localhost:8000
set AGENTNET_API_KEY=ak_REPLACE_ME
```

然后运行示例脚本：

```powershell
python packages/python-sdk/examples/send_task.py AN-GLOBAL-BB05A89F32-ZQ
```

脚本会创建任务、轮询状态、打印结果和进度历史。把参数换成第 3 步
拿到的真实 Agent Number。

等价代码：

```python
from agentnet import Client

client = Client.from_env()
task = client.create_task(
    assigned_to="AN-GLOBAL-BB05A89F32-ZQ",
    payload={"message": "hello"},
    idempotency_key="run-001",
)
print(task["task_id"], task["status"])
```

## 5. 接收任务（WebSocket）

设好智能体 token：

```powershell
set AGENTNET_AGENT_TOKEN=agt_sk_REPLACE_ME
```

运行回声智能体示例：

```powershell
python packages/python-sdk/examples/echo_agent.py
```

收到任务后它会回传 payload。等价代码：

```python
from agentnet import Agent, TaskContext

agent = Agent.from_env()

@agent.task_handler
async def echo(ctx: TaskContext):
    await ctx.accept()
    await ctx.progress("Echo agent received task", progress_pct=10)
    await ctx.result({"echo": ctx.payload})

agent.run()
```

第 4 步发送的任务会投递到这里，状态依次变成 accepted、running、
completed。

## 6. 下一步

- 完整 API：`docs/sdk-python.md`
- 连接恢复、心跳、幂等的参数说明：同上
- 协议信封字段：`docs/protocol.md`
- REST 端点契约：API Reference（控制台文档站 `/docs/api-reference`）

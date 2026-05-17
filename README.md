# AgentNet / Agent Relay Platform

AgentNet 是一个中心化 Agent Relay Platform，用来让不同用户、不同机器、不同框架里的 AI Agent 能够安全、可审计、可恢复地互相通信。

它不是一个聊天应用，也不是一个去中心化网络。它更像是给 Agent 之间建立的一层“任务中继网络”：每个 Agent 拥有稳定但不可枚举的 Agent Number，用户可以通过 API、SDK 或 CLI 向目标 Agent 投递任务，平台负责认证、路由、离线队列、状态管理、审批和审计。

## 适合谁使用

AgentNet 适合这些场景：

- 你有多个 Agent 分布在不同机器上，希望它们能互相发任务。
- 你希望 Agent 不直接暴露公网地址，而是统一接入一个 relay。
- 你需要离线消息、任务状态、重试、幂等和审计。
- 你需要 Human-in-the-loop 审批，避免高风险操作自动执行。
- 你希望把 OpenClaw、MCP 或未来其他 Agent 框架接入同一套协议。

AgentNet 当前不做这些事情：

- 不做区块链、gas、链上结算。
- 不做完整 E2EE。协议字段已经预留，但业务上不会假装已经实现。
- 不做多组织企业权限系统。
- 不做 Dashboard。
- 不做生产级公网托管方案。当前是 MVP 代码库，可以作为本地开发、验证、专利说明和后续产品化基础。

## 核心能力

### Agent Number

每个 Agent 创建后会获得一个 `agent_number`。它用于跨用户寻址，而不是直接暴露数据库 ID。

Agent Number 的目标是：

- 稳定：Agent 生命周期内保持不变。
- 不可枚举：避免简单递增 ID 被批量猜测。
- 可扩展：可承载 region、namespace、随机后缀和校验位。

### 任务投递

用户可以向目标 Agent Number 创建任务：

- REST API: `POST /v1/tasks`
- Python SDK: `Client.create_task(...)`
- CLI: `agentnet task send <agent_number>`

任务会进入数据库，生成 `task_id` 和 `message_id`。如果目标 Agent 在线，平台会通过 WebSocket 投递；如果目标 Agent 离线，平台会进入 Redis pending queue，等 Agent 重新连接后补发。

### WebSocket Agent Runtime

Agent 使用 agent token 连接：

```text
Authorization: Bearer agt_sk_...
```

SDK 默认会：

- 维护 WebSocket 连接。
- 自动发送 heartbeat。
- 自动 ack 收到的消息。
- 自动 session.resume。
- 维护本地 session store。
- 基于 message_id 做幂等去重。

### Human-in-the-loop Approval

高风险动作可以进入审批流程：

- Agent 请求 approval。
- 平台创建 approval 记录。
- 用户通过 CLI 或 API 查看审批。
- 用户 accept 或 reject。
- 任务继续运行、拒绝或超时。

CLI 会对高风险审批显示更醒目的提示，并要求确认。

### 安全和审计

AgentNet 当前已经实现：

- API key 哈希存储。
- Agent token 哈希存储和轮换。
- REST 支持 `Authorization: Bearer <api_key>` 和 `X-API-Key`。
- WebSocket 支持 `Authorization: Bearer <agent_token>`，兼容 query token。
- 跨用户 task / message / progress / approval 读取隔离。
- Rate limit fail-closed。限流依赖不可用时返回错误，不静默放行。
- Audit log 记录 task、delivery、approval、connection 等关键事件。
- 日志和响应中避免直接暴露敏感 token。

## 仓库结构

```text
.
├── apps
│   └── api                  FastAPI Relay API
├── packages
│   ├── python-sdk           Python SDK 和 Agent runtime
│   ├── cli                  agentnet 命令行工具
│   └── protocol             JSON Schema 协议文件
├── adapters
│   ├── base                 AdapterInterface 基础接口
│   ├── openclaw             OpenClaw adapter
│   └── mcp                  MCP adapter 占位
├── infra                    Docker Compose 本地和生产模板
├── docs                     主题文档
├── reports                  Phase 验收报告
├── .github/workflows        CI/CD 工作流
├── plan.md                  Phase 0-10 规划和验收标准
├── planv2.md                Phase 11 生产化增强计划
└── DEVELOPER_README.md      开发者维护手册
```

## 快速开始

### 1. 准备环境

推荐：

- Python 3.11+
- Docker Desktop
- PowerShell 或 Bash

### 2. 启动 PostgreSQL、Redis 和 API

在仓库根目录执行：

```powershell
docker compose -f infra/docker-compose.yml -f infra/docker-compose.dev.yml up --build
```

如果只想使用基础 compose：

```powershell
docker compose -f infra/docker-compose.yml up --build
```

API 默认地址：

```text
http://localhost:8000
```

健康检查：

```powershell
curl http://localhost:8000/healthz
```

期望响应：

```json
{"status":"ok"}
```

### 3. 安装本地 SDK 和 CLI

另开一个终端，在仓库根目录执行：

```powershell
python -m pip install -e packages/python-sdk
python -m pip install -e packages/cli
```

如果你要运行 API 测试或本地 API：

```powershell
python -m pip install -e "apps/api[test]"
```

如果你要使用 OpenClaw adapter：

```powershell
python -m pip install -e adapters/base
python -m pip install -e adapters/openclaw
```

### 4. 注册用户并获得 API key

```powershell
curl -X POST http://localhost:8000/v1/auth/register `
  -H "Content-Type: application/json" `
  -d "{\"username\":\"alice\",\"key_name\":\"local-dev\"}"
```

响应里会包含 `api_key`。请保存它。API key 只应该在创建时明文出现一次。

示例：

```json
{
  "user_id": "9b7f...",
  "username": "alice",
  "api_key": "ak_..."
}
```

### 5. 配置 CLI

```powershell
agentnet login --base-url http://localhost:8000
```

CLI 会提示输入 API key。

配置文件默认保存在：

```text
~/.agentnet/config.json
```

API key 轮换：

```powershell
agentnet key create --name rotated-local
agentnet key list
agentnet key revoke <old_api_key_id>
```

### 6. 创建 Agent

```powershell
agentnet agent create `
  --name echo-agent `
  --runtime python `
  --capability echo `
  --inbound-policy public
```

创建成功后你会看到：

- `agent_id`
- `agent_number`
- `agent_token`

请立即保存 `agent_token`。它用于 Agent WebSocket 连接，旧 token 轮换后会失效。

### 7. 启动一个 Python Agent

设置环境变量：

```powershell
$env:AGENTNET_BASE_URL="http://localhost:8000"
$env:AGENTNET_AGENT_TOKEN="agt_sk_..."
```

运行示例 Echo Agent：

```powershell
python packages/python-sdk/examples/echo_agent.py
```

### 8. 向 Agent 发送任务

使用 CLI：

```powershell
agentnet task send AN-GLOBAL-... --message "hello agent"
```

如果你有多个发送方 Agent，可以指定发送方：

```powershell
agentnet task send AN-GLOBAL-TARGET `
  --from-agent-number AN-GLOBAL-SENDER `
  --payload "{\"action\":\"echo\",\"text\":\"hello\"}" `
  --idempotency-key demo-001
```

使用 Python SDK：

```python
from agentnet import Client

client = Client(base_url="http://localhost:8000", api_key="ak_...")

task = client.create_task(
    assigned_to="AN-GLOBAL-TARGET",
    from_agent_number="AN-GLOBAL-SENDER",
    payload={"action": "echo", "text": "hello"},
    idempotency_key="demo-001",
)

print(task["task_id"], task["status"])
```

查看任务：

```powershell
agentnet task get <task_id>
agentnet task logs <task_id>
agentnet task list
```

## API 认证

REST API 支持两种认证头：

```text
Authorization: Bearer ak_...
```

或：

```text
X-API-Key: ak_...
```

推荐使用 `Authorization: Bearer`，因为 SDK 默认使用它。

WebSocket Agent 认证：

```text
Authorization: Bearer agt_sk_...
```

兼容模式下也支持 query token：

```text
ws://localhost:8000/v1/ws?token=agt_sk_...&session_id=...
```

生产或准生产环境中不建议把 token 放在 URL 中，因为 URL 可能进入访问日志。

## 常用 REST API

| 功能 | 方法 | 路径 |
|---|---:|---|
| 健康检查 | GET | `/healthz` |
| 注册用户 | POST | `/v1/auth/register` |
| 创建 Agent | POST | `/v1/agents` |
| 列出 Agent | GET | `/v1/agents` |
| 获取 Agent | GET | `/v1/agents/{agent_id}` |
| 轮换 Agent token | POST | `/v1/agents/{agent_id}/rotate-token` |
| 删除 Agent | DELETE | `/v1/agents/{agent_id}` |
| 创建任务 | POST | `/v1/tasks` |
| 列出任务 | GET | `/v1/tasks` |
| 获取任务 | GET | `/v1/tasks/{task_id}` |
| 查看任务消息 | GET | `/v1/tasks/{task_id}/messages` |
| 查看任务进度 | GET | `/v1/tasks/{task_id}/progress` |
| 请求连接 | POST | `/v1/connections/request` |
| 接受连接 | POST | `/v1/connections/{connection_id}/accept` |
| 拒绝连接 | POST | `/v1/connections/{connection_id}/reject` |
| 列出审批 | GET | `/v1/approvals` |
| 接受审批 | POST | `/v1/approvals/{approval_id}/accept` |
| 拒绝审批 | POST | `/v1/approvals/{approval_id}/reject` |
| Agent WebSocket | WS | `/v1/ws` |

## 任务生命周期

典型状态流：

```text
created -> delivered -> accepted -> running -> completed
```

失败或中断路径：

```text
created/running -> expired
running -> awaiting_approval -> running
running -> awaiting_approval -> rejected
running -> failed
running -> cancelled
```

说明：

- `created`: 任务已经创建。
- `delivered`: 任务请求已投递给在线 Agent。
- `accepted`: Agent 已接受任务。
- `running`: Agent 正在执行，lease 生效。
- `awaiting_approval`: 等待用户审批。
- `completed`: 执行完成。
- `failed`: 执行失败。
- `expired`: lease 或最大运行时间超时。
- `rejected`: 用户拒绝审批。
- `cancelled`: 任务被取消。

## 幂等性

创建任务时可以传入 `idempotency_key`：

```json
{
  "assigned_to": "AN-GLOBAL-TARGET",
  "from_agent_number": "AN-GLOBAL-SENDER",
  "idempotency_key": "job-2026-05-15-001",
  "payload": {"action": "echo"}
}
```

幂等范围是：

```text
(created_by, assigned_to, idempotency_key)
```

这意味着：

- 同一个发送 Agent 向同一个目标 Agent 使用同一个 key，会返回同一个 task。
- 同一个 key 发给不同目标 Agent，不会错误复用。
- 不同发送 Agent 使用同一个 key，也不会互相影响。

## 离线队列和恢复

当目标 Agent 离线时，任务消息会进入 Redis pending queue。

当 Agent 重新连接时：

- 服务端会根据 Agent ID 投递离线期间积压的消息。
- SDK 会发送 `session.resume`。
- SDK 会携带本地保存的 `session_id` 和 `last_message_id`。
- 服务端会返回 `session.resume_result`。
- SDK 会自动 ack 非 ack、非 error、非 heartbeat 的业务消息。

本地 session 文件默认是：

```text
agentnet_session.json
```

可以通过环境变量覆盖：

```powershell
$env:AGENTNET_SESSION_FILE="C:\agentnet\echo-agent-session.json"
```

## Human-in-the-loop 审批

列出审批：

```powershell
agentnet approve list
agentnet approve list --status pending
```

接受审批：

```powershell
agentnet approve accept <approval_id>
```

拒绝审批：

```powershell
agentnet approve reject <approval_id>
```

跳过确认：

```powershell
agentnet approve accept <approval_id> --force
```

高风险审批会显示醒目的确认提示。除非你明确知道 Agent 要做什么，否则不要用 `--force`。

## OpenClaw Adapter

OpenClaw adapter 的目标是把 AgentNet task 转换成本地 OpenClaw CLI 执行。

已实现的安全原则：

- 生产模式必须存在真实 OpenClaw CLI，不使用 mock fallback。
- 工作目录必须通过 allow path / deny path 校验。
- 检测路径穿越。
- 子进程环境变量使用最小化策略。
- 敏感环境变量会被剥离。
- 输出超过限制会截断。
- 高风险命令可以进入 approval 流程。

配置示例见：

```text
adapters/openclaw/examples/openclaw-agent.yaml
```

更多说明见：

```text
docs/openclaw-adapter.md
```

## 配置项

API 读取 `.env` 和环境变量。

| 变量 | 默认值 | 说明 |
|---|---|---|
| `AGENTNET_ENV` | `development` | 运行环境 |
| `LOG_LEVEL` | `INFO` | 日志级别 |
| `DATABASE_URL` | `postgresql+asyncpg://agentnet:agentnet@localhost:5432/agentnet` | Postgres 连接 |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis 连接 |
| `MAX_PAYLOAD_BYTES` | `1048576` | WebSocket payload 限制 |
| `WS_HEARTBEAT_INTERVAL_S` | `15` | 心跳间隔 |
| `WS_HEARTBEAT_TIMEOUT_S` | `45` | 心跳超时 |
| `WS_MAX_CONNECTIONS_PER_AGENT` | `3` | 单 Agent 最大连接数 |
| `RATE_LIMIT_WINDOW_S` | `60` | 限流窗口 |
| `RATE_LIMIT_GLOBAL_MAX` | `1000` | 全局请求限制 |
| `RATE_LIMIT_USER_MAX` | `300` | 单用户请求限制 |
| `RATE_LIMIT_AGENT_MAX` | `200` | 单 Agent 请求限制 |
| `RATE_LIMIT_IP_MAX` | `100` | 单 IP 请求限制 |
| `TASK_MAX_RUNTIME_S` | `600` | 任务最大运行时间 |
| `TASK_LEASE_DURATION_S` | `60` | task lease 时长 |
| `TIMEOUT_WORKER_INTERVAL_S` | `30` | timeout worker 间隔 |

SDK/CLI 常用环境变量：

| 变量 | 默认值 | 说明 |
|---|---|---|
| `AGENTNET_BASE_URL` | `http://localhost:8000` | Relay API 地址 |
| `AGENTNET_API_KEY` | 空 | REST API key |
| `AGENTNET_AGENT_TOKEN` | 空 | Agent WebSocket token |
| `AGENTNET_SESSION_FILE` | `agentnet_session.json` | SDK session store 文件 |

## 测试

从仓库根目录运行完整测试：

```powershell
python -m pytest -q
```

按模块运行：

```powershell
python -m pytest apps/api -q
python -m pytest packages/python-sdk -q
python -m pytest packages/cli -q
python -m pytest adapters/openclaw -q
```

当前根级测试入口已经打通，会覆盖 API、SDK、CLI、OpenClaw adapter。

## 常见问题

### Docker 连接失败

如果看到类似 Docker pipe 或 daemon 连接错误，请确认 Docker Desktop 已启动。

### API 返回 503 Rate limiter unavailable

AgentNet 的限流是 fail-closed 策略。如果 Redis 不可用，API 不会静默放行请求。请检查：

```powershell
docker compose -f infra/docker-compose.yml ps
```

### WebSocket 认证失败

确认你使用的是 Agent token，而不是 API key：

```text
agt_sk_...
```

REST API 使用：

```text
ak_...
```

### 任务一直 pending

常见原因：

- 目标 Agent 没有连接。
- Agent token 错误。
- Agent 连接到错误 base URL。
- Redis 不可用，离线队列无法正常工作。

### 幂等请求返回旧 task

这是预期行为。相同发送 Agent、相同目标 Agent、相同 `idempotency_key` 会返回同一个 task。

如果你希望创建新 task，请换一个 `idempotency_key` 或不传该字段。

## 文档索引

- 用户快速开始: `docs/quickstart.md`
- 架构说明: `docs/architecture.md`
- 协议说明: `docs/protocol.md`
- CI/CD: `docs/ci-cd.md`
- 生产部署: `docs/production-deploy.md`
- 生产检查表: `docs/production-checklist.md`
- OpenAPI: `docs/openapi.md`
- API 示例: `docs/api-examples.md`
- 数据库备份恢复: `docs/backup-restore.md`
- Secret 轮换: `docs/secrets-rotation.md`
- Secret 泄露响应: `docs/incident-secret-leak.md`
- 观测性和告警: `docs/observability.md`
- CLI: `docs/cli.md`
- Python SDK: `docs/sdk-python.md`
- OpenClaw Adapter: `docs/openclaw-adapter.md`
- 安全模型: `docs/security-model.md`
- 开发者维护手册: `DEVELOPER_README.md`

## 当前成熟度

当前项目已经覆盖 Agent Registry、WebSocket Presence、Task/Message Storage、Relay Routing、Connection Policy、Approval、Python SDK、CLI、OpenClaw Adapter、Hardening，以及 Phase 11 的 CI/CD、生产配置模板、OpenAPI 导出、真实 WebSocket E2E、备份恢复、Secret 轮换流程和 Prometheus/Grafana 观测模板。

它适合继续向“可试点的产品化原型”推进，但仍不是无需运维投入即可公网商用的稳定版本。真实公网试用前，建议继续强化：

- 专用 Redis/Postgres exporter。
- 更严格的权限模型。
- 压力测试和故障注入。
- TLS 自动化和正式发布流程。

# AgentNet - Agent Relay Platform

<p align="center">
  <a href="#核心能力"><strong>核心能力</strong></a> ·
  <a href="#快速开始"><strong>快速开始</strong></a> ·
  <a href="#架构总览"><strong>架构总览</strong></a> ·
  <a href="#api-参考"><strong>API 参考</strong></a> ·
  <a href="#测试状态"><strong>测试状态</strong></a> ·
  <a href="#路线图"><strong>路线图</strong></a>
</p>

AgentNet 是一个中心化的 AI Agent 中继平台，用于让不同用户、不同机器、不同框架中的 Agent 能够安全、可审计、可恢复地互相通信。

它不是聊天应用，不是去中心化网络，也不是链上结算系统。AgentNet 的定位是一层面向 Agent 的任务中继网络：为 Agent 分配稳定但不可枚举的 Agent Number，并提供 WebSocket 长连接、异步任务路由、离线消息队列、Human-in-the-loop 审批、安全审计和 Python SDK / CLI 自动化闭环。

## 一句话说明

AgentNet 可以理解为 Agent 之间的消息队列、审批网关和审计中心。用户通过 REST API、Python SDK 或 CLI 向目标 Agent Number 投递任务；平台负责认证、策略校验、幂等、路由、状态跟踪、断线恢复和审计记录。

## 适用场景

| 场景 | 说明 |
| --- | --- |
| 多机 Agent 通信 | 多个 Agent 分布在不同机器上，需要互相投递任务 |
| 安全隔离 | Agent 不直接暴露公网地址，统一接入 Relay API |
| 离线消息 | 需要消息排队、断线重连、session resume 和 ack |
| Human-in-the-loop | 高风险任务需要人工审批，避免自动执行危险操作 |
| 多框架适配 | 接入 OpenClaw、MCP 或未来其他 Agent 框架 |
| 审计合规 | 记录 task 创建、投递、执行、审批和结果 |

## 当前不做

- 不做区块链、gas 或链上结算。
- 不做完整 E2EE。协议字段已经预留，但不会把预留能力描述为已实现。
- 不做多组织企业权限系统。
- 当前主线不包含 Dashboard；Dashboard 已单独规划在 [web.md](web.md)。
- 不提供无需运维投入即可公网商用的托管方案。

## 架构总览

<p align="center">
  <img src="docs/figures/agentnet_nature_flow.svg" width="90%" alt="AgentNet 系统架构图">
</p>

完整架构图位于 [docs/figures](docs/figures)，包含可编辑的 Draw.io 源文件、SVG/PDF 矢量图和 PNG 图像。

| 层级 | 职责 |
| --- | --- |
| Identity | 用户注册、API key 认证、rate limit、Agent Number 分配 |
| Policy and Delivery | 策略门控、幂等去重、任务/消息存储、路由、结果存储 |
| Execution | 离线队列、WebSocket 投递、SDK runtime、OpenClaw Adapter、真实 CLI 执行 |
| Operations | PostgreSQL 持久化、Redis presence/queue、可观测性、备份恢复、密钥管理 |

## 技术栈

| 组件 | 技术 |
| --- | --- |
| API | FastAPI + Uvicorn, Python 3.11+ |
| 数据库 | PostgreSQL 16 + asyncpg |
| 缓存/队列 | Redis 7 |
| 协议 | JSON Schema + WebSocket + Agent Relay Protocol |
| ORM | SQLAlchemy 2.0 async |
| 测试 | pytest + asyncio + httpx + websockets |
| 部署 | Docker Compose |
| SDK | Python REST client + WebSocket runtime |
| CLI | Click-based `agentnet` 命令 |
| Adapter | OpenClaw 已实现，MCP 预留 |

## 快速开始

### 1. 环境要求

- Python 3.11+
- Docker Desktop
- PowerShell 或 Bash

### 2. 启动基础设施

```bash
docker compose -f infra/docker-compose.yml up --build -d
```

API 默认运行在：

```text
http://localhost:8000
```

健康检查：

```bash
curl http://localhost:8000/healthz
```

期望响应：

```json
{"status":"ok"}
```

### 3. 注册用户并获取 API key

```bash
curl -X POST http://localhost:8000/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username":"alice","key_name":"local-dev"}'
```

响应示例：

```json
{
  "user_id": "9b7f...",
  "username": "alice",
  "api_key": "ak_..."
}
```

`api_key` 只在创建时明文返回一次，请妥善保存。后续系统只保存 hash。

### 4. 创建 Agent

```bash
curl -X POST http://localhost:8000/v1/agents \
  -H "Authorization: Bearer ak_..." \
  -H "Content-Type: application/json" \
  -d '{"name":"my-agent","runtime":"python","inbound_policy":"public"}'
```

响应会包含：

- `agent_id`
- `agent_number`
- `agent_token`

`agent_number` 用于跨 Agent 寻址；`agent_token` 用于 WebSocket 连接。

### 5. 连接 Agent WebSocket

```python
from agentnet import AgentNetWebSocket

ws = AgentNetWebSocket(
    base_url="http://localhost:8000",
    token="agt_sk_...",
    session_id="my-session-1",
)
ws.connect()
```

SDK 会自动处理 heartbeat、ack 和 session.resume。

### 6. 发送任务

Python SDK：

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

CLI：

```bash
agentnet task send AN-GLOBAL-TARGET --message "hello agent"
```

curl：

```bash
curl -X POST http://localhost:8000/v1/tasks \
  -H "Authorization: Bearer ak_..." \
  -H "Content-Type: application/json" \
  -d '{
    "assigned_to": "AN-GLOBAL-TARGET",
    "from_agent_number": "AN-GLOBAL-SENDER",
    "payload": {"action": "echo"},
    "idempotency_key": "demo-001"
  }'
```

### 7. 运行测试

```bash
python -m pytest -q
```

按模块运行：

```bash
python -m pytest apps/api -q
python -m pytest packages/python-sdk -q
python -m pytest packages/cli -q
python -m pytest adapters/openclaw -q
```

真实 OpenClaw 跨机器 E2E 测试报告见 [tests/real_openclaw/TEST_REPORT.md](tests/real_openclaw/TEST_REPORT.md)。

## 核心能力

### Agent Number

每个 Agent 创建后会获得一个 `agent_number`，例如：

```text
AN-GLOBAL-BB05A89F32-ZQ
```

Agent Number 用于跨用户寻址，而不是直接暴露数据库 ID。

- 稳定：Agent 生命周期内保持不变。
- 不可枚举：避免递增 ID 被批量猜测。
- 可扩展：可承载 region、namespace、随机后缀和校验位。

### 任务生命周期

主路径：

```text
created -> delivered -> accepted -> running -> completed
```

失败或中断路径：

```text
created/running -> expired
running -> awaiting_approval -> running
running -> awaiting_approval -> rejected
running -> failed / cancelled
```

| 状态 | 说明 |
| --- | --- |
| `created` | 任务已创建 |
| `delivered` | 请求已投递给在线 Agent |
| `accepted` | Agent 已接受 |
| `running` | Agent 正在执行，lease 生效 |
| `awaiting_approval` | 等待用户审批 |
| `completed` | 执行完成 |
| `failed` | 执行失败 |
| `expired` | lease 或最大运行时间超时 |
| `rejected` | 用户拒绝审批 |
| `cancelled` | 任务被取消 |

### WebSocket Agent Runtime

Agent 使用 agent token 连接：

```text
Authorization: Bearer agt_sk_...
```

SDK 自动处理：

- 维护 WebSocket 长连接。
- 自动发送 heartbeat。
- 自动 ack 收到的消息。
- 自动 session.resume。
- 本地 session store 持久化。
- 基于 `message_id` 幂等去重。

### Human-in-the-loop 审批

```bash
agentnet approve list --status pending
agentnet approve accept <approval_id>
agentnet approve reject <approval_id>
```

高风险动作可以进入审批流程，由用户确认后继续执行或拒绝。

### 安全和审计

- API key 和 Agent token 均以 hash 存储。
- REST API 支持 `Authorization: Bearer <api_key>` 和 `X-API-Key`。
- WebSocket 使用 Agent token 认证。
- 跨用户 task、message、progress、approval 读取隔离。
- Rate limit 使用 fail-closed 策略，限流依赖不可用时返回错误，不静默放行。
- Audit log 记录 task、delivery、approval、connection 等关键事件。
- 日志和响应避免暴露敏感 token、secret 或用户敏感 payload。

### 离线队列和恢复

目标 Agent 离线时，消息进入 Redis pending queue。Agent 重连后：

1. 服务端按 Agent ID 投递离线积压消息。
2. SDK 发送 `session.resume` 和 `last_message_id`。
3. 服务端返回 `session.resume_result`。
4. SDK 自动 ack 未确认消息。

## API 参考

| 功能 | 方法 | 路径 |
| --- | --- | --- |
| 健康检查 | `GET` | `/healthz` |
| 注册用户 | `POST` | `/v1/auth/register` |
| 创建 API key | `POST` | `/v1/auth/api-keys` |
| 列出 API keys | `GET` | `/v1/auth/api-keys` |
| 撤销 API key | `POST` | `/v1/auth/api-keys/{id}/revoke` |
| 创建 Agent | `POST` | `/v1/agents` |
| 列出 Agents | `GET` | `/v1/agents` |
| 获取 Agent | `GET` | `/v1/agents/{id}` |
| 轮换 Agent token | `POST` | `/v1/agents/{id}/rotate-token` |
| 删除 Agent | `DELETE` | `/v1/agents/{id}` |
| 创建任务 | `POST` | `/v1/tasks` |
| 列出任务 | `GET` | `/v1/tasks` |
| 获取任务 | `GET` | `/v1/tasks/{id}` |
| 任务消息 | `GET` | `/v1/tasks/{id}/messages` |
| 任务进度 | `GET` | `/v1/tasks/{id}/progress` |
| 连接请求 | `POST` | `/v1/connections/request` |
| 审批列表 | `GET` | `/v1/approvals` |
| 接受审批 | `POST` | `/v1/approvals/{id}/accept` |
| 拒绝审批 | `POST` | `/v1/approvals/{id}/reject` |
| Agent WebSocket | `WS` | `/v1/ws` |

更完整的接口说明见 [docs/openapi.md](docs/openapi.md) 和 [docs/api-examples.md](docs/api-examples.md)。

## 测试状态

### E2E 测试

| 分类 | 通过 | 总数 |
| --- | ---: | ---: |
| 失败路径 | 5 | 5 |
| 安全边界 | 3 | 3 |
| 稳定性 | 3 | 3 |
| 边缘用例 | 3 | 3 |
| 审批链路 | 2 | 2 |
| 离线去重 | 1 | 1 |
| 模型失败收敛 | 3 | 3 |
| 总计 | 20 | 20 |

### 压力测试

| 测试 | 结果 |
| --- | --- |
| 15 Agent 并发 WebSocket + 连接搅动 | 8,114 heartbeats, 0 drops, P99 = 5.4ms |
| 30 分钟长稳测试 | 900/900 cycles, 0 drops, avg 2ms |
| 10 Agent 并发 WebSocket 压测 | 1,500 heartbeats, 0 drops, P99 = 4ms |
| 纯写压力，1000 tasks | 1000/1000, 0 errors, DB delta 精确匹配 |

### 运维演练

| 演练 | 结果 |
| --- | --- |
| 备份、停机、恢复、healthz | PG dump 1.4MB，完整性验证通过 |
| 测试数据清理 | 清理 1,479 agents 和 834 tasks |

完整测试报告见 [tests/real_openclaw/TEST_REPORT.md](tests/real_openclaw/TEST_REPORT.md)。

## 仓库结构

```text
.
├── apps/
│   └── api/                     FastAPI Relay API
│       ├── app/
│       │   ├── routers/         HTTP route handlers
│       │   ├── services/        Business logic
│       │   ├── models/          SQLAlchemy ORM models
│       │   ├── protocol/        ARP constants and validators
│       │   ├── websocket/       WebSocket connection manager
│       │   └── workers/         Background asyncio tasks
│       └── tests/               Phase-based test files
├── packages/
│   ├── python-sdk/              Python client SDK
│   ├── cli/                     agentnet CLI
│   └── protocol/                JSON Schema protocol files
├── adapters/
│   ├── base/                    AdapterInterface
│   ├── openclaw/                OpenClaw adapter
│   └── mcp/                     MCP adapter placeholder
├── infra/                       Docker Compose for dev and prod
├── docs/                        Architecture, protocol, security docs
├── scripts/                     Backup, restore, cleanup utilities
└── tests/real_openclaw/         Cross-machine E2E tests
```

## 配置

所有配置通过环境变量或 `.env` 管理。

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `DATABASE_URL` | `postgresql+asyncpg://agentnet:agentnet@localhost:5432/agentnet` | PostgreSQL 连接 |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis 连接 |
| `WS_HEARTBEAT_INTERVAL_S` | `15` | 心跳间隔 |
| `WS_HEARTBEAT_TIMEOUT_S` | `45` | 心跳超时 |
| `WS_MAX_CONNECTIONS_PER_AGENT` | `3` | 单 Agent 最大连接数 |
| `RATE_LIMIT_WINDOW_S` | `60` | 限流窗口 |
| `RATE_LIMIT_IP_MAX` | `100` | 单 IP 限流 |
| `TASK_MAX_RUNTIME_S` | `600` | 任务最大运行时间 |
| `TASK_LEASE_DURATION_S` | `60` | Task lease 时长 |

完整配置见 [apps/api/app/config.py](apps/api/app/config.py)。

## 文档索引

| 文档 | 说明 |
| --- | --- |
| [docs/quickstart.md](docs/quickstart.md) | 用户快速开始 |
| [docs/architecture.md](docs/architecture.md) | 架构设计说明 |
| [docs/protocol.md](docs/protocol.md) | ARP 协议规范 |
| [docs/security-model.md](docs/security-model.md) | 安全模型 |
| [docs/sdk-python.md](docs/sdk-python.md) | Python SDK 使用 |
| [docs/cli.md](docs/cli.md) | CLI 使用 |
| [docs/openclaw-adapter.md](docs/openclaw-adapter.md) | OpenClaw Adapter |
| [docs/production-deploy.md](docs/production-deploy.md) | 生产部署指南 |
| [docs/production-checklist.md](docs/production-checklist.md) | 生产上线检查表 |
| [docs/backup-restore.md](docs/backup-restore.md) | 数据库备份恢复 |
| [docs/secrets-rotation.md](docs/secrets-rotation.md) | 密钥轮换流程 |
| [docs/observability.md](docs/observability.md) | 观测性和告警 |
| [docs/openapi.md](docs/openapi.md) | OpenAPI 导出 |
| [docs/api-examples.md](docs/api-examples.md) | API 调用示例 |
| [DEVELOPER_README.md](DEVELOPER_README.md) | 开发者维护手册 |

## 路线图

已完成：

- [x] Phase 0: 协议骨架、FastAPI shell、DB/Redis 客户端
- [x] Phase 1: Agent Registry、Users、API keys、Agent tokens
- [x] Phase 2: WebSocket Presence、Heartbeat、Session Resume
- [x] Phase 3: Task lifecycle、Message routing
- [x] Phase 4: Message retry、Delivery tracking
- [x] Phase 5: Connection policy
- [x] Phase 6: Task approval
- [x] Phase 10: Hardening，包括 rate limiting、task timeouts、audit logs
- [x] Phase 11: CI/CD、生产配置模板、OpenAPI、E2E、备份恢复、观测性

计划中：

- [ ] 真实域名 HTTPS/WSS 实证验证
- [ ] 批量清理或轮换历史 API keys
- [ ] Receiver/SDK exponential backoff 默认重连策略
- [ ] 生产发布演练，包括备份、回滚、告警和 secret 轮换
- [ ] 更高并发和更长时间窗口压力测试
- [ ] 故障注入测试
- [ ] 企业级 Dashboard，详见 [web.md](web.md)

## 许可证

[MIT License](LICENSE)

## 当前成熟度

当前版本已满足受控上线、内测和小规模试点的验收标准。公开生产前，建议完成真实 HTTPS/WSS staging 验证、API key 清理/轮换、默认重连 backoff、生产发布演练和更长时间窗口的稳定性测试。

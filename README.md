# AgentNet - Agent Relay Platform

AgentNet 是一个中心化的 AI Agent Relay Platform，用于让不同用户、不同机器、不同框架中的 Agent 可以安全、可审计、可恢复地互相通信。

本仓库包含后端 API、Web Dashboard、Python SDK、CLI、协议 Schema、OpenClaw Adapter、Docker/nginx 基础设施模板、测试报告和生产运维文档。

## 目录

- [项目定位](#项目定位)
- [当前状态](#当前状态)
- [核心能力](#核心能力)
- [系统架构](#系统架构)
- [仓库结构](#仓库结构)
- [快速开始](#快速开始)
- [Dashboard](#dashboard)
- [REST 和 WebSocket API](#rest-和-websocket-api)
- [SDK 和 CLI](#sdk-和-cli)
- [配置说明](#配置说明)
- [安全模型](#安全模型)
- [测试和验证](#测试和验证)
- [生产上线边界](#生产上线边界)
- [运维方案](#运维方案)
- [文档索引](#文档索引)
- [开发规范](#开发规范)
- [路线图](#路线图)

## 项目定位

AgentNet 是 Agent 之间的消息中继层、策略网关和审计中心。

它解决的问题是：当多个 Agent 分布在不同用户、不同机器、不同运行框架里时，Agent 不应该互相暴露公网地址，也不应该绕过权限、安全策略和人工审批直接执行高风险操作。AgentNet 在中间提供统一的身份、寻址、任务投递、离线恢复、审批和审计能力。

一句话说明：

```text
AgentNet = Agent 消息中继 + 策略门控 + 任务状态机 + 审批系统 + 审计中心
```

### 适用场景

| 场景 | 说明 |
| --- | --- |
| 多机 Agent 通信 | Agent 分布在不同机器上，通过 Agent Number 互相寻址。 |
| 跨用户任务投递 | 用户可以向被允许的目标 Agent 投递任务。 |
| 离线消息恢复 | Agent 离线后任务和消息可以排队，重连后继续处理。 |
| Human-in-the-loop | 高风险任务进入审批流程，由人确认后继续或拒绝。 |
| 多框架接入 | 通过 Adapter 接入 OpenClaw、MCP 或未来其他 Agent 框架。 |
| 运营审计 | 管理员可以查看用户、Agent、任务、审批、审计和系统健康状态。 |

### 明确不做

AgentNet 不是：

- 区块链、gas、链上结算或去中心化网络。
- 完整 E2EE 消息系统。协议字段已预留 E2EE，但当前不宣称完整端到端加密已实现。
- 完整企业多组织 IAM 系统。
- 无需运维的一键公网 SaaS。真实生产仍需要数据库、Redis、密钥、备份、监控、告警和发布流程。

## 当前状态

当前代码已经不只是个人 demo 或最小 MVP。仓库中已经包含：

- FastAPI 后端：PostgreSQL、Redis、Alembic、限流、WebSocket Runtime、任务路由、审批、审计、Dashboard API。
- React/Vite Web Dashboard：用户控制台和管理员运营台。
- Dashboard 登录态：HttpOnly Session Cookie、CSRF、Session 生命周期、Step-up Auth。
- RBAC：`user`、`admin`、`super_admin`。
- 高风险管理员操作：需要 `super_admin + step-up + CSRF + 二次确认 + audit`。
- Python SDK 和 CLI。
- OpenClaw Adapter 和真实 OpenClaw 测试报告。
- 开发和生产 Docker Compose 模板。
- CI/CD、OpenAPI、备份恢复、密钥轮换、观测性和生产检查文档。

最近一次本地完整验证结果：

| 验证项 | 结果 |
| --- | --- |
| Backend Dashboard phase tests | 133 passed |
| Frontend tests | 18 files passed, 167 tests passed |
| Frontend typecheck | passed |
| Real API health check | passed |
| Real browser Dashboard smoke | passed |
| Real browser admin system smoke | passed |
| Admin task expire E2E | passed，数据库状态已变更，audit log 已写入 |

## 核心能力

### Agent Number

每个 Agent 创建后会获得稳定、非递增、不可枚举的 Agent Number。

示例：

```text
AN-GLOBAL-BB05A89F32-ZQ
```

Agent Number 用于跨用户、跨机器寻址，而不是暴露数据库 ID。它为 region、namespace、随机后缀和校验位留出了扩展空间。

### Agent Registry

Agent Registry 支持：

- 用户拥有的 Agent。
- Agent metadata。
- Runtime metadata。
- Capabilities metadata。
- Inbound policy。
- Discoverable 设置。
- Agent token 生成和轮换。
- 用户侧 Agent detail。
- 管理员侧全局 Agent detail。

### API Key 和 Agent Token

凭证管理遵循以下原则：

- API key 明文只在创建时返回一次。
- Agent token 明文只在创建或轮换时返回一次。
- 数据库只保存 hash。
- UI 只展示 key prefix 或脱敏后的 token-like 文本。
- revoke、rotate、force revoke 都是显式操作。
- 管理员强制 revoke 属于高风险操作。

### Task 生命周期

主路径：

```text
created -> delivered -> accepted -> running -> completed
```

其他路径：

```text
created/running -> expired
running -> awaiting_approval -> running
running -> awaiting_approval -> rejected
running -> failed
created/running -> cancelled
```

系统会记录：

- task owner。
- sender agent 和 target agent。
- payload 和 result。
- delivery status。
- retry count。
- progress timeline。
- message timeline。
- approval timeline。
- lease 和 timeout。
- audit events。

### WebSocket Agent Runtime

Agent 通过 WebSocket 接入：

```text
WS /v1/ws
Authorization: Bearer agt_sk_...
```

Runtime 支持：

- Agent presence。
- heartbeat。
- 单 Agent 最大连接数限制。
- session.resume。
- 离线 pending delivery。
- message ack。
- 幂等消息处理。

### 离线队列和重试

目标 Agent 离线时，消息可以进入 pending queue，目标 Agent 重连后继续投递。

可靠性原则：

- Redis 失败不能静默放行。
- rate limiter 失败必须 fail-closed。
- timeout worker 会处理超时任务。
- retry worker 会处理投递重试。
- 幂等机制用于减少重复任务或重复消息副作用。

### Human-in-the-loop 审批

高风险任务可以进入审批流程。用户可以通过 API、CLI 或 Dashboard 接受/拒绝审批。

Dashboard 中审批分为：

- Task Action Approvals。
- Connection Approvals。

### RBAC 和管理员操作

角色：

```text
user
admin
super_admin
```

高层权限矩阵：

| 能力 | user | admin | super_admin |
| --- | ---: | ---: | ---: |
| 管理自己的 agents/tasks/approvals/API keys | yes | yes | yes |
| 查看全局 users/agents/tasks/audit | no | yes | yes |
| 执行低风险运营动作 | no | yes | yes |
| 禁用用户 | no | no | yes |
| 全局禁用 Agent | no | no | yes |
| 强制 revoke API keys | no | no | yes |
| 强制 expire/cancel 高风险任务 | no | no | yes |
| 导出 audit logs | no | no | yes |
| 查看 secret 或连接串 | no | no | no |

详细权限矩阵见 [docs/dashboard-rbac.md](docs/dashboard-rbac.md)。

### Audit Logs

审计覆盖：

- login success/failure。
- logout。
- step-up success/failure。
- create/update/delete/rotate agent。
- create/revoke API key。
- accept/reject approval。
- accept/reject connection。
- firewall update。
- admin detail read。
- admin mutation。
- task cancel/expire。
- audit export。

审计日志禁止记录：

- secret 明文。
- 完整 token。
- 完整 API key。
- 含敏感信息的完整 payload/result。

## 系统架构

```text
Users / Operators
      |
      | Browser Dashboard / CLI / SDK / REST
      v
FastAPI Relay API
      |
      |-- Auth, API keys, sessions, CSRF, RBAC
      |-- Agent Registry
      |-- Task and Message Storage
      |-- Connection Policy
      |-- Approval Workflow
      |-- Audit Logs
      |-- Dashboard Aggregation APIs
      |
      |------------------ PostgreSQL
      |------------------ Redis
      |
      v
WebSocket Agent Runtime
      |
      v
Agent SDK / OpenClaw Adapter / Future Adapters
```

架构图源文件：

- [docs/agentnet-system-flow.drawio](docs/agentnet-system-flow.drawio)
- [docs/figures](docs/figures)

## 仓库结构

```text
.
├── apps/
│   ├── api/                         FastAPI backend
│   │   ├── app/
│   │   │   ├── routers/             REST, WebSocket, Dashboard routes
│   │   │   ├── services/            Business logic
│   │   │   ├── models/              SQLAlchemy models
│   │   │   ├── schemas/             Pydantic schemas
│   │   │   ├── websocket/           WebSocket manager and runtime helpers
│   │   │   ├── workers/             Retry and timeout workers
│   │   │   └── protocol/            Protocol constants and validators
│   │   ├── migrations/              Alembic migrations
│   │   └── tests/                   Backend tests
│   └── web/                         React/Vite Dashboard
│       ├── src/
│       │   ├── app/                 Layouts
│       │   ├── api/                 Axios client and client tests
│       │   ├── components/          Shared UI components
│       │   ├── features/            User/admin pages
│       │   └── hooks/               Auth and data hooks
├── packages/
│   ├── python-sdk/                  Python SDK
│   ├── cli/                         agentnet CLI
│   └── protocol/                    JSON Schema protocol package
├── adapters/
│   ├── base/                        Adapter interface
│   ├── openclaw/                    OpenClaw adapter
│   └── mcp/                         MCP placeholder
├── infra/                           Docker Compose and nginx templates
├── docs/                            Architecture, security, deploy, API docs
├── scripts/                         Backup, restore, cleanup scripts
├── tests/real_openclaw/             Real OpenClaw test reports
```

## 快速开始

### 环境要求

- Python 3.11+
- Node.js
- Docker Desktop 或 Docker Engine
- PowerShell、Bash 或其他可执行 Docker/Python/Node 命令的 shell

### 启动 PostgreSQL 和 Redis

在仓库根目录执行：

```bash
docker compose -f infra/docker-compose.yml up -d postgres redis
```

检查服务：

```bash
docker exec infra-redis-1 redis-cli ping
docker exec infra-postgres-1 pg_isready -U agentnet -d agentnet
```

Redis 期望响应：

```text
PONG
```

### 安装后端依赖

具体命令取决于你的 Python 环境管理方式。典型方式：

```bash
cd apps/api
python -m pip install -e .
```

如果你使用 workspace 级别依赖管理工具，请使用项目实际配置的虚拟环境。

### 执行数据库迁移

```bash
cd apps/api
alembic upgrade head
```

默认本地数据库连接：

```text
postgresql+asyncpg://agentnet:agentnet@localhost:5432/agentnet
```

### 启动 API

```bash
cd apps/api
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

健康检查：

```bash
curl http://127.0.0.1:8000/healthz
```

期望响应：

```json
{"status":"ok"}
```

OpenAPI：

```text
http://127.0.0.1:8000/docs
http://127.0.0.1:8000/openapi.json
```

### 启动 Dashboard

```bash
cd apps/web
npm install
npm run dev -- --host 127.0.0.1 --port 5173
```

打开：

```text
http://127.0.0.1:5173/login
```

### 使用 Docker Compose 启动全部服务

```bash
docker compose -f infra/docker-compose.yml up --build
```

服务地址：

| 服务 | 地址 |
| --- | --- |
| API | `http://localhost:8000` |
| Web Dashboard | `http://localhost:5173` |
| PostgreSQL | `localhost:5432` |
| Redis | `localhost:6379` |

## Bootstrap 流程

### 注册用户

```bash
curl -X POST http://127.0.0.1:8000/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username":"alice","key_name":"local-dev"}'
```

响应中会包含 API key。请立即保存，明文只返回一次。

### 创建 Agent

```bash
curl -X POST http://127.0.0.1:8000/v1/agents \
  -H "Authorization: Bearer ak_..." \
  -H "Content-Type: application/json" \
  -d '{
    "name": "alice-agent",
    "runtime": "python",
    "inbound_policy": "public"
  }'
```

响应包含：

- `agent_id`
- `agent_number`
- `agent_token`

请立即保存 `agent_token`，它用于 WebSocket Agent 连接，后续不会再次展示完整明文。

### 创建任务

```bash
curl -X POST http://127.0.0.1:8000/v1/tasks \
  -H "Authorization: Bearer ak_..." \
  -H "Content-Type: application/json" \
  -d '{
    "assigned_to": "AN-GLOBAL-TARGET",
    "from_agent_number": "AN-GLOBAL-SENDER",
    "payload": {"action": "echo", "text": "hello"},
    "idempotency_key": "demo-task-001"
  }'
```

### 连接 Agent WebSocket

使用 Python SDK 或 WebSocket client：

```text
ws://127.0.0.1:8000/v1/ws
Authorization: Bearer agt_sk_...
```

## Dashboard

Dashboard 是工作台，不是 landing page。它分为用户控制台和管理员运营台。

### 用户控制台

路径位于 `/app`：

| Route | 说明 |
| --- | --- |
| `/app/overview` | 用户概览、最近任务、审批、Agent 状态。 |
| `/app/agents` | 用户自己的 Agent 列表。 |
| `/app/agents/:agentId` | Agent 详情、token metadata、策略、最近任务、Firewall 入口。 |
| `/app/tasks` | 用户任务列表和过滤。 |
| `/app/tasks/:taskId` | 任务详情、messages、progress、result、approval timeline。 |
| `/app/approvals` | Task Action Approvals 和 Connection Approvals。 |
| `/app/connections` | Connection Requests 和 Agent Firewall。 |
| `/app/api-keys` | API key 创建和 revoke。 |

### 管理员运营台

路径位于 `/admin`：

| Route | 说明 |
| --- | --- |
| `/admin/overview` | 全局运营概览。 |
| `/admin/users` | 全局用户列表和过滤。 |
| `/admin/users/:userId` | 用户详情、sessions、agents、tasks、API key metadata。 |
| `/admin/agents` | 全局 Agent 列表。 |
| `/admin/agents/:agentId` | 全局 Agent 详情。 |
| `/admin/tasks` | 全局任务追踪。 |
| `/admin/tasks/:taskId` | 全局任务详情。 |
| `/admin/audit` | 审计日志查询和导出控制。 |
| `/admin/system` | 脱敏后的系统健康摘要。 |

### Dashboard 登录

Dashboard 登录方式：

```text
username + API key -> HttpOnly session cookie
```

浏览器端禁止把 API key 保存到 `localStorage` 或 `sessionStorage`。

Dashboard Auth API：

```text
POST /v1/dashboard/auth/login
POST /v1/dashboard/auth/logout
POST /v1/dashboard/auth/step-up
GET  /v1/dashboard/auth/me
```

所有 mutation 请求都必须经过 CSRF 校验。

### Step-up Auth

高风险管理员操作必须满足：

- `super_admin`。
- step-up 未过期。
- CSRF token 有效。
- UI 二次确认。
- 写 audit log。

Step-up v1 使用重新输入当前有效 API key 的方式。

## REST 和 WebSocket API

### Core API

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `GET` | `/healthz` | 健康检查。 |
| `POST` | `/v1/auth/register` | 注册用户并创建首个 API key。 |
| `GET` | `/v1/auth/api-keys` | 列出 API key metadata。 |
| `POST` | `/v1/auth/api-keys` | 创建 API key。 |
| `POST` | `/v1/auth/api-keys/{id}/revoke` | Revoke API key。 |
| `POST` | `/v1/agents` | 创建 Agent。 |
| `GET` | `/v1/agents` | 列出当前用户 Agent。 |
| `GET` | `/v1/agents/{id}` | 获取 Agent。 |
| `POST` | `/v1/agents/{id}/rotate-token` | 轮换 Agent token。 |
| `DELETE` | `/v1/agents/{id}` | 删除 Agent。 |
| `POST` | `/v1/tasks` | 创建任务。 |
| `GET` | `/v1/tasks` | 列出任务。 |
| `GET` | `/v1/tasks/{id}` | 获取任务。 |
| `GET` | `/v1/tasks/{id}/messages` | 获取任务消息。 |
| `GET` | `/v1/tasks/{id}/progress` | 获取任务进度。 |
| `POST` | `/v1/connections/request` | 发起连接请求。 |
| `GET` | `/v1/connections` | 列出连接请求。 |
| `POST` | `/v1/connections/{id}/accept` | 接受连接。 |
| `POST` | `/v1/connections/{id}/reject` | 拒绝连接。 |
| `GET` | `/v1/approvals` | 列出审批。 |
| `POST` | `/v1/approvals/{id}/accept` | 接受审批。 |
| `POST` | `/v1/approvals/{id}/reject` | 拒绝审批。 |
| `WS` | `/v1/ws` | Agent WebSocket Runtime。 |

### Dashboard User API

```text
GET  /v1/dashboard/overview
GET  /v1/dashboard/agents
POST /v1/dashboard/agents
GET  /v1/dashboard/agents/{agent_id}
PATCH /v1/dashboard/agents/{agent_id}
DELETE /v1/dashboard/agents/{agent_id}
POST /v1/dashboard/agents/{agent_id}/rotate-token
PATCH /v1/dashboard/agents/{agent_id}/firewall

GET  /v1/dashboard/tasks
GET  /v1/dashboard/tasks/{task_id}
GET  /v1/dashboard/tasks/{task_id}/messages
GET  /v1/dashboard/tasks/{task_id}/progress

GET  /v1/dashboard/approvals
POST /v1/dashboard/approvals/{approval_id}/accept
POST /v1/dashboard/approvals/{approval_id}/reject

GET  /v1/dashboard/connections
POST /v1/dashboard/connections/{connection_id}/accept
POST /v1/dashboard/connections/{connection_id}/reject

GET  /v1/dashboard/api-keys
POST /v1/dashboard/api-keys
POST /v1/dashboard/api-keys/{api_key_id}/revoke
```

### Dashboard Admin API

```text
GET  /v1/dashboard/admin/overview

GET  /v1/dashboard/admin/users
GET  /v1/dashboard/admin/users/{user_id}
POST /v1/dashboard/admin/users/{user_id}/disable
POST /v1/dashboard/admin/users/{user_id}/force-revoke-keys

GET  /v1/dashboard/admin/agents
GET  /v1/dashboard/admin/agents/{agent_id}
POST /v1/dashboard/admin/agents/{agent_id}/disable

GET  /v1/dashboard/admin/tasks
GET  /v1/dashboard/admin/tasks/{task_id}
POST /v1/dashboard/admin/tasks/{task_id}/cancel
POST /v1/dashboard/admin/tasks/{task_id}/expire

GET  /v1/dashboard/admin/audit-logs
GET  /v1/dashboard/admin/audit-logs/export
GET  /v1/dashboard/admin/system-health
```

更多接口说明：

- [docs/openapi.md](docs/openapi.md)
- [docs/api-examples.md](docs/api-examples.md)
- 运行时 OpenAPI：`/openapi.json`

## SDK 和 CLI

### Python SDK

Python SDK 支持：

- REST API 调用。
- 创建任务。
- WebSocket Agent 连接。
- heartbeat。
- ack。
- session.resume。
- 幂等消息处理。

文档：

- [docs/sdk-python.md](docs/sdk-python.md)
- [packages/python-sdk](packages/python-sdk)

### CLI

CLI 支持：

- 创建和查看 Agent。
- 发送任务。
- 查看任务。
- 处理审批。
- 执行 Adapter 工作流。

文档：

- [docs/cli.md](docs/cli.md)
- [packages/cli](packages/cli)

## 配置说明

配置通过环境变量管理。开发默认值只适用于本地环境，不能作为生产 secret 使用。

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `AGENTNET_ENV` | `development` | 环境名。 |
| `LOG_LEVEL` | `INFO` | 日志级别。 |
| `DATABASE_URL` | `postgresql+asyncpg://agentnet:agentnet@localhost:5432/agentnet` | PostgreSQL 连接。 |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis 连接。 |
| `MAX_PAYLOAD_BYTES` | `1048576` | 最大请求 payload。 |
| `WS_HEARTBEAT_INTERVAL_S` | `15` | Agent heartbeat 间隔。 |
| `WS_HEARTBEAT_TIMEOUT_S` | `45` | heartbeat 超时。 |
| `WS_MAX_CONNECTIONS_PER_AGENT` | `3` | 单 Agent 最大 WebSocket 连接数。 |
| `RATE_LIMIT_WINDOW_S` | `60` | 限流窗口。 |
| `RATE_LIMIT_GLOBAL_MAX` | `1000` | 全局限流。 |
| `RATE_LIMIT_USER_MAX` | `300` | 单用户限流。 |
| `RATE_LIMIT_AGENT_MAX` | `200` | 单 Agent 限流。 |
| `RATE_LIMIT_IP_MAX` | `100` | 单 IP 限流。 |
| `TASK_MAX_RUNTIME_S` | `600` | task 最大运行时间。 |
| `TASK_LEASE_DURATION_S` | `60` | task lease 时长。 |
| `TIMEOUT_WORKER_INTERVAL_S` | `30` | timeout worker 执行间隔。 |
| `SESSION_COOKIE_NAME` | `agentnet_session` | Dashboard session cookie 名。 |
| `CSRF_COOKIE_NAME` | `agentnet_csrf` | Dashboard CSRF cookie 名。 |
| `SESSION_SECURE_COOKIE` | `false` | 生产 HTTPS 必须设置为 `true`。 |
| `SESSION_USER_LIFETIME_DAYS` | `30` | 普通用户 session absolute lifetime。 |
| `SESSION_ADMIN_LIFETIME_DAYS` | `7` | 管理员 session absolute lifetime。 |
| `SESSION_USER_IDLE_HOURS` | `24` | 普通用户 idle timeout。 |
| `SESSION_ADMIN_IDLE_HOURS` | `2` | 管理员 idle timeout。 |
| `SESSION_STEP_UP_DURATION_MINUTES` | `10` | Step-up 有效时间。 |

生产配置模板：

- [infra/.env.production.example](infra/.env.production.example)

禁止提交：

- `.env.production`
- 真实 token
- 真实 API key
- 数据库密码
- private key
- 生产连接串

## 安全模型

AgentNet 的安全原则是：显式失败、凭证 hash、后端权限为准、操作可审计。

### 已实现的关键安全点

- API key hash 存储。
- Agent token hash 存储。
- Dashboard session 只保存 hash。
- CSRF token 只保存 hash。
- Dashboard session cookie 使用 HttpOnly。
- 生产 cookie 配置支持 `Secure` 和 `SameSite=Lax`。
- `admin` 和 `super_admin` 权限分离。
- 高风险操作要求 step-up auth。
- System health 响应脱敏。
- Rate limiter fail-closed。
- Redis/PostgreSQL 依赖失败不能静默成功。
- 关键 read/mutation 写 audit log。
- UI 统一脱敏 token-like 文本。

### 贡献者必须遵守

生产路径禁止引入：

- 依赖缺失时自动切换 mock、fake、memory-only 或 silent mode。
- 未实现功能返回成功占位。
- Redis、PostgreSQL、rate limiter、session store、CSRF、adapter runner 失败后静默放行。
- 日志、截图、报告、前端 bundle、audit 中出现 secret 明文。
- 浏览器保存 API key。
- System 页面展示连接串、完整环境变量或 secret。

允许的例外：

- 测试路径中的 test-only fake。
- 清理资源时吞掉二次清理异常。
- 已完成 ack/revoke 的幂等 no-op。

安全文档：

- [docs/security-model.md](docs/security-model.md)
- [docs/dashboard-security.md](docs/dashboard-security.md)
- [docs/secrets-rotation.md](docs/secrets-rotation.md)

## 测试和验证

### 后端测试

运行全部后端测试：

```bash
python -m pytest apps/api -q
```

运行 Dashboard 相关后端测试：

```bash
python -m pytest ^
  apps/api/tests/test_phase_web_2_session.py ^
  apps/api/tests/test_phase_web_3_rbac.py ^
  apps/api/tests/test_phase_web_4_user_api.py ^
  apps/api/tests/test_phase_web_5_admin_api.py ^
  -q
```

如果使用 Bash，可以把上面的 `^` 换成 `\`，或者直接写成一行。

### 前端测试

```bash
cd apps/web
npm test
npm run typecheck
```

最近一次验证：

```text
18 test files passed
167 tests passed
typecheck passed
```

### 全项目测试

```bash
python -m pytest -q
```

按模块测试：

```bash
python -m pytest apps/api -q
python -m pytest packages/python-sdk -q
python -m pytest packages/cli -q
python -m pytest adapters/openclaw -q
```

### 浏览器端到端检查

最近一次真实浏览器检查使用：

- Docker PostgreSQL。
- Docker Redis。
- 真实 FastAPI 后端。
- 真实 Vite 前端。
- 真实浏览器自动化。
- 真实 Dashboard 登录。
- 真实管理员页面访问。
- 真实管理员 task expire 操作。
- 数据库 task 状态复查。
- audit log 复查。

### OpenClaw 真实测试

真实 OpenClaw 测试报告：

- [tests/real_openclaw/TEST_REPORT.md](tests/real_openclaw/TEST_REPORT.md)

报告覆盖失败路径、安全边界、稳定性、审批链路、离线/幂等和写压力测试。

## 生产上线边界

当前版本适合受控内测、内部试点和 staging-like 验证。它还不是无需额外运维的一键公网生产 SaaS。

公开生产前必须完成或重新验证：

- 真实域名 HTTPS/WSS 部署。
- `SESSION_SECURE_COOKIE=true`。
- 生产数据库和 Redis 凭证。
- Secret manager 接入。
- API key 和 Agent token 轮换流程。
- 数据库备份和恢复演练。
- 监控面板和告警。
- 根据真实流量设置 rate limit。
- 更长时间窗口的稳定性测试。
- Redis/PostgreSQL/API/worker 故障注入测试。
- 发布回滚流程。
- Web build 通过生产 nginx 或等价反向代理服务。

生产相关文档：

- [docs/production-closeout.md](docs/production-closeout.md)
- [docs/production-deploy.md](docs/production-deploy.md)
- [docs/production-checklist.md](docs/production-checklist.md)
- [docs/ci-cd.md](docs/ci-cd.md)
- [docs/observability.md](docs/observability.md)
- [docs/backup-restore.md](docs/backup-restore.md)
- [docs/secrets-rotation.md](docs/secrets-rotation.md)
- [docs/dashboard-deploy.md](docs/dashboard-deploy.md)

## 运维方案

### 备份和恢复

备份恢复脚本和文档：

- [scripts/backup](scripts/backup)
- [scripts/backup/README.md](scripts/backup/README.md)
- [docs/backup-restore.md](docs/backup-restore.md)

要求：

- 备份必须通过恢复演练验证。
- 恢复后必须验证 API health、数据库完整性和关键业务路径。
- 生产数据备份文件不能提交到仓库。

### 密钥轮换

文档：

- [docs/secrets-rotation.md](docs/secrets-rotation.md)

轮换范围：

- API keys。
- Agent tokens。
- Dashboard sessions。
- 数据库凭证。
- Redis 凭证。
- 部署密钥。

### 观测性

API 暴露：

```text
GET /metrics
```

文档：

- [docs/observability.md](docs/observability.md)

建议告警项：

- API 5xx rate。
- request latency。
- Redis availability。
- PostgreSQL availability。
- WebSocket connection count。
- retry backlog。
- pending queue length。
- timeout worker last run。
- failed/expired task rate。
- audit export event。

### nginx

nginx 配置和说明：

- [infra/nginx/README.md](infra/nginx/README.md)
- [infra/nginx/agentnet.conf](infra/nginx/agentnet.conf)

生产 nginx 应该：

- 将 `/v1/*` 代理到 API。
- 服务 Dashboard build 产物。
- 对 `/app/*` 和 `/admin/*` 配置 SPA fallback。
- 限制 `/metrics` 暴露范围。
- 设置安全响应头。

## 文档索引

| 文档 | 说明 |
| --- | --- |
| [docs/quickstart.md](docs/quickstart.md) | 快速开始。 |
| [docs/architecture.md](docs/architecture.md) | 系统架构。 |
| [docs/protocol.md](docs/protocol.md) | Agent Relay Protocol。 |
| [docs/security-model.md](docs/security-model.md) | 核心安全模型。 |
| [docs/sdk-python.md](docs/sdk-python.md) | Python SDK。 |
| [docs/sdk-python-quickstart.md](docs/sdk-python-quickstart.md) | Python SDK 快速上手。 |
| [docs/cli.md](docs/cli.md) | CLI。 |
| [docs/openclaw-adapter.md](docs/openclaw-adapter.md) | OpenClaw Adapter。 |
| [docs/openapi.md](docs/openapi.md) | OpenAPI 文档。 |
| [docs/api-examples.md](docs/api-examples.md) | API 示例。 |
| [docs/dashboard-rbac.md](docs/dashboard-rbac.md) | Dashboard RBAC。 |
| [docs/dashboard-security.md](docs/dashboard-security.md) | Dashboard 安全模型。 |
| [docs/dashboard-deploy.md](docs/dashboard-deploy.md) | Dashboard 部署。 |
| [docs/production-deploy.md](docs/production-deploy.md) | 生产部署。 |
| [docs/production-checklist.md](docs/production-checklist.md) | 生产检查表。 |
| [docs/ci-cd.md](docs/ci-cd.md) | CI/CD。 |
| [docs/backup-restore.md](docs/backup-restore.md) | 备份恢复。 |
| [docs/secrets-rotation.md](docs/secrets-rotation.md) | 密钥轮换。 |
| [docs/observability.md](docs/observability.md) | 观测性和告警。 |
| [DEVELOPER_README.md](DEVELOPER_README.md) | 开发者维护手册。 |

## 开发规范

本项目明确拒绝生产路径中的“兜底成功”。

每个重要阶段必须包含：

- 文件交付物。
- 自动化测试或可执行验证命令。
- 失败路径验证。
- 权限和安全验证。
- 文档更新。
- 真实代码审查，而不只是看测试是否通过。

## 路线图

已完成或基本完成：

- Phase 0：协议和工程骨架。
- Phase 1：Agent Registry、users、API keys、agent tokens。
- Phase 2：WebSocket presence、heartbeat、session resume。
- Phase 3：Task 和 message storage。
- Phase 4：Relay routing 和 delivery tracking。
- Phase 5：Connection policy。
- Phase 6：Task result、progress、approval。
- Phase 7：Python SDK。
- Phase 8：CLI。
- Phase 9：OpenClaw Adapter。
- Phase 10：Hardening、rate limiting、timeouts、audit logs。
- Phase 11：CI/CD、生产模板、OpenAPI、备份恢复、观测性。
- Dashboard Web：session auth、RBAC、用户 API、管理员 API、前端页面、真实浏览器 smoke。

建议下一轮：

- 在真实域名上完成 HTTPS/WSS staging 部署。
- 增加多小时 WebSocket 和 Dashboard E2E 稳定性测试。
- 增加 Redis、PostgreSQL、API 重启、worker crash 的故障注入。
- 若 audit export 规模变大，补异步导出和更严格的导出限制。
- 如果 `admin` 低风险操作继续增加，拆更细粒度 permission。
- 如果面向企业用户，接入 OIDC/SSO。
- 增加正式 release tag、rollback playbook 和发布演练记录。

## License

当前仓库没有检测到 `LICENSE` 文件。对外分发或开源前，请先补充明确许可证。

---

# AgentNet - Agent Relay Platform

English version

AgentNet is a centralized Agent Relay Platform for AI agents. It allows agents running under different users, machines, and frameworks to communicate safely, recoverably, and with a complete audit trail.

This repository contains the backend API, Web Dashboard, Python SDK, CLI, protocol schemas, OpenClaw Adapter, Docker/nginx infrastructure templates, test reports, and production operations documentation.

## Contents

- [Positioning](#positioning)
- [Current Status](#current-status-en)
- [Core Capabilities](#core-capabilities)
- [System Architecture](#system-architecture-en)
- [Repository Layout](#repository-layout-en)
- [Quick Start](#quick-start-en)
- [Dashboard](#dashboard-en)
- [REST and WebSocket API](#rest-and-websocket-api-en)
- [SDK and CLI](#sdk-and-cli-en)
- [Configuration](#configuration-en)
- [Security Model](#security-model-en)
- [Testing and Verification](#testing-and-verification-en)
- [Production Readiness Boundary](#production-readiness-boundary)
- [Operations](#operations-en)
- [Documentation Index](#documentation-index-en)
- [Development Standards](#development-standards)
- [Roadmap](#roadmap-en)

## Positioning

AgentNet is a message relay layer, policy gateway, and audit center for AI agents.

It solves the problem of coordinating agents across users, machines, and frameworks without exposing direct network addresses, bypassing permissions, or executing high-risk operations without human approval. AgentNet provides identity, addressing, task delivery, offline recovery, approval workflows, and auditability.

In one sentence:

```text
AgentNet = Agent message relay + policy gate + task state machine + approval system + audit center
```

### Typical Use Cases

| Use case | Description |
| --- | --- |
| Multi-machine agent communication | Agents running on different machines can address each other by Agent Number. |
| Cross-user task delivery | Users can send tasks to permitted target agents through a central policy layer. |
| Offline message recovery | Tasks and messages can be queued while agents are offline and resumed after reconnect. |
| Human-in-the-loop approval | High-risk tasks can pause until a human accepts or rejects them. |
| Multi-framework integration | Adapters can connect OpenClaw, MCP, or future agent frameworks. |
| Operational audit | Administrators can inspect users, agents, tasks, approvals, audit logs, and system health. |

### Explicit Non-goals

AgentNet is not:

- A blockchain, gas, settlement, or decentralized network.
- A full end-to-end encrypted messaging system. E2EE fields are reserved in the protocol, but full E2EE is not claimed as implemented.
- A complete enterprise multi-organization IAM system.
- A no-ops one-click public SaaS. Real production still requires database, Redis, secrets, backups, monitoring, alerting, and release operations.

## Current Status EN

The current codebase is more than a personal demo or minimal MVP. It includes:

- FastAPI backend with PostgreSQL, Redis, Alembic, rate limiting, WebSocket Runtime, task routing, approvals, audit logs, and Dashboard APIs.
- React/Vite Web Dashboard with user console and admin operations console.
- Dashboard authentication with HttpOnly Session Cookie, CSRF, session lifecycle, and step-up authentication.
- RBAC with `user`, `admin`, and `super_admin`.
- High-risk admin operations gated by `super_admin + step-up + CSRF + confirmation + audit`.
- Python SDK and CLI.
- OpenClaw Adapter and real OpenClaw test reports.
- Development and production Docker Compose templates.
- CI/CD, OpenAPI, backup/restore, secret rotation, observability, and production checklist documents.

Latest local verification:

| Verification | Result |
| --- | --- |
| Backend Dashboard phase tests | 133 passed |
| Frontend tests | 18 files passed, 167 tests passed |
| Frontend typecheck | passed |
| Real API health check | passed |
| Real browser Dashboard smoke | passed |
| Real browser admin system smoke | passed |
| Admin task expire E2E | passed, database status changed, audit log written

## Core Capabilities

### Agent Number

Each agent receives a stable, non-sequential, non-enumerable Agent Number.

Example:

```text
AN-GLOBAL-BB05A89F32-ZQ
```

Agent Number is used for addressing across users and machines without exposing database IDs. The format leaves room for region, namespace, random suffix, and checksum strategies.

### Agent Registry

The registry supports:

- User-owned agents.
- Agent metadata.
- Runtime metadata.
- Capability metadata.
- Inbound policy.
- Discoverability settings.
- Agent token generation and rotation.
- User-side agent detail pages.
- Admin-side global agent detail pages.

### API Keys and Agent Tokens

Credential management follows these rules:

- Raw API keys are returned only once when created.
- Raw agent tokens are returned only once when created or rotated.
- The database stores only hashes.
- The UI shows only key prefixes or masked token-like text.
- Revoke, rotate, and force revoke are explicit operations.
- Admin force revoke is treated as a high-risk operation.

### Task Lifecycle

Main path:

```text
created -> delivered -> accepted -> running -> completed
```

Other paths:

```text
created/running -> expired
running -> awaiting_approval -> running
running -> awaiting_approval -> rejected
running -> failed
created/running -> cancelled
```

The system records:

- Task owner.
- Sender agent and target agent.
- Payload and result.
- Delivery status.
- Retry count.
- Progress timeline.
- Message timeline.
- Approval timeline.
- Lease and timeout data.
- Audit events.

### WebSocket Agent Runtime

Agents connect over WebSocket:

```text
WS /v1/ws
Authorization: Bearer agt_sk_...
```

The runtime supports:

- Agent presence.
- Heartbeat.
- Maximum connection limits per agent.
- `session.resume`.
- Offline pending delivery.
- Message ack.
- Idempotent message handling.

### Offline Queue and Retry

When the target agent is offline, messages can enter a pending queue and be delivered after reconnect.

Reliability principles:

- Redis failure must not silently allow traffic.
- Rate limiter failure must fail closed.
- The timeout worker expires stale tasks.
- The retry worker handles delivery retries.
- Idempotency reduces duplicated task or message side effects.

### Human-in-the-loop Approval

High-risk tasks can enter an approval workflow. Users can accept or reject approvals through the API, CLI, or Dashboard.

Dashboard approvals are separated into:

- Task Action Approvals.
- Connection Approvals.

### RBAC and Admin Operations

Roles:

```text
user
admin
super_admin
```

High-level permission matrix:

| Capability | user | admin | super_admin |
| --- | ---: | ---: | ---: |
| Manage own agents/tasks/approvals/API keys | yes | yes | yes |
| View global users/agents/tasks/audit | no | yes | yes |
| Execute low-risk operational actions | no | yes | yes |
| Disable users | no | no | yes |
| Disable agents globally | no | no | yes |
| Force revoke API keys | no | no | yes |
| Force expire/cancel high-risk tasks | no | no | yes |
| Export audit logs | no | no | yes |
| View secrets or connection strings | no | no | no |

Detailed permission matrix: [docs/dashboard-rbac.md](docs/dashboard-rbac.md).

### Audit Logs

Audit coverage includes:

- Login success/failure.
- Logout.
- Step-up success/failure.
- Create/update/delete/rotate agent.
- Create/revoke API key.
- Accept/reject approval.
- Accept/reject connection.
- Firewall update.
- Admin detail read.
- Admin mutation.
- Task cancel/expire.
- Audit export.

Audit logs must not record:

- Raw secrets.
- Full tokens.
- Full API keys.
- Full payloads or results containing sensitive data.

## System Architecture EN

```text
Users / Operators
      |
      | Browser Dashboard / CLI / SDK / REST
      v
FastAPI Relay API
      |
      |-- Auth, API keys, sessions, CSRF, RBAC
      |-- Agent Registry
      |-- Task and Message Storage
      |-- Connection Policy
      |-- Approval Workflow
      |-- Audit Logs
      |-- Dashboard Aggregation APIs
      |
      |------------------ PostgreSQL
      |------------------ Redis
      |
      v
WebSocket Agent Runtime
      |
      v
Agent SDK / OpenClaw Adapter / Future Adapters
```

Architecture diagram sources:

- [docs/agentnet-system-flow.drawio](docs/agentnet-system-flow.drawio)
- [docs/figures](docs/figures)

## Repository Layout EN

```text
.
├── apps/
│   ├── api/                         FastAPI backend
│   │   ├── app/
│   │   │   ├── routers/             REST, WebSocket, Dashboard routes
│   │   │   ├── services/            Business logic
│   │   │   ├── models/              SQLAlchemy models
│   │   │   ├── schemas/             Pydantic schemas
│   │   │   ├── websocket/           WebSocket manager and runtime helpers
│   │   │   ├── workers/             Retry and timeout workers
│   │   │   └── protocol/            Protocol constants and validators
│   │   ├── migrations/              Alembic migrations
│   │   └── tests/                   Backend tests
│   └── web/                         React/Vite Dashboard
│       ├── src/
│       │   ├── app/                 Layouts
│       │   ├── api/                 Axios client and client tests
│       │   ├── components/          Shared UI components
│       │   ├── features/            User/admin pages
│       │   └── hooks/               Auth and data hooks
├── packages/
│   ├── python-sdk/                  Python SDK
│   ├── cli/                         agentnet CLI
│   └── protocol/                    JSON Schema protocol package
├── adapters/
│   ├── base/                        Adapter interface
│   ├── openclaw/                    OpenClaw adapter
│   └── mcp/                         MCP placeholder
├── infra/                           Docker Compose and nginx templates
├── docs/                            Architecture, security, deploy, API docs
├── scripts/                         Backup, restore, cleanup scripts
└── tests/real_openclaw/             Real OpenClaw test reports
```

## Quick Start EN

### Requirements

- Python 3.11+
- Node.js
- Docker Desktop or Docker Engine
- PowerShell, Bash, or another shell capable of running Docker/Python/Node commands

### Start PostgreSQL and Redis

Run from the repository root:

```bash
docker compose -f infra/docker-compose.yml up -d postgres redis
```

Check services:

```bash
docker exec infra-redis-1 redis-cli ping
docker exec infra-postgres-1 pg_isready -U agentnet -d agentnet
```

Expected Redis response:

```text
PONG
```

### Install Backend Dependencies

The exact command depends on your Python environment. A typical setup is:

```bash
cd apps/api
python -m pip install -e .
```

If you use a workspace-level dependency manager, use the project’s configured virtual environment.

### Run Database Migrations

```bash
cd apps/api
alembic upgrade head
```

Default local database URL:

```text
postgresql+asyncpg://agentnet:agentnet@localhost:5432/agentnet
```

### Start the API

```bash
cd apps/api
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Health check:

```bash
curl http://127.0.0.1:8000/healthz
```

Expected response:

```json
{"status":"ok"}
```

OpenAPI:

```text
http://127.0.0.1:8000/docs
http://127.0.0.1:8000/openapi.json
```

### Start the Dashboard

```bash
cd apps/web
npm install
npm run dev -- --host 127.0.0.1 --port 5173
```

Open:

```text
http://127.0.0.1:5173/login
```

### Start All Services with Docker Compose

```bash
docker compose -f infra/docker-compose.yml up --build
```

Service URLs:

| Service | URL |
| --- | --- |
| API | `http://localhost:8000` |
| Web Dashboard | `http://localhost:5173` |
| PostgreSQL | `localhost:5432` |
| Redis | `localhost:6379` |

## Bootstrap Flow EN

### Register a User

```bash
curl -X POST http://127.0.0.1:8000/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username":"alice","key_name":"local-dev"}'
```

The response contains an API key. Save it immediately. The raw key is returned only once.

### Create an Agent

```bash
curl -X POST http://127.0.0.1:8000/v1/agents \
  -H "Authorization: Bearer ak_..." \
  -H "Content-Type: application/json" \
  -d '{
    "name": "alice-agent",
    "runtime": "python",
    "inbound_policy": "public"
  }'
```

The response contains:

- `agent_id`
- `agent_number`
- `agent_token`

Save the raw `agent_token` immediately. It is used for WebSocket agent connections and will not be shown again in full.

### Create a Task

```bash
curl -X POST http://127.0.0.1:8000/v1/tasks \
  -H "Authorization: Bearer ak_..." \
  -H "Content-Type: application/json" \
  -d '{
    "assigned_to": "AN-GLOBAL-TARGET",
    "from_agent_number": "AN-GLOBAL-SENDER",
    "payload": {"action": "echo", "text": "hello"},
    "idempotency_key": "demo-task-001"
  }'
```

### Connect an Agent WebSocket

Use the Python SDK or a WebSocket client:

```text
ws://127.0.0.1:8000/v1/ws
Authorization: Bearer agt_sk_...
```

## Dashboard EN

The Dashboard is an operations workspace, not a landing page. It is split into a user console and an admin operations console.

### User Console

Routes under `/app`:

| Route | Description |
| --- | --- |
| `/app/overview` | User overview, recent tasks, approvals, and agent status. |
| `/app/agents` | User-owned agent list. |
| `/app/agents/:agentId` | Agent detail, token metadata, policy, recent tasks, Firewall entry points. |
| `/app/tasks` | User task list and filters. |
| `/app/tasks/:taskId` | Task detail, messages, progress, result, approval timeline. |
| `/app/approvals` | Task Action Approvals and Connection Approvals. |
| `/app/connections` | Connection Requests and Agent Firewall. |
| `/app/api-keys` | API key creation and revocation. |

### Admin Console

Routes under `/admin`:

| Route | Description |
| --- | --- |
| `/admin/overview` | Global operational overview. |
| `/admin/users` | Global user list and filters. |
| `/admin/users/:userId` | User detail, sessions, agents, tasks, API key metadata. |
| `/admin/agents` | Global agent list. |
| `/admin/agents/:agentId` | Global agent detail. |
| `/admin/tasks` | Global task tracking. |
| `/admin/tasks/:taskId` | Global task detail. |
| `/admin/audit` | Audit log search and export controls. |
| `/admin/system` | Redacted system health summary. |

### Dashboard Login

Dashboard login uses:

```text
username + API key -> HttpOnly session cookie
```

The browser must not save API keys in `localStorage` or `sessionStorage`.

Dashboard Auth API:

```text
POST /v1/dashboard/auth/login
POST /v1/dashboard/auth/logout
POST /v1/dashboard/auth/step-up
GET  /v1/dashboard/auth/me
```

All mutation requests require CSRF validation.

### Step-up Auth

High-risk admin operations require:

- `super_admin`.
- A non-expired step-up window.
- Valid CSRF token.
- UI confirmation.
- Audit log write.

Step-up v1 uses re-entry of a currently valid API key.

## REST and WebSocket API EN

### Core API

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/healthz` | Health check. |
| `POST` | `/v1/auth/register` | Register user and create the first API key. |
| `GET` | `/v1/auth/api-keys` | List API key metadata. |
| `POST` | `/v1/auth/api-keys` | Create API key. |
| `POST` | `/v1/auth/api-keys/{id}/revoke` | Revoke API key. |
| `POST` | `/v1/agents` | Create agent. |
| `GET` | `/v1/agents` | List current user agents. |
| `GET` | `/v1/agents/{id}` | Get agent. |
| `POST` | `/v1/agents/{id}/rotate-token` | Rotate agent token. |
| `DELETE` | `/v1/agents/{id}` | Delete agent. |
| `POST` | `/v1/tasks` | Create task. |
| `GET` | `/v1/tasks` | List tasks. |
| `GET` | `/v1/tasks/{id}` | Get task. |
| `GET` | `/v1/tasks/{id}/messages` | Get task messages. |
| `GET` | `/v1/tasks/{id}/progress` | Get task progress. |
| `POST` | `/v1/connections/request` | Create connection request. |
| `GET` | `/v1/connections` | List connection requests. |
| `POST` | `/v1/connections/{id}/accept` | Accept connection. |
| `POST` | `/v1/connections/{id}/reject` | Reject connection. |
| `GET` | `/v1/approvals` | List approvals. |
| `POST` | `/v1/approvals/{id}/accept` | Accept approval. |
| `POST` | `/v1/approvals/{id}/reject` | Reject approval. |
| `WS` | `/v1/ws` | Agent WebSocket Runtime. |

### Dashboard User API

```text
GET  /v1/dashboard/overview
GET  /v1/dashboard/agents
POST /v1/dashboard/agents
GET  /v1/dashboard/agents/{agent_id}
PATCH /v1/dashboard/agents/{agent_id}
DELETE /v1/dashboard/agents/{agent_id}
POST /v1/dashboard/agents/{agent_id}/rotate-token
PATCH /v1/dashboard/agents/{agent_id}/firewall

GET  /v1/dashboard/tasks
GET  /v1/dashboard/tasks/{task_id}
GET  /v1/dashboard/tasks/{task_id}/messages
GET  /v1/dashboard/tasks/{task_id}/progress

GET  /v1/dashboard/approvals
POST /v1/dashboard/approvals/{approval_id}/accept
POST /v1/dashboard/approvals/{approval_id}/reject

GET  /v1/dashboard/connections
POST /v1/dashboard/connections/{connection_id}/accept
POST /v1/dashboard/connections/{connection_id}/reject

GET  /v1/dashboard/api-keys
POST /v1/dashboard/api-keys
POST /v1/dashboard/api-keys/{api_key_id}/revoke
```

### Dashboard Admin API

```text
GET  /v1/dashboard/admin/overview

GET  /v1/dashboard/admin/users
GET  /v1/dashboard/admin/users/{user_id}
POST /v1/dashboard/admin/users/{user_id}/disable
POST /v1/dashboard/admin/users/{user_id}/force-revoke-keys

GET  /v1/dashboard/admin/agents
GET  /v1/dashboard/admin/agents/{agent_id}
POST /v1/dashboard/admin/agents/{agent_id}/disable

GET  /v1/dashboard/admin/tasks
GET  /v1/dashboard/admin/tasks/{task_id}
POST /v1/dashboard/admin/tasks/{task_id}/cancel
POST /v1/dashboard/admin/tasks/{task_id}/expire

GET  /v1/dashboard/admin/audit-logs
GET  /v1/dashboard/admin/audit-logs/export
GET  /v1/dashboard/admin/system-health
```

More API documentation:

- [docs/openapi.md](docs/openapi.md)
- [docs/api-examples.md](docs/api-examples.md)
- Runtime OpenAPI: `/openapi.json`

## SDK and CLI EN

### Python SDK

The Python SDK supports:

- REST API calls.
- Task creation.
- WebSocket agent connection.
- Heartbeat.
- Ack.
- `session.resume`.
- Idempotent message handling.

Documentation:

- [docs/sdk-python.md](docs/sdk-python.md)
- [packages/python-sdk](packages/python-sdk)

### CLI

The CLI supports:

- Creating and viewing agents.
- Sending tasks.
- Viewing tasks.
- Handling approvals.
- Running adapter workflows.

Documentation:

- [docs/cli.md](docs/cli.md)
- [packages/cli](packages/cli)

## Configuration EN

Configuration is environment-driven. Development defaults are local only and must not be reused as production secrets.

| Variable | Default | Description |
| --- | --- | --- |
| `AGENTNET_ENV` | `development` | Environment name. |
| `LOG_LEVEL` | `INFO` | Log level. |
| `DATABASE_URL` | `postgresql+asyncpg://agentnet:agentnet@localhost:5432/agentnet` | PostgreSQL connection. |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis connection. |
| `MAX_PAYLOAD_BYTES` | `1048576` | Maximum request payload size. |
| `WS_HEARTBEAT_INTERVAL_S` | `15` | Agent heartbeat interval. |
| `WS_HEARTBEAT_TIMEOUT_S` | `45` | Heartbeat timeout. |
| `WS_MAX_CONNECTIONS_PER_AGENT` | `3` | Maximum WebSocket connections per agent. |
| `RATE_LIMIT_WINDOW_S` | `60` | Rate limit window. |
| `RATE_LIMIT_GLOBAL_MAX` | `1000` | Global rate limit. |
| `RATE_LIMIT_USER_MAX` | `300` | Per-user rate limit. |
| `RATE_LIMIT_AGENT_MAX` | `200` | Per-agent rate limit. |
| `RATE_LIMIT_IP_MAX` | `100` | Per-IP rate limit. |
| `TASK_MAX_RUNTIME_S` | `600` | Maximum task runtime. |
| `TASK_LEASE_DURATION_S` | `60` | Task lease duration. |
| `TIMEOUT_WORKER_INTERVAL_S` | `30` | Timeout worker interval. |
| `SESSION_COOKIE_NAME` | `agentnet_session` | Dashboard session cookie name. |
| `CSRF_COOKIE_NAME` | `agentnet_csrf` | Dashboard CSRF cookie name. |
| `SESSION_SECURE_COOKIE` | `false` | Must be `true` for production HTTPS. |
| `SESSION_USER_LIFETIME_DAYS` | `30` | User session absolute lifetime. |
| `SESSION_ADMIN_LIFETIME_DAYS` | `7` | Admin session absolute lifetime. |
| `SESSION_USER_IDLE_HOURS` | `24` | User idle timeout. |
| `SESSION_ADMIN_IDLE_HOURS` | `2` | Admin idle timeout. |
| `SESSION_STEP_UP_DURATION_MINUTES` | `10` | Step-up validity duration. |

Production configuration template:

- [infra/.env.production.example](infra/.env.production.example)

Do not commit:

- `.env.production`
- Real tokens
- Real API keys
- Database passwords
- Private keys
- Production connection strings

## Security Model EN

AgentNet is built around explicit failure, credential hashing, backend-enforced permissions, and auditability.

### Implemented Security Controls

- API keys are hashed at rest.
- Agent tokens are hashed at rest.
- Dashboard sessions store only hashes.
- CSRF tokens store only hashes.
- Dashboard session cookies are HttpOnly.
- Production cookie configuration supports `Secure` and `SameSite=Lax`.
- `admin` and `super_admin` permissions are separated.
- High-risk operations require step-up authentication.
- System health responses are redacted.
- Rate limiter failure is fail-closed.
- Redis/PostgreSQL dependency failures must not silently succeed.
- Key reads and mutations write audit logs.
- UI masks token-like text consistently.

### Contributor Rules

Production paths must not introduce:

- Automatic fallback to mock, fake, memory-only, or silent mode when dependencies are missing.
- Success placeholders for unimplemented features.
- Silent allow behavior when Redis, PostgreSQL, rate limiter, session store, CSRF validation, or adapter runner fails.
- Raw secrets in logs, screenshots, reports, frontend bundles, or audit records.
- API key storage in the browser.
- System pages displaying connection strings, full environment variables, or secrets.

Allowed exceptions:

- Test-only fakes in explicit test paths.
- Swallowing secondary cleanup errors during resource cleanup.
- Idempotent no-op for already completed ack/revoke behavior.

Security documentation:

- [docs/security-model.md](docs/security-model.md)
- [docs/dashboard-security.md](docs/dashboard-security.md)
- [docs/secrets-rotation.md](docs/secrets-rotation.md)

## Testing and Verification EN

### Backend Tests

Run all backend tests:

```bash
python -m pytest apps/api -q
```

Run Dashboard-specific backend tests:

```bash
python -m pytest ^
  apps/api/tests/test_phase_web_2_session.py ^
  apps/api/tests/test_phase_web_3_rbac.py ^
  apps/api/tests/test_phase_web_4_user_api.py ^
  apps/api/tests/test_phase_web_5_admin_api.py ^
  -q
```

If you use Bash, replace `^` with `\`, or run the command on one line.

### Frontend Tests

```bash
cd apps/web
npm test
npm run typecheck
```

Latest verification:

```text
18 test files passed
167 tests passed
typecheck passed
```

### Full Project Tests

```bash
python -m pytest -q
```

Module-level examples:

```bash
python -m pytest apps/api -q
python -m pytest packages/python-sdk -q
python -m pytest packages/cli -q
python -m pytest adapters/openclaw -q
```

### Browser End-to-End Check

The latest real browser check used:

- Docker PostgreSQL.
- Docker Redis.
- Real FastAPI backend.
- Real Vite frontend.
- Real browser automation.
- Real Dashboard login.
- Real admin page access.
- Real admin task expire operation.
- Database task status verification.
- Audit log verification.

### Real OpenClaw Tests

Real OpenClaw test report:

- [tests/real_openclaw/TEST_REPORT.md](tests/real_openclaw/TEST_REPORT.md)

The report covers failure paths, safety boundaries, stability, approval chain, offline/idempotency, and write pressure tests.

## Production Readiness Boundary

The current version is suitable for controlled internal testing, internal pilots, and staging-like validation. It is not a no-ops one-click public production SaaS.

Before public production, complete or re-verify:

- Real-domain HTTPS/WSS deployment.
- `SESSION_SECURE_COOKIE=true`.
- Production database and Redis credentials.
- Secret manager integration.
- API key and Agent token rotation procedures.
- Database backup and restore drill.
- Monitoring dashboards and alerts.
- Rate limits sized for real traffic.
- Longer-duration stability tests.
- Redis/PostgreSQL/API/worker fault injection.
- Release rollback procedure.
- Web build served by production nginx or an equivalent reverse proxy.

Production documentation:

- [docs/production-closeout.md](docs/production-closeout.md)
- [docs/production-deploy.md](docs/production-deploy.md)
- [docs/production-checklist.md](docs/production-checklist.md)
- [docs/ci-cd.md](docs/ci-cd.md)
- [docs/observability.md](docs/observability.md)
- [docs/backup-restore.md](docs/backup-restore.md)
- [docs/secrets-rotation.md](docs/secrets-rotation.md)
- [docs/dashboard-deploy.md](docs/dashboard-deploy.md)

## Operations EN

### Backup and Restore

Backup and restore scripts/docs:

- [scripts/backup](scripts/backup)
- [scripts/backup/README.md](scripts/backup/README.md)
- [docs/backup-restore.md](docs/backup-restore.md)

Requirements:

- Backups must be verified through restore drills.
- After restore, verify API health, database integrity, and key business paths.
- Production data backup files must not be committed to the repository.

### Secret Rotation

Documentation:

- [docs/secrets-rotation.md](docs/secrets-rotation.md)

Rotation scope:

- API keys.
- Agent tokens.
- Dashboard sessions.
- Database credentials.
- Redis credentials.
- Deployment secrets.

### Observability

The API exposes:

```text
GET /metrics
```

Documentation:

- [docs/observability.md](docs/observability.md)

Recommended alert areas:

- API 5xx rate.
- Request latency.
- Redis availability.
- PostgreSQL availability.
- WebSocket connection count.
- Retry backlog.
- Pending queue length.
- Timeout worker last run.
- Failed/expired task rate.
- Audit export event.

### nginx

nginx config and documentation:

- [infra/nginx/README.md](infra/nginx/README.md)
- [infra/nginx/agentnet.conf](infra/nginx/agentnet.conf)

Production nginx should:

- Proxy `/v1/*` to the API.
- Serve Dashboard build artifacts.
- Configure SPA fallback for `/app/*` and `/admin/*`.
- Restrict `/metrics` exposure.
- Set security response headers.

## Documentation Index EN

| Document | Description |
| --- | --- |
| [docs/quickstart.md](docs/quickstart.md) | Quick start guide. |
| [docs/architecture.md](docs/architecture.md) | System architecture. |
| [docs/protocol.md](docs/protocol.md) | Agent Relay Protocol. |
| [docs/security-model.md](docs/security-model.md) | Core security model. |
| [docs/sdk-python.md](docs/sdk-python.md) | Python SDK. |
| [docs/cli.md](docs/cli.md) | CLI. |
| [docs/openclaw-adapter.md](docs/openclaw-adapter.md) | OpenClaw Adapter. |
| [docs/openapi.md](docs/openapi.md) | OpenAPI documentation. |
| [docs/api-examples.md](docs/api-examples.md) | API examples. |
| [docs/dashboard-rbac.md](docs/dashboard-rbac.md) | Dashboard RBAC. |
| [docs/dashboard-security.md](docs/dashboard-security.md) | Dashboard security model. |
| [docs/dashboard-deploy.md](docs/dashboard-deploy.md) | Dashboard deployment. |
| [docs/production-deploy.md](docs/production-deploy.md) | Production deployment. |
| [docs/production-checklist.md](docs/production-checklist.md) | Production checklist. |
| [docs/ci-cd.md](docs/ci-cd.md) | CI/CD. |
| [docs/backup-restore.md](docs/backup-restore.md) | Backup and restore. |
| [docs/secrets-rotation.md](docs/secrets-rotation.md) | Secret rotation. |
| [docs/observability.md](docs/observability.md) | Observability and alerts. |
| [DEVELOPER_README.md](DEVELOPER_README.md) | Developer maintenance guide. |

## Development Standards

This project explicitly rejects “fallback success” behavior in production paths.

Every important phase must include:

- File deliverables.
- Automated tests or executable verification commands.
- Failure-path validation.
- Permission and security validation.
- Documentation updates.
- Real code review, not only test result review.

## Roadmap EN

Completed or substantially implemented:

- Phase 0: Protocol and engineering skeleton.
- Phase 1: Agent Registry, users, API keys, agent tokens.
- Phase 2: WebSocket presence, heartbeat, session resume.
- Phase 3: Task and message storage.
- Phase 4: Relay routing and delivery tracking.
- Phase 5: Connection policy.
- Phase 6: Task result, progress, approval.
- Phase 7: Python SDK.
- Phase 8: CLI.
- Phase 9: OpenClaw Adapter.
- Phase 10: Hardening, rate limiting, timeouts, audit logs.
- Phase 11: CI/CD, production templates, OpenAPI, backup/restore, observability.
- Dashboard Web: session auth, RBAC, user API, admin API, frontend pages, real browser smoke.

Recommended next round:

- Complete HTTPS/WSS staging deployment on a real domain.
- Add multi-hour WebSocket and Dashboard E2E stability tests.
- Add fault injection for Redis, PostgreSQL, API restart, and worker crash.
- If audit export volume grows, add async export and stricter export limits.
- If low-risk `admin` operations expand, split into finer-grained permissions.
- If enterprise users are expected, integrate OIDC/SSO.
- Add formal release tags, rollback playbooks, and release drill records.

## License EN

No `LICENSE` file was detected in this repository. Add an explicit license before external distribution or open-source release.

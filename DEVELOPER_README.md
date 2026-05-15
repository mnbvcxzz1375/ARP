# AgentNet Developer README

这份文档面向项目开发者和维护者，目标是让你能快速理解 AgentNet 的工程结构、核心业务流、测试策略、迁移方式和扩展边界。

如果 `README.md` 回答的是“用户怎么用”，这份文档回答的是“我们怎么继续把它做稳、做大、做对”。

## 项目目标

AgentNet / Agent Relay Platform 的目标是构建一个中心化 Agent 通信平台：

- 为 Agent 分配不可枚举的 Agent Number。
- 为不同用户、机器、框架中的 Agent 提供统一通信协议。
- 支持异步任务投递、状态管理、离线队列、ack、重试和幂等。
- 支持跨用户安全策略和 Human-in-the-loop approval。
- 支持 Adapter 插件化，把 OpenClaw、MCP 等外部框架接入平台。
- 保留未来 E2EE、多 Relay 节点、多安全模式协商的协议空间。

重要的产品边界：

- 不做去中心化。
- 不做 gas、链上结算。
- 不做 Dashboard。
- 不假装实现 E2EE。
- 不使用生产 mock fallback。
- 不用“最小验收”替代完整验收。

## 当前实现状态

项目已经从初始 Phase 0 骨架推进到 Phase 10 MVP 能力：

| Phase | 主题 | 当前状态 |
|---:|---|---|
| 0 | 协议与工程骨架 | 已实现 |
| 1 | Agent Registry | 已实现 |
| 2 | WebSocket Presence | 已实现 |
| 3 | Task + Message Storage | 已实现 |
| 4 | Relay Routing | 已实现 |
| 5 | Connection Policy | 已实现 |
| 6 | Task Result / Progress / Approval | 已实现 |
| 7 | Python SDK | 已实现 |
| 8 | CLI | 已实现 |
| 9 | OpenClaw Adapter | 已实现 |
| 10 | Hardening | 已实现 |

“已实现”在这里指 MVP 级完整链路，不代表生产商用完备。

## 设计硬约束

### 1. 不写兜底成功

项目要求“显式失败”，尤其是安全、路由、执行、限流相关代码。

不允许：

```python
try:
    do_security_check()
except Exception:
    return allow()
```

推荐：

```python
try:
    do_security_check()
except Exception as exc:
    raise DomainException(ErrorCode.INTERNAL_ERROR, "Security check unavailable", status_code=503)
```

允许的例外：

- 清理资源时吞掉二次异常，例如关闭 WebSocket、取消 task。
- 幂等 ack 未找到消息时返回 no-op。
- 测试专用 fake runner，但必须只存在于测试路径或显式 test 命名中。

### 2. 不把 mock 当生产实现

OpenClaw runner 如果找不到真实 binary，必须抛错。不能自动切到 fake runner。

### 3. API 和 SDK 契约必须跨包测试

只测 API 自己或 SDK 自己不够。关键协议点必须有 contract tests：

- REST `Authorization: Bearer`。
- WebSocket agent token 认证。
- `task.request` 的顶层 `task_id`。
- `session.resume` payload。
- `from_agent_number` 多发送方选择。
- 幂等范围。
- 跨用户数据隔离。

### 4. schema、model、migration 必须一致

任何数据库约束变化，都要同步：

- SQLAlchemy model。
- Alembic migration。
- 服务层查询语义。
- 测试。

典型例子：`Task.idempotency_key` 的唯一范围必须是：

```text
(created_by, assigned_to, idempotency_key)
```

不能退回全局唯一。

## Monorepo 结构

```text
apps/api
  FastAPI backend、SQLAlchemy models、Alembic migrations、workers、routers、services。

packages/python-sdk
  同步 REST Client、WebSocket Agent runtime、TaskContext、SessionStore、IdempotencyCache。

packages/cli
  agentnet CLI，封装登录、agent 管理、task 管理、approval 管理、agent connect。

packages/protocol
  JSON Schema 文件。用于协议说明和跨语言客户端生成基础。

adapters/base
  AdapterInterface 和 AdapterContext。

adapters/openclaw
  OpenClaw CLI adapter，包含安全检查、runner、配置和测试。

adapters/mcp
  MCP adapter 预留。

infra
  Docker Compose 和本地基础设施配置。

docs
  主题文档。
```

## API 应用结构

### 入口

```text
apps/api/app/main.py
```

负责：

- 创建 FastAPI app。
- 配置 logging。
- 注册 DomainException handler。
- 注册 rate limit middleware。
- 注册 routers。
- 启动和关闭后台 workers。
- 启动 WebSocket connection cleanup loop。

### 配置

```text
apps/api/app/config.py
```

使用 `pydantic-settings`，读取 `.env` 和环境变量。

关键配置：

- `DATABASE_URL`
- `REDIS_URL`
- `MAX_PAYLOAD_BYTES`
- `WS_HEARTBEAT_INTERVAL_S`
- `WS_HEARTBEAT_TIMEOUT_S`
- `WS_MAX_CONNECTIONS_PER_AGENT`
- `RATE_LIMIT_*`
- `TASK_MAX_RUNTIME_S`
- `TASK_LEASE_DURATION_S`
- `TIMEOUT_WORKER_INTERVAL_S`

### 数据库

```text
apps/api/app/database.py
apps/api/migrations
```

技术栈：

- SQLAlchemy async。
- asyncpg。
- Alembic。

本地默认数据库：

```text
postgresql+asyncpg://agentnet:agentnet@localhost:5432/agentnet
```

### Redis

```text
apps/api/app/redis.py
apps/api/app/services/session_service.py
apps/api/app/services/rate_limit_service.py
```

Redis 用途：

- WebSocket session pending queue。
- 离线消息恢复。
- rate limit sliding window。

当前 Redis 失败策略：

- Rate limit: fail-closed，返回 503。
- Pending queue: 不应该静默伪造成功。

## 核心模型

### User

文件：

```text
apps/api/app/models/user.py
```

代表平台用户，拥有 API keys 和 agents。

### ApiKey

文件：

```text
apps/api/app/models/api_key.py
```

关键点：

- 明文 API key 只在创建时返回。
- 数据库存 `key_hash`。
- 支持 revoke。
- `key_prefix` 用于展示和排障。

### Agent

文件：

```text
apps/api/app/models/agent.py
```

关键字段：

- `agent_number`
- `owner_id`
- `name`
- `runtime`
- `capabilities`
- `status`
- `inbound_policy`
- `discoverable`

### AgentToken

文件：

```text
apps/api/app/models/agent_token.py
```

用于 WebSocket Agent 认证。

关键点：

- 明文 token 只在创建或 rotate 时返回。
- 数据库存 hash。
- 支持 revoke 和 expires_at。

### Task

文件：

```text
apps/api/app/models/task.py
```

关键字段：

- `id`
- `idempotency_key`
- `created_by`
- `assigned_to`
- `status`
- `message_id`
- `lease_agent_id`
- `lease_expires_at`
- `last_progress_at`
- `last_heartbeat_at`
- `result`
- `error_message`

关键约束：

```text
UniqueConstraint("created_by", "assigned_to", "idempotency_key")
```

### Message

文件：

```text
apps/api/app/models/message.py
```

负责记录 task.request 等消息，包含：

- `message_id`
- `task_id`
- `type`
- `delivery_status`
- `retry_count`
- `max_retries`
- `next_retry_at`
- `ttl_seconds`
- `content`

### Approval

文件：

```text
apps/api/app/models/approval.py
```

用于 Human-in-the-loop。

关键字段：

- `task_id`
- `agent_id`
- `status`
- `risk_level`
- `action_kind`
- `action_preview`
- `reason`
- `expires_at`
- `decided_at`

### AuditLog

文件：

```text
apps/api/app/models/audit_log.py
```

记录关键事件：

- task created / delivered / state transition。
- approval created / accepted / rejected / expired。
- websocket connected / disconnected。
- connection request / accept / reject。

## 主要服务层

### auth.py

```text
apps/api/app/services/auth.py
```

负责 REST API 认证。

支持：

- `Authorization: Bearer ak_...`
- `X-API-Key: ak_...`

注意：这里只认证用户 API key，不认证 Agent token。

### agent_service.py

负责 Agent CRUD、Agent Number 创建、token 创建和轮换。

### task_service.py

负责：

- 创建任务。
- 幂等查询。
- 任务状态机。
- lease 创建和刷新。
- progress。
- result。
- fail。
- approval request。

创建任务的关键顺序：

1. Resolve target agent。
2. 检查 `(from_agent_id, to_agent_id, idempotency_key)`。
3. 执行 connection policy。
4. 创建 Task。
5. 创建 Message。
6. 写 audit。
7. 调用 routing service。
8. 更新 delivery status。

### routing_service.py

负责：

- 在线投递。
- 离线入队。
- pending 消息重连投递。
- ack。
- retry。
- TTL expire。

注意：

- 离线队列当前使用 agent_id queue。
- session.resume queue 使用 session_id。
- deliver_pending_on_connect 会同时检查 session_id queue 和 agent_id queue 并按 message_id 去重。

### session_service.py

负责 Redis pending queue：

- `store_pending_message`
- `get_pending_messages`
- `ack_message`
- `clear_session`
- `has_pending_messages`

`ack_message` 使用 Lua 脚本做原子 read-filter-rewrite，避免 delete 后 crash 造成整队丢失。

### connection_service.py

负责 inbound policy：

- `private`
- `contacts_only`
- `request_approval`
- `public`

同 owner 的 Agent 默认允许通信。

### approval_service.py

负责：

- 创建 approval。
- accept。
- reject。
- expire stale approvals。
- 按 owner 过滤 approval list。

### rate_limit_service.py

负责 Redis sliding window 限流。

维度：

- user
- agent
- IP
- global

安全策略：

- Redis 不可用时抛 `DomainException(INTERNAL_ERROR, 503)`。
- 不 fail-open。

## WebSocket 流程

入口：

```text
apps/api/app/routers/ws.py
```

管理器：

```text
apps/api/app/websocket/manager.py
```

消息处理：

```text
apps/api/app/websocket/handlers.py
apps/api/app/websocket/protocol.py
```

连接流程：

1. 客户端连接 `/v1/ws?session_id=...`。
2. 服务端读取 `Authorization: Bearer agt_sk_...`。
3. 服务端认证 Agent token。
4. rate limit 检查。
5. connection manager 注册连接。
6. Agent status 置为 online。
7. 投递 pending messages。
8. 返回 `session.resume_result`。
9. 持续处理 heartbeat、ack、task.*、approval.* 等消息。
10. 断开时 unregister，Agent status 置为 offline。

SDK 启动时还会主动发送：

```json
{
  "type": "session.resume",
  "payload": {
    "session_id": "...",
    "last_message_id": "..."
  }
}
```

## Python SDK

位置：

```text
packages/python-sdk/agentnet
```

### Client

文件：

```text
packages/python-sdk/agentnet/client.py
```

同步 REST client。

支持：

- create/list/get/rotate/delete agent。
- create/get/list task。
- task messages。
- task progress。
- list/accept/reject approval。

### Agent

文件：

```text
packages/python-sdk/agentnet/agent.py
```

负责：

- 从环境变量读取配置。
- 创建 SessionStore。
- 创建 AgentWebSocket。
- 注册 task handler。
- 调用用户 handler。
- handler 异常时上报 task failed。

### AgentWebSocket

文件：

```text
packages/python-sdk/agentnet/websocket.py
```

负责：

- WebSocket 连接。
- Authorization header。
- session_id。
- reconnect backoff。
- heartbeat。
- task heartbeat。
- session.resume。
- auto ack。
- message idempotency。

### SessionStore

文件：

```text
packages/python-sdk/agentnet/session_store.py
```

本地 JSON 文件，持久化：

- `session_id`
- `last_message_id`
- `running_tasks`

### TaskContext

文件：

```text
packages/python-sdk/agentnet/task.py
```

给用户 task handler 使用，支持：

- `accept`
- `progress`
- `result`
- `fail`
- `request_approval`
- `heartbeat`

## CLI

位置：

```text
packages/cli/agentnet_cli
```

入口：

```text
packages/cli/agentnet_cli/main.py
```

命令：

```text
agentnet login
agentnet agent create/list/get/rotate-token
agentnet connect
agentnet task send/get/list/logs
agentnet approve list/accept/reject
```

配置：

```text
~/.agentnet/config.json
```

安全注意：

- CLI 会保存 API key 和 agent token。
- Windows / Linux / macOS 权限处理不同，后续生产化要补平台级密钥存储。
- 高风险 approval 默认要求确认。

## OpenClaw Adapter

位置：

```text
adapters/openclaw
```

核心文件：

- `adapter.py`: AdapterInterface 实现。
- `runner.py`: 子进程执行和输出流。
- `safety.py`: 路径、命令、环境变量安全检查。
- `config.py`: Pydantic 配置。

关键安全约束：

- 不存在 OpenClaw binary 时显式失败。
- 不使用 mock fallback。
- `asyncio.create_subprocess_exec`，不使用 shell string。
- 工作目录必须经过 allow/deny path 校验。
- 检查路径穿越。
- 敏感环境变量剥离。
- 输出截断。
- 高风险命令可触发 approval。

## 数据库迁移

进入 API 目录：

```powershell
cd apps/api
```

查看当前 revision：

```powershell
alembic current
```

升级：

```powershell
alembic upgrade head
```

降级一个版本：

```powershell
alembic downgrade -1
```

创建新迁移：

```powershell
alembic revision -m "describe_change"
```

注意：

- 不要只改 model 不写 migration。
- 不要只改 migration 不改 model。
- 约束命名要稳定。
- downgrade 至少要能表达反向操作。

## 本地开发流程

### 1. 安装依赖

```powershell
python -m pip install -e "apps/api[test]"
python -m pip install -e packages/python-sdk
python -m pip install -e packages/cli
python -m pip install -e adapters/base
python -m pip install -e adapters/openclaw
```

### 2. 启动基础设施

```powershell
docker compose -f infra/docker-compose.yml -f infra/docker-compose.dev.yml up --build
```

### 3. 运行 API

如果不用 Docker 启动 API，也可以本地运行：

```powershell
cd apps/api
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

### 4. 跑测试

根目录：

```powershell
python -m pytest -q
```

按模块：

```powershell
python -m pytest apps/api -q
python -m pytest packages/python-sdk -q
python -m pytest packages/cli -q
python -m pytest adapters/openclaw -q
```

指定契约测试：

```powershell
python -m pytest apps/api/tests/test_protocol_contract.py -q
```

检查收集情况：

```powershell
python -m pytest --collect-only -q
```

## 测试分层

### API tests

位置：

```text
apps/api/tests
```

覆盖：

- health。
- errors。
- protocol。
- schema files。
- Redis。
- Agent Registry。
- WebSocket session service。
- Task / Message。
- Routing。
- Connection Policy。
- Approval。
- Hardening。
- API/SDK protocol contract。

### SDK tests

位置：

```text
packages/python-sdk/tests
```

覆盖：

- Client。
- Agent。
- WebSocket。
- TaskContext。
- SessionStore。
- IdempotencyCache。

### CLI tests

位置：

```text
packages/cli/tests
```

覆盖：

- ConfigManager。
- CLI help。
- version。
- 关键 option 暴露。

### Adapter tests

位置：

```text
adapters/openclaw/tests
```

覆盖：

- path safety。
- env sanitization。
- command review。
- output truncation。
- missing binary fail-fast。
- existing binary execution。
- config validation。

## 代码审查清单

提交前建议逐项看：

- API 和 SDK 的字段是否一致。
- REST 认证和 SDK headers 是否一致。
- WebSocket envelope 是否和 SDK handler 一致。
- task_id 是否在顶层 envelope。
- owner_id 是否被用于跨用户隔离。
- approval list 和 accept/reject 是否都做所有权校验。
- idempotency 查询范围是否仍是 `(from_agent, to_agent, key)`。
- migration 是否和 model 一致。
- Redis 错误是否显式失败。
- 是否新增了静默 fallback。
- 是否把 token 写入日志。
- 是否新增了未被 pytest 收集的测试类。
- 是否补了跨包契约测试。

## 常见回归点

### 测试类没有被收集

pytest 默认只收集以 `Test` 开头的测试类。

错误：

```python
class TaskIdDispatchContract:
    ...
```

正确：

```python
class TestTaskIdDispatchContract:
    ...
```

### SDK 和 API 认证漂移

如果 SDK 改 header，API 也要改；如果 API 改认证方式，SDK 和 CLI 也要改。

当前约定：

```text
REST: Authorization: Bearer ak_...
WS:   Authorization: Bearer agt_sk_...
```

### from_agent_number 只在 API 实现

多 Agent 用户语义要求 SDK 和 CLI 也暴露发送方选择。

检查点：

- `apps/api/app/schemas/task.py`
- `apps/api/app/routers/tasks.py`
- `packages/python-sdk/agentnet/client.py`
- `packages/cli/agentnet_cli/commands/task_cmd.py`
- tests。

### OpenClaw runner 未实际执行测试

只测 missing binary 不够。需要测一个真实可执行文件路径，确保 subprocess 路径能走通。

### session.resume 只测 payload 结构

更完整的测试应该覆盖：

- SDK 持久化 session_id。
- 重启后复用 session_id。
- last_message_id 发送。
- 服务端按 after_message_id 返回 pending。
- ack 后 Redis 队列移除。

## 发布前建议补齐

这不是当前 MVP 必须项，但进入真实用户试用前建议做：

- GitHub Actions 或其他 CI。
- Ruff / mypy / pyright。
- Alembic migration smoke test。
- Docker Compose health smoke test。
- 真实 WebSocket end-to-end integration test。
- OpenAPI 文档导出。
- API examples collection。
- 生产 `.env.example`。
- Secret 管理方案。
- structured logging sink。
- metrics。
- alerting。
- backup and restore。
- load test。
- chaos test for Redis/Postgres temporary failure。

## 排障指南

### `python -m pytest` 不能从根目录跑

检查：

- 根目录 `pyproject.toml` 是否包含 `testpaths`。
- 根目录 `conftest.py` 是否把 subproject roots 加入 `sys.path`。
- 是否有多个顶层 `tests` 包冲突。

### API 连接不上数据库

检查：

```powershell
docker compose -f infra/docker-compose.yml ps
```

检查 `DATABASE_URL` 是否指向正确 host：

- Docker 内部 API 用 `postgres`。
- 本机 uvicorn 用 `localhost`。

### Redis 报错导致 API 503

这是预期的 fail-closed 行为。检查 Redis：

```powershell
docker compose -f infra/docker-compose.yml logs redis
```

### WebSocket 连接后马上断开

检查：

- token 是否是 `agt_sk_...`。
- token 是否已 rotate 或 revoke。
- Authorization header 是否正确。
- 单 Agent 是否超过最大连接数。
- 服务端日志是否有 `INVALID_TOKEN`。

### Task 创建成功但 Agent 没收到

检查：

- 目标 Agent 是否 online。
- `assigned_to` 是否是 agent_number，不是 agent_id。
- Agent 是否连接到同一个 API 实例。
- Redis pending queue 是否可用。
- message delivery status 是否是 `pending`、`delivered`、`acked` 或 `failed`。

### Approval accept/reject 返回 404

常见原因：

- 当前 API key 用户不拥有该 approval 对应 Agent。
- approval_id 错误。
- approval 已过期或不存在。

### OpenClaw Adapter 运行失败

检查：

- OpenClaw binary 是否存在。
- `command` 是否是可执行文件或 PATH 中可找到的命令。
- `working_dir` 是否在 allow_paths 内。
- 是否命中了 deny_paths。
- 是否有敏感环境变量被剥离后导致命令缺少必要配置。
- 是否需要 approval handler。

## 安全注意事项

### Token

- API key 和 Agent token 都只保存 hash。
- 明文只在创建或 rotate 时返回。
- 不要把 token 放在日志里。
- 不要把 token commit 到仓库。
- WebSocket 推荐 header token，不推荐 query token。

### 日志

结构化日志应优先包含：

- `trace_id`
- `task_id`
- `message_id`
- `delivery_status`
- `error_code`

不要记录：

- API key 明文。
- Agent token 明文。
- 用户 payload 中的 secret。
- 完整环境变量。

### Adapter

Adapter 是高风险边界。任何执行本地命令、读写路径、传递环境变量的代码都必须按安全边界审查。

最低要求：

- 不使用 shell string。
- 不使用生产 fallback。
- 不默认透传全部环境变量。
- 不允许路径穿越。
- 不允许绕过 approval。

## 未来扩展建议

### MCP Adapter

建议沿用 `AdapterInterface`：

```python
class AdapterInterface(Protocol):
    async def start(self) -> None: ...
    async def stop(self) -> None: ...
    async def handle_task(self, context: AdapterContext, content: list[dict]) -> dict: ...
```

新增 MCP adapter 时应先补：

- 配置模型。
- fake MCP server tests。
- 安全策略。
- task payload schema。
- progress/result 映射。

### E2EE

当前只预留协议字段，不实现业务加密。

真正实现前需要设计：

- key agreement。
- sender/recipient key discovery。
- message encryption envelope。
- signature。
- replay protection。
- key rotation。
- multi-device。
- recovery。

在这些完成前，不能把 `e2ee` 描述为已支持。

### 多 Relay 节点

未来需要：

- Agent connection ownership registry。
- node discovery。
- distributed pending queue。
- consistent routing。
- cross-node ack。
- load balancing。
- health and failover。

### Dashboard

当前明确不做。但如果未来要做，建议只作为 API consumer，不要把业务逻辑塞进前端。

## 维护命令速查

```powershell
# 全量测试
python -m pytest -q

# API 测试
python -m pytest apps/api -q

# SDK 测试
python -m pytest packages/python-sdk -q

# CLI 测试
python -m pytest packages/cli -q

# OpenClaw adapter 测试
python -m pytest adapters/openclaw -q

# 协议契约测试
python -m pytest apps/api/tests/test_protocol_contract.py -q

# 测试收集检查
python -m pytest --collect-only -q

# Docker 配置检查
docker compose -f infra/docker-compose.yml -f infra/docker-compose.dev.yml config

# 启动本地栈
docker compose -f infra/docker-compose.yml -f infra/docker-compose.dev.yml up --build

# Alembic 当前版本
cd apps/api
alembic current

# Alembic 升级
alembic upgrade head
```

## 当前重点质量结论

当前代码库已经具备较完整的 MVP 闭环：

- API、SDK、CLI、Adapter 都可测试。
- 根目录 pytest 已打通。
- 协议契约有测试锁定。
- 跨用户读取隔离已收紧。
- 幂等范围已按 Agent 对实现。
- Rate limit 已 fail-closed。
- OpenClaw 不再依赖生产 fallback。

仍建议下一轮强化：

- 真实 WebSocket API+SDK end-to-end 测试。
- 更完整的 session.resume 行为测试。
- CI。
- migration 从空库到 head 的 smoke test。
- OpenAPI examples。
- 生产部署文档。


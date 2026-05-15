下面是一份可以**直接复制给 Codex** 的开发计划。它已经把我们前面讨论的重点整合进去：中心化 Relay、Agent Number、跨用户请求安全、断线恢复、幂等、Human-in-the-loop、OpenClaw Adapter、MCP 适配预留、E2EE 预留，但**暂不做去中心化 / gas / 链上结算**。

技术选型上，MVP 先用 FastAPI + PostgreSQL + Redis Streams + 原生 WebSocket；FastAPI 官方支持 WebSocket 场景，适合先做双向通信闭环。MCP 暂时作为 Adapter 层而不是核心协议，因为 MCP 官方定位是让应用通过 JSON-RPC 连接工具、资源和上下文能力；你的核心协议仍然负责 agent 身份、路由、任务和权限。E2EE 先预留协议字段，后续用 Noise / libsodium 风格实现，不复刻 MTProto；Noise 官方本身就是构建加密协议的框架，支持认证、前向安全等能力。后续如果高频分布式消息需求变强，再从 Redis Streams 迁移到 NATS JetStream，因为 JetStream 官方强调其持久化、重放、复制和水平扩展能力。([FastAPI](https://fastapi.tiangolo.com/advanced/websockets/?utm_source=chatgpt.com))

------

下面是一版**完整可交给 Codex 的 AgentNet / Agent Relay Platform 开发计划 **

你可以直接把这份作为项目根文档，或者拆成多条 prompt 逐步喂给 Codex。

------

# AgentNet / Agent Relay Platform

## 0. 项目定位

构建一个中心化的 **Agent Relay Platform**，让不同用户、不同机器、不同框架里的 AI Agent 可以互相通信。

平台为每个 Agent 分配一个不可枚举的 **Agent Number**，并负责：

```text
1. Agent 身份注册
2. Agent Number 分配
3. Agent 在线状态管理
4. WebSocket 长连接
5. Agent-to-Agent 消息路由
6. Task 请求、进度、结果、失败状态管理
7. 跨用户 connection.request 审批
8. Human-in-the-loop 本地高风险操作审批
9. 离线消息排队
10. 断线重连与 session.resume
11. 幂等与重复消息去重
12. OpenClaw Adapter 原型
13. MCP Adapter 预留
14. E2EE 协议字段预留
```

第一版不做：

```text
1. 去中心化节点
2. gas 支付
3. 链上身份
4. 链上结算
5. marketplace
6. 复杂 billing
7. 完整 E2EE
8. 多方群组加密
9. 企业多组织权限系统
10. 完整 Dashboard
```

## 0.1 全局优化原则

以下原则适用于 Phase 0-10，后续每个 Phase 都必须按这些约束实现和验收：

```text
1. 安全性：
   - Token 支持生命周期、轮换、哈希存储和日志脱敏。
   - 高风险任务必须进入 Human-in-the-loop 审批，支持 CLI 展示、超时处理和策略化审批。
   - Adapter 默认最小环境变量、路径越权检测、敏感目录拒绝和危险命令审查。
   - E2EE 只预留协议字段，未来再接入多方加密或 Noise/libsodium 风格实现。

2. 可靠性：
   - 幂等性必须同时依赖数据库唯一约束和 SDK 本地缓存。
   - Task lease + task heartbeat 是任务可靠性的核心机制。
   - 离线队列、ack、retry backoff 和 session.resume 必须恢复未 ack 消息。
   - 失败必须显式暴露错误码，不允许静默吞错。

3. 扩展性：
   - Adapter 必须走统一接口，支持 OpenClaw / MCP / 未来扩展。
   - Agent Number 支持 region / namespace / random / checksum 扩展。
   - ARP Envelope 允许受控扩展字段，但外部输入仍必须先经过 Pydantic 校验。

4. 可审计性：
   - task / message / approval / adapter action 等关键动作必须写 audit_logs。
   - 结构化日志至少支持 trace_id、task_id、message_id、delivery_status、error_code。
   - 日志不得打印 secret、token、API key 或敏感 payload。

5. 客户端闭环：
   - SDK 自动 heartbeat、ack、session.resume、reconnect backoff 和重复消息去重。
   - CLI 必须能完成高风险审批展示和确认。
```

## 0.2 严格实现边界

```text
1. 严禁兜底代码：
   - 不允许用 fallback 逻辑掩盖缺失依赖、错误配置、协议错误或未实现能力。
   - 不允许捕获异常后返回看似成功的默认结果。
   - 不允许在生产路径中自动切换到 mock、fake、memory-only、best-effort 或 silent mode。
   - 未实现能力必须显式 raise DomainException，返回稳定错误码，例如 E2EE_NOT_IMPLEMENTED。
   - 测试 fake / mock runner 只能在明确命名的测试或 demo 模式中使用，必须通过显式参数启用，不能作为运行时兜底。

2. 不接受“最低验收”替代完整验收：
   - 每个 Phase 的验收必须覆盖该 Phase 声明的全部目标，而不是只满足 happy path。
   - 验收必须包含失败路径、安全边界、幂等/重试/超时等关键行为。
   - 若环境原因导致某项验收无法执行，必须明确记录阻塞原因和已完成的替代静态验证，不能宣称完整通过。

3. 占位模块规则：
   - 占位代码只能声明接口、类型、README、TODO 或显式 NotImplementedError。
   - 占位模块不得返回假成功、假数据或无声忽略输入。
   - 日志可以说明能力未实现，但不得替代错误返回。
```

------

# 1. 核心产品模型

## 1.1 AgentNet 是什么

AgentNet 是一个中心化 Agent 通信中转网络。

类比：

```text
Agent Number       类似手机号
Agent Token        类似设备密钥
Local Gateway      类似本地基站接入器
Relay Platform     类似通信运营商核心网
Task               类似一次任务请求
Connection Request 类似第一次加好友 / 授权通信
Approval Request   类似本地高风险操作确认
```

一句话：

> AgentNet 让 OpenClaw、本地 LLM、LangGraph、CrewAI、自研 Agent 等不同 Agent 能通过统一的 Agent Number 互相发现、请求任务、返回结果。

------

# 2. 技术栈

## 2.1 Backend

```text
Language: Python 3.11+
Framework: FastAPI
ASGI Server: Uvicorn
Database: PostgreSQL
ORM: SQLAlchemy 2.x async
Migration: Alembic
Cache / Queue: Redis
Redis Client: redis.asyncio
Message Queue MVP: Redis Streams
Validation: Pydantic v2
Testing: pytest + pytest-asyncio
Auth: API Key + Agent Token
```

## 2.2 SDK / CLI

```text
Python SDK package: agentnet
CLI package: agentnet-cli
CLI framework: Typer
WebSocket client: websockets
HTTP client: httpx
Local config: ~/.agentnet/config.yaml
Local session store: ~/.agentnet/sessions/
```

## 2.3 Adapter

```text
OpenClaw Adapter: subprocess CLI mode first
MCP Adapter: placeholder only in MVP
```

## 2.4 Infra

```text
Docker Compose
PostgreSQL
Redis
Local development first
```

------

# 3. Monorepo 结构

Codex 应创建以下目录结构：

```text
agentnet/
  apps/
    api/
      app/
        __init__.py
        main.py
        config.py
        database.py
        redis.py
        logging.py
        exceptions.py

        models/
          __init__.py
          user.py
          api_key.py
          agent.py
          gateway.py
          connection.py
          task.py
          message.py
          approval.py
          audit_log.py

        schemas/
          __init__.py
          common.py
          agent.py
          gateway.py
          task.py
          message.py
          connection.py
          approval.py
          error.py

        routers/
          __init__.py
          health.py
          agents.py
          gateways.py
          tasks.py
          messages.py
          connections.py
          approvals.py
          ws.py

        services/
          __init__.py
          auth_service.py
          api_key_service.py
          agent_service.py
          number_service.py
          gateway_service.py
          task_service.py
          message_service.py
          routing_service.py
          connection_service.py
          approval_service.py
          rate_limit_service.py
          audit_service.py
          session_service.py

        websocket/
          __init__.py
          manager.py
          protocol.py
          handlers.py

        workers/
          __init__.py
          retry_worker.py
          timeout_worker.py
          offline_delivery_worker.py

        protocol/
          __init__.py
          envelope.py
          constants.py
          validators.py

      migrations/
      tests/
        test_health.py
        test_protocol.py
        test_errors.py
        test_agents.py
        test_tasks.py
        test_websocket.py
        test_connection_policy.py
        test_idempotency.py
        test_session_resume.py
        test_approval.py

      Dockerfile
      pyproject.toml

    cli/
      agentnet_cli/
        __init__.py
        main.py
        config.py
        commands/
          login.py
          agent.py
          connect.py
          send.py
          task.py
          expose.py
      pyproject.toml

  packages/
    python-sdk/
      agentnet/
        __init__.py
        client.py
        agent.py
        task.py
        websocket.py
        types.py
        crypto.py
        session_store.py
        idempotency.py
      examples/
        echo_agent.py
        send_task.py
      pyproject.toml

    protocol/
      schemas/
        envelope.schema.json
        agent.schema.json
        task.schema.json
        message.schema.json
        connection.schema.json
        approval.schema.json
        error.schema.json

  adapters/
    openclaw/
      agentnet_openclaw/
        __init__.py
        adapter.py
        config.py
        safety.py
        runner.py
      examples/
        openclaw-agent.yaml
      README.md
      pyproject.toml

    mcp/
      README.md
      TODO.md

  infra/
    docker-compose.yml
    postgres/
    redis/

  docs/
    architecture.md
    protocol.md
    security-model.md
    quickstart.md
    sdk-python.md
    cli.md
    openclaw-adapter.md

  README.md
```

------

# 4. 核心概念

## 4.1 User

平台用户。

```json
{
  "id": "usr_01J...",
  "email": "andrew@example.com",
  "name": "Andrew",
  "plan": "free"
}
```

## 4.2 Agent

一个可寻址的通信节点。

```json
{
  "id": "agt_01J...",
  "agent_number": "AN-GLOBAL-QZ91TR-77",
  "owner_user_id": "usr_01J...",
  "name": "Andrew OpenClaw Agent",
  "runtime": "openclaw",
  "description": "Local OpenClaw coding agent",
  "status": "offline",
  "visibility": "private",
  "discoverable": false,
  "inbound_policy": "request_approval",
  "capabilities": ["code_analysis", "repo_summary"],
  "security_modes_supported": ["relay_visible"],
  "created_at": "..."
}
```

## 4.3 Agent Number

不要使用简单自增号码。

不要使用：

```text
AN-000001
AN-000002
```

MVP 使用不可枚举格式：

```text
AN-{REGION}-{RANDOM}-{SUFFIX}
```

示例：

```text
AN-GLOBAL-QZ91TR-77
AN-US-7K4P9Q-21
AN-CN-X8M2LA-04
```

要求：

```text
1. 全局唯一
2. 不暴露注册顺序
3. 不容易被扫描
4. 支持 region / namespace 扩展
5. 使用 secrets 或 uuid 生成随机部分
6. 数据库层 agent_number 唯一索引
```

`number_service.py` 需要实现：

```python
def generate_agent_number(region: str = "GLOBAL") -> str:
    ...
```

测试要求：

```text
生成 10,000 个 agent number 不重复。
```

------

# 5. Agent Relay Protocol v0.1

协议简称：

```text
ARP v0.1
```

所有 REST 创建的消息、WebSocket 双向消息、SDK 内部消息都应遵循统一 Envelope。

## 5.1 Envelope

```json
{
  "version": "arp-0.1",
  "message_id": "msg_01JABC",
  "request_id": "req_01JABC",
  "session_id": "sess_01JABC",
  "type": "task.request",
  "from": "agt_sender",
  "to": "agt_receiver",
  "task_id": "task_01JABC",
  "conversation_id": "conv_01JABC",
  "timestamp": "2026-05-14T12:00:00Z",
  "ttl_seconds": 600,
  "delivery": {
    "requires_ack": true,
    "idempotency_key": "idem_01JABC",
    "retry_count": 0
  },
  "security": {
    "mode": "relay_visible",
    "encryption": "none",
    "key_id": null
  },
  "limits": {
    "max_duration_seconds": 600,
    "max_steps": 20,
    "max_output_bytes": 1048576
  },
  "content": [
    {
      "mime": "text/plain",
      "text": "Please analyze this repository."
    }
  ],
  "metadata": {
    "trace_id": "trace_01JABC"
  }
}
```

## 5.2 E2EE 预留格式

MVP 只定义字段，不实现真正加密。

```json
{
  "version": "arp-0.1",
  "message_id": "msg_01JABC",
  "request_id": "req_01JABC",
  "session_id": "sess_01JABC",
  "type": "task.request",
  "from": "agt_sender",
  "to": "agt_receiver",
  "task_id": "task_01JABC",
  "timestamp": "2026-05-14T12:00:00Z",
  "security": {
    "mode": "e2ee",
    "encryption": "x25519-chacha20poly1305",
    "key_id": "key_01JABC",
    "nonce": "base64_nonce"
  },
  "encrypted_payload": "base64_ciphertext",
  "aad": {
    "from": "agt_sender",
    "to": "agt_receiver",
    "type": "task.request",
    "task_id": "task_01JABC"
  }
}
```

MVP 中，业务逻辑如果收到 `security.mode = e2ee`，返回：

```json
{
  "type": "error",
  "error": {
    "code": "E2EE_NOT_IMPLEMENTED",
    "message": "E2EE mode is reserved but not implemented in MVP.",
    "details": {}
  }
}
```

------

# 6. 消息类型

## 6.1 P0 必须支持

```text
presence.heartbeat

connection.request
connection.accepted
connection.rejected

session.resume
session.resume_result

task.request
task.accepted
task.rejected
task.progress
task.heartbeat
task.result
task.failed
task.cancelled

approval.request
approval.accepted
approval.rejected
approval.expired

ack
error
```

## 6.2 P1 后续支持

```text
message.chat
agent.status.changed
report.spam
sender.blocked
```

------

# 7. Task 状态机

必须支持状态：

```text
created
queued
delivered
accepted
running
awaiting_approval
completed
failed
cancelled
expired
rejected
```

允许状态转换：

```text
created -> queued
created -> delivered
queued -> delivered
delivered -> accepted
accepted -> running
running -> awaiting_approval
awaiting_approval -> running
awaiting_approval -> rejected
running -> completed
running -> failed
running -> cancelled
queued -> expired
delivered -> expired
running -> failed
```

非法转换必须抛出：

```text
INVALID_TASK_STATE_TRANSITION
```

------

# 8. Task Heartbeat / Task Lease

Agent 级别 heartbeat 不足够。需要任务级别 lease。

`tasks` 表需要字段：

```sql
last_progress_at TIMESTAMPTZ;
lease_expires_at TIMESTAMPTZ;
```

任务进入 `running` 时：

```text
last_progress_at = now()
lease_expires_at = now() + task_lease_seconds
```

默认：

```text
task_lease_seconds = 300
```

收到以下消息时刷新 lease：

```text
task.accepted
task.progress
task.heartbeat
```

如果 task 处于 `running`，并且超过 `lease_expires_at` 仍无更新：

```text
status = failed
error.code = TASK_LEASE_EXPIRED
```

新增错误码：

```text
TASK_LEASE_EXPIRED
```

------

# 9. 跨用户通信安全模型

## 9.1 inbound_policy

每个 agent 必须有：

```text
private
contacts_only
request_approval
public
```

默认：

```text
request_approval
```

行为：

```text
private:
  只允许同一 owner_user_id 下的 agent 调用。

contacts_only:
  只允许已授权 connection 的 agent 调用。

request_approval:
  陌生 agent 第一次请求时进入 connection.request 审批。

public:
  任何登录用户的 agent 都可以请求，但仍受限流、quota、TTL、max_steps 约束。
```

## 9.2 connection.request 流程

当 Agent A 第一次请求 Agent B，且 B 的 policy 为 `request_approval`：

```text
1. 不直接创建 task
2. 创建 connection_request
3. 向 B 的 gateway 投递 connection.request
4. B 接受后创建 connection grant
5. 后续 A 可以向 B 创建 task
```

请求：

```json
{
  "type": "connection.request",
  "from": "agt_sender",
  "to": "agt_receiver",
  "reason": "Request to use your OpenClaw agent for code analysis.",
  "requested_capabilities": ["code_analysis"],
  "requested_security_modes": ["relay_visible"]
}
```

接受：

```json
{
  "type": "connection.accepted",
  "from": "agt_receiver",
  "to": "agt_sender",
  "allowed_capabilities": ["code_analysis"],
  "expires_at": "2026-06-14T00:00:00Z",
  "preferred_security_mode": "relay_visible"
}
```

拒绝：

```json
{
  "type": "connection.rejected",
  "from": "agt_receiver",
  "to": "agt_sender",
  "reason": "not_allowed"
}
```

------

# 10. Security Mode 协商

创建 connection request 时，必须比较双方支持的安全模式。

Sender 请求：

```json
{
  "requested_security_modes": ["e2ee", "relay_visible"]
}
```

Receiver agent 有：

```json
{
  "security_modes_supported": ["relay_visible"]
}
```

平台计算：

```text
intersection(sender_requested_modes, receiver_supported_modes)
```

如果交集为空，拒绝：

```json
{
  "type": "error",
  "error": {
    "code": "SECURITY_MODE_NOT_SUPPORTED",
    "message": "No compatible security mode between sender and receiver.",
    "details": {}
  }
}
```

MVP 默认：

```text
relay_visible
```

E2EE 只预留，不实现。

------

# 11. Human-in-the-loop 审批

## 11.1 高风险操作

Adapter 遇到以下行为时，必须触发审批：

```text
shell_command
file_write
file_delete
network_request
access_sensitive_path
long_running_task
large_output
```

## 11.2 approval.request

```json
{
  "type": "approval.request",
  "task_id": "task_01JABC",
  "risk_level": "high",
  "action": {
    "kind": "shell_command",
    "preview": "rm -rf ./dist"
  },
  "reason": "OpenClaw wants to delete generated build output.",
  "expires_in_seconds": 120
}
```

## 11.3 CLI 展示

```text
Remote task requests local action:

Risk: high
Action: shell_command
Preview:
rm -rf ./dist

Allow? [y/N]
```

用户接受：

```json
{
  "type": "approval.accepted",
  "task_id": "task_01JABC"
}
```

用户拒绝：

```json
{
  "type": "approval.rejected",
  "task_id": "task_01JABC",
  "reason": "user_rejected"
}
```

------

# 12. 断线恢复与幂等

## 12.1 WebSocket 连接参数

Agent 连接：

```http
GET /v1/ws/agents/{agent_id}?session_id=sess_01J&last_seen_message_id=msg_01J
Authorization: Bearer <agent_token>
```

必须验证：

```text
1. agent exists
2. token hash matches
3. token not revoked
4. connection count within limit
```

成功后返回：

```json
{
  "type": "agent.connected",
  "agent_id": "agt_01J...",
  "session_id": "sess_01J...",
  "status": "online"
}
```

## 12.2 session.resume

重连后，SDK 立即发送：

```json
{
  "type": "session.resume",
  "agent_id": "agt_123",
  "session_id": "sess_123",
  "last_seen_message_id": "msg_456",
  "running_tasks": ["task_01JABC"]
}
```

服务端返回：

```json
{
  "type": "session.resume_result",
  "missed_messages": [],
  "tasks_to_reconcile": []
}
```

## 12.3 本地 Session Store

SDK 保存：

```text
~/.agentnet/sessions/{agent_id}/{task_id}.json
```

内容：

```json
{
  "task_id": "task_01JABC",
  "request_id": "req_01JABC",
  "idempotency_key": "idem_01JABC",
  "status": "running",
  "last_message_id": "msg_456",
  "local_session_ref": "openclaw_session_123",
  "updated_at": "2026-05-14T12:00:00Z"
}
```

## 12.4 幂等要求

所有 `task.request` 必须包含：

```text
request_id
idempotency_key
```

数据库层唯一约束：

```text
from_agent_id + to_agent_id + idempotency_key
```

服务端逻辑：

```text
如果同一个 from_agent_id + to_agent_id + idempotency_key 已存在 task：
  返回已有 task，不创建新 task。
```

SDK 逻辑：

```text
如果收到重复 message_id：
  自动 ack
  不重复执行 handler
```

------

# 13. 数据库 Schema

## 13.1 users

```sql
CREATE TABLE users (
  id TEXT PRIMARY KEY,
  email TEXT UNIQUE NOT NULL,
  name TEXT,
  plan TEXT DEFAULT 'free',
  created_at TIMESTAMPTZ DEFAULT now()
);
```

## 13.2 api_keys

```sql
CREATE TABLE api_keys (
  id TEXT PRIMARY KEY,
  owner_user_id TEXT NOT NULL REFERENCES users(id),
  name TEXT NOT NULL,
  key_hash TEXT NOT NULL,
  scopes JSONB DEFAULT '[]',
  last_used_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT now(),
  revoked_at TIMESTAMPTZ
);
```

## 13.3 agents

```sql
CREATE TABLE agents (
  id TEXT PRIMARY KEY,
  agent_number TEXT UNIQUE NOT NULL,
  owner_user_id TEXT NOT NULL REFERENCES users(id),
  name TEXT NOT NULL,
  runtime TEXT NOT NULL,
  description TEXT,
  visibility TEXT DEFAULT 'private',
  discoverable BOOLEAN DEFAULT false,
  inbound_policy TEXT DEFAULT 'request_approval',
  status TEXT DEFAULT 'offline',
  capabilities JSONB DEFAULT '[]',
  security_modes_supported JSONB DEFAULT '["relay_visible"]',
  metadata JSONB DEFAULT '{}',
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now()
);
```

Indexes:

```sql
CREATE INDEX idx_agents_owner ON agents(owner_user_id);
CREATE INDEX idx_agents_number ON agents(agent_number);
CREATE INDEX idx_agents_status ON agents(status);
CREATE INDEX idx_agents_discoverable ON agents(discoverable);
CREATE INDEX idx_agents_capabilities ON agents USING GIN(capabilities);
```

## 13.4 agent_tokens

```sql
CREATE TABLE agent_tokens (
  id TEXT PRIMARY KEY,
  agent_id TEXT NOT NULL REFERENCES agents(id),
  token_hash TEXT NOT NULL,
  name TEXT,
  last_used_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT now(),
  revoked_at TIMESTAMPTZ
);
```

## 13.5 gateways

```sql
CREATE TABLE gateways (
  id TEXT PRIMARY KEY,
  owner_user_id TEXT NOT NULL REFERENCES users(id),
  name TEXT NOT NULL,
  status TEXT DEFAULT 'offline',
  last_seen_at TIMESTAMPTZ,
  metadata JSONB DEFAULT '{}',
  created_at TIMESTAMPTZ DEFAULT now()
);
```

## 13.6 agent_gateway_bindings

```sql
CREATE TABLE agent_gateway_bindings (
  id TEXT PRIMARY KEY,
  agent_id TEXT NOT NULL REFERENCES agents(id),
  gateway_id TEXT NOT NULL REFERENCES gateways(id),
  local_endpoint TEXT,
  created_at TIMESTAMPTZ DEFAULT now(),
  UNIQUE(agent_id, gateway_id)
);
```

## 13.7 agent_connections

```sql
CREATE TABLE agent_connections (
  id TEXT PRIMARY KEY,
  from_agent_id TEXT NOT NULL REFERENCES agents(id),
  to_agent_id TEXT NOT NULL REFERENCES agents(id),
  status TEXT NOT NULL,
  allowed_capabilities JSONB DEFAULT '[]',
  preferred_security_mode TEXT DEFAULT 'relay_visible',
  expires_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now(),
  UNIQUE(from_agent_id, to_agent_id)
);
```

Connection status:

```text
pending
accepted
rejected
blocked
expired
```

## 13.8 tasks

```sql
CREATE TABLE tasks (
  id TEXT PRIMARY KEY,
  request_id TEXT NOT NULL,
  idempotency_key TEXT NOT NULL,
  from_agent_id TEXT REFERENCES agents(id),
  to_agent_id TEXT REFERENCES agents(id),
  status TEXT NOT NULL,
  title TEXT,
  timeout_seconds INTEGER DEFAULT 600,
  max_duration_seconds INTEGER DEFAULT 600,
  max_steps INTEGER DEFAULT 20,
  max_output_bytes INTEGER DEFAULT 1048576,
  last_progress_at TIMESTAMPTZ,
  lease_expires_at TIMESTAMPTZ,
  metadata JSONB DEFAULT '{}',
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now(),
  completed_at TIMESTAMPTZ,
  UNIQUE(from_agent_id, to_agent_id, idempotency_key)
);
```

## 13.9 messages

```sql
CREATE TABLE messages (
  id TEXT PRIMARY KEY,
  request_id TEXT,
  session_id TEXT,
  task_id TEXT REFERENCES tasks(id),
  type TEXT NOT NULL,
  from_agent_id TEXT REFERENCES agents(id),
  to_agent_id TEXT REFERENCES agents(id),
  payload JSONB NOT NULL,
  delivery_status TEXT DEFAULT 'created',
  retry_count INTEGER DEFAULT 0,
  created_at TIMESTAMPTZ DEFAULT now(),
  delivered_at TIMESTAMPTZ,
  acked_at TIMESTAMPTZ,
  expires_at TIMESTAMPTZ
);
```

Indexes:

```sql
CREATE INDEX idx_messages_task ON messages(task_id);
CREATE INDEX idx_messages_to_agent ON messages(to_agent_id);
CREATE INDEX idx_messages_created ON messages(created_at);
CREATE INDEX idx_messages_delivery ON messages(delivery_status);
```

## 13.10 approvals

```sql
CREATE TABLE approvals (
  id TEXT PRIMARY KEY,
  task_id TEXT NOT NULL REFERENCES tasks(id),
  agent_id TEXT NOT NULL REFERENCES agents(id),
  status TEXT NOT NULL,
  risk_level TEXT NOT NULL,
  action JSONB NOT NULL,
  reason TEXT,
  expires_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT now(),
  resolved_at TIMESTAMPTZ
);
```

## 13.11 audit_logs

```sql
CREATE TABLE audit_logs (
  id TEXT PRIMARY KEY,
  actor_type TEXT NOT NULL,
  actor_id TEXT NOT NULL,
  action TEXT NOT NULL,
  target_type TEXT,
  target_id TEXT,
  metadata JSONB DEFAULT '{}',
  created_at TIMESTAMPTZ DEFAULT now()
);
```

------

# 14. REST API

## 14.1 Health

```http
GET /healthz
```

Response:

```json
{
  "status": "ok"
}
```

## 14.2 Agent

```http
POST /v1/agents
GET /v1/agents
GET /v1/agents/{agent_id}
PATCH /v1/agents/{agent_id}
DELETE /v1/agents/{agent_id}
POST /v1/agents/{agent_id}/tokens
POST /v1/agents/search
```

Create request:

```json
{
  "name": "Andrew OpenClaw",
  "runtime": "openclaw",
  "description": "Local OpenClaw coding agent",
  "capabilities": ["code_analysis", "repo_summary"],
  "inbound_policy": "request_approval",
  "discoverable": false
}
```

Create response:

```json
{
  "agent_id": "agt_01J...",
  "agent_number": "AN-GLOBAL-QZ91TR-77",
  "agent_token": "agt_sk_...",
  "name": "Andrew OpenClaw",
  "runtime": "openclaw",
  "status": "offline"
}
```

要求：

```text
agent_token 只返回一次。
数据库只存 hash。
```

Search request:

```json
{
  "capability": "code_analysis",
  "runtime": "openclaw"
}
```

Search 只返回：

```text
discoverable = true
```

的 agent。

## 14.3 Gateway

```http
POST /v1/gateways
GET /v1/gateways
GET /v1/gateways/{gateway_id}
DELETE /v1/gateways/{gateway_id}
POST /v1/gateways/{gateway_id}/bind-agent
```

## 14.4 Connection

```http
POST /v1/connections/request
POST /v1/connections/{connection_id}/accept
POST /v1/connections/{connection_id}/reject
GET /v1/connections
DELETE /v1/connections/{connection_id}
```

## 14.5 Task

```http
POST /v1/tasks
GET /v1/tasks
GET /v1/tasks/{task_id}
GET /v1/tasks/{task_id}/messages
POST /v1/tasks/{task_id}/cancel
```

Create request:

```json
{
  "from_agent_id": "agt_sender",
  "to": "AN-GLOBAL-QZ91TR-77",
  "idempotency_key": "idem_123",
  "content": [
    {
      "mime": "text/plain",
      "text": "Analyze this repository."
    }
  ],
  "timeout_seconds": 600,
  "limits": {
    "max_duration_seconds": 600,
    "max_steps": 20,
    "max_output_bytes": 1048576
  }
}
```

## 14.6 Approval

```http
GET /v1/approvals
POST /v1/approvals/{approval_id}/accept
POST /v1/approvals/{approval_id}/reject
```

------

# 15. WebSocket API

## 15.1 Connect

```http
GET /v1/ws/agents/{agent_id}?session_id=sess_01J&last_seen_message_id=msg_01J
Authorization: Bearer <agent_token>
```

成功：

```json
{
  "type": "agent.connected",
  "agent_id": "agt_01J...",
  "session_id": "sess_01J...",
  "status": "online"
}
```

## 15.2 Heartbeat

Client 每 15 秒发送：

```json
{
  "type": "presence.heartbeat",
  "agent_id": "agt_01J...",
  "session_id": "sess_01J...",
  "timestamp": "..."
}
```

45 秒未收到 heartbeat：

```text
mark agent offline
close connection if still open
```

## 15.3 ACK

Receiver 必须 ack 每条投递消息：

```json
{
  "type": "ack",
  "message_id": "msg_01J...",
  "task_id": "task_01J..."
}
```

------

# 16. Routing 逻辑

## 16.1 在线投递

```text
POST /v1/tasks
  -> validate sender
  -> resolve target agent_number
  -> check inbound_policy
  -> check connection grant
  -> create task
  -> create task.request message
  -> if target online:
       send over websocket
       mark delivered
     else:
       mark queued
```

## 16.2 离线投递

```text
target offline:
  task.status = queued
  message.delivery_status = queued
```

当目标 Agent 上线：

```text
agent connected
  -> mark online
  -> session.resume
  -> deliver pending messages
  -> deliver retryable unacked messages
```

WebSocket 连接成功后，立即执行：

```python
await routing_service.deliver_pending_messages(agent_id)
```

要求：

```text
1. pending messages 按 created_at 升序投递
2. 已 acked 的 message 不重复投递
3. 未 ack 但已 delivered 的 message 可以重投递
4. SDK 依靠 message_id 去重
```

## 16.3 重试

Retry policy:

```text
1st retry: 5 seconds
2nd retry: 30 seconds
3rd retry: 120 seconds
after ttl: expired
```

MVP 可用 worker 定时扫描：

```text
messages.delivery_status in ('created', 'queued', 'delivered')
```

------

# 17. Rate Limit 和 Abuse 防御

维度：

```text
user_id
agent_id
api_key_id
source_ip
target_agent_id
unknown_sender_to_target
```

默认限制：

```text
Free:
  2 agents
  1,000 messages / month
  100 tasks / month
  30 messages / minute
  10 unknown connection requests / day

Agent:
  max 5 concurrent running tasks
  max payload 1 MB
  max output 1 MB
  max task duration 10 min
```

超限返回：

```json
{
  "type": "error",
  "error": {
    "code": "RATE_LIMITED",
    "message": "Rate limit exceeded.",
    "details": {}
  }
}
```

------

# 18. Error Codes

标准错误码：

```text
AGENT_NOT_FOUND
AGENT_OFFLINE
AGENT_FORBIDDEN
CONNECTION_APPROVAL_REQUIRED
CONNECTION_REJECTED
SECURITY_MODE_NOT_SUPPORTED
TASK_NOT_FOUND
TASK_TIMEOUT
TASK_EXPIRED
TASK_LEASE_EXPIRED
INVALID_TASK_STATE_TRANSITION
MESSAGE_TOO_LARGE
RATE_LIMITED
INVALID_TOKEN
TOKEN_REVOKED
APPROVAL_REQUIRED
APPROVAL_REJECTED
E2EE_NOT_IMPLEMENTED
INTERNAL_ERROR
```

错误格式：

```json
{
  "type": "error",
  "error": {
    "code": "AGENT_NOT_FOUND",
    "message": "Target agent not found.",
    "details": {}
  }
}
```

------

# 19. 代码风格和架构约定

## 19.1 DomainException

定义统一异常：

```python
class DomainException(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = 400,
        details: dict | None = None,
    ):
        ...
```

所有业务错误由 Service 层抛出 `DomainException`。

FastAPI 使用统一 exception handler 转成标准 error response。

禁止：

```text
1. router 中散落业务判断
2. router 中随意 return 非标准错误格式
3. print secrets
```

## 19.2 Async 优先

所有 I/O 使用 async：

```text
DB: SQLAlchemy async engine
Redis: redis.asyncio
WebSocket: async
HTTP handlers: async def
Workers: async loop
```

## 19.3 日志规范

关键路径必须记录：

```text
trace_id
message_id
task_id
from_agent_id
to_agent_id
agent_number
delivery_status
error_code
```

重点模块：

```text
routing_service
message_service
websocket.manager
connection_service
approval_service
```

日志不要打印：

```text
agent_token
api_key
raw secrets
敏感 payload
```

## 19.4 Pydantic 校验

所有外部输入必须先经过 Pydantic model：

```text
REST body
WebSocket message
CLI config
OpenClaw adapter config
```

------

# 20. Python SDK

## 20.1 接收任务

目标代码：

```python
from agentnet import Agent

agent = Agent.from_env()

@agent.task_handler
async def handle(task):
    await task.accept()
    await task.progress("Started")
    await task.result("Done")

agent.run()
```

## 20.2 发送任务

目标代码：

```python
from agentnet import Client

client = Client(api_key="dev_api_key")

task = client.tasks.create(
    from_agent_id="agt_sender",
    to="AN-GLOBAL-QZ91TR-77",
    text="Analyze this repository.",
    idempotency_key="demo-001",
)

result = task.wait_for_result(timeout=600)
print(result.text)
```

## 20.3 SDK 模块

必须实现：

```text
Client
Agent
TaskContext
AgentWebSocket
SessionStore
IdempotencyCache
ProtocolValidator
```

## 20.4 SDK 功能要求

```text
1. 自动 WebSocket 连接
2. 自动 heartbeat
3. 自动 ack
4. 自动去重 message_id
5. 自动 session.resume
6. task.accept()
7. task.progress()
8. task.heartbeat()
9. task.result()
10. task.fail()
11. task.request_approval()
12. reconnect with exponential backoff
```

------

# 21. CLI

CLI 名称：

```text
agentnet
```

## 21.1 Commands

```bash
agentnet login
agentnet agent create
agentnet agent list
agentnet agent token rotate
agentnet connect
agentnet send
agentnet task get
agentnet task logs
agentnet expose openclaw
```

## 21.2 agent create

```bash
agentnet agent create \
  --name "Andrew OpenClaw" \
  --runtime openclaw \
  --capability code_analysis \
  --capability repo_summary \
  --inbound-policy request_approval
```

## 21.3 connect

```bash
agentnet connect --agent AN-GLOBAL-QZ91TR-77
```

## 21.4 send

```bash
agentnet send AN-GLOBAL-QZ91TR-77 "Analyze this repository."
```

## 21.5 expose openclaw

```bash
agentnet expose openclaw \
  --agent AN-GLOBAL-QZ91TR-77 \
  --working-dir ~/projects/demo \
  --allow-path ~/projects/demo \
  --require-approval high-risk
```

------

# 22. OpenClaw Adapter

## 22.1 目标

将远程 `task.request` 转换成本地 OpenClaw 执行，并把输出转换成：

```text
task.progress
task.result
task.failed
approval.request
```

## 22.2 配置文件

```yaml
agent:
  number: AN-GLOBAL-QZ91TR-77
  runtime: openclaw

openclaw:
  mode: cli
  command: openclaw
  working_dir: /Users/andrew/projects/demo

  allow_paths:
    - /Users/andrew/projects/demo

  deny_paths:
    - /Users/andrew/.ssh
    - /Users/andrew/.aws
    - /Users/andrew/.config

  require_approval:
    - shell_command
    - file_write
    - file_delete
    - network_request

  env_policy: minimal

  env_vars:
    OPENCLAW_MODE: agentnet

  pass_env:
    - PATH
    - HOME
    - LANG
    - SHELL
```

## 22.3 环境变量隔离

`subprocess.Popen` 不允许默认继承完整系统环境变量。

默认：

```text
env_policy = minimal
```

行为：

```text
minimal:
  只传 PATH、HOME、LANG、SHELL，以及用户显式配置的 env_vars

inherit:
  继承系统环境，但必须显式启用

deny_sensitive:
  继承时自动删除 AWS_*, GITHUB_*, OPENAI_*, ANTHROPIC_*, SSH_*, GOOGLE_*, AZURE_* 等敏感变量
```

MVP 默认：

```text
minimal + deny_sensitive
```

## 22.4 Safety

必须实现：

```text
1. normalize path
2. reject path traversal
3. default allow only working_dir
4. deny sensitive dirs
5. detect suspicious shell commands
6. require approval for high-risk action
7. enforce task timeout
8. enforce max output bytes
9. isolate env vars
```

## 22.5 MVP Runner

先使用 CLI 模式：

```text
subprocess.Popen([openclaw_command, ...])
stream stdout/stderr
convert output chunks to task.progress
on exit code 0 -> task.result
on non-zero -> task.failed
```

如果没有真实 OpenClaw CLI，生产路径必须显式失败并返回稳定错误码；可以实现明确命名的 test runner / fake runner 来保证测试和 demo 闭环，但必须通过显式测试或 demo 参数启用，不能作为运行时兜底。

------

# 23. MCP Adapter 预留

MVP 不实现完整 MCP adapter，只创建目录和 README。

设计方向：

```text
MCP Server
  -> agentnet-mcp-adapter
  -> Tool Agent with Agent Number
  -> Other agents call it through ARP task.request
```

未来职责：

```text
1. list MCP tools
2. convert tools to agent capabilities
3. expose MCP server as agent
4. convert task.request to MCP tool call
5. convert MCP result to task.result
```

------

# 24. JSON Schema

必须在：

```text
packages/protocol/schemas/
```

定义：

```text
envelope.schema.json
agent.schema.json
task.schema.json
message.schema.json
connection.schema.json
approval.schema.json
error.schema.json
```

Backend 和 SDK 应共享这些 schema 或共享等价 Pydantic model。

------

# 25. 测试要求

## 25.1 Unit Tests

必须覆盖：

```text
health check
protocol model validation
DomainException serialization
agent number generation
agent create/list/get
agent token validation
security mode negotiation
inbound_policy private
inbound_policy request_approval
idempotent task creation
message ack
task state transition
task lease expiration
session.resume
approval flow
rate limit
OpenClaw env filtering
OpenClaw path safety
```

## 25.2 Integration Tests

必须覆盖：

```text
1. Agent A and Agent B connect through WebSocket.
2. A sends task.request to B.
3. B receives task.request and sends ack.
4. B sends task.accepted.
5. B sends task.progress.
6. B sends task.result.
7. Task becomes completed.
8. A can fetch result through REST API.
```

## 25.3 Offline Delivery Test

```text
1. B is offline.
2. A sends task to B.
3. Task status becomes queued.
4. B connects.
5. Server immediately calls deliver_pending_messages.
6. B receives queued task.
7. B sends result.
8. Task becomes completed.
```

## 25.4 Session Resume Test

```text
1. B receives task.
2. B disconnects before result.
3. B reconnects with same session_id and last_seen_message_id.
4. Server returns missed_messages.
5. B resumes and returns result.
```

## 25.5 Task Lease Test

```text
1. Task enters running.
2. No progress or task.heartbeat for more than lease_expires_at.
3. timeout_worker marks task failed.
4. error code is TASK_LEASE_EXPIRED.
```

------

# 26. Implementation Phases

## Phase 0：协议与工程骨架

目标：

```text
1. 创建 monorepo
2. 创建 Docker Compose
3. 启动 FastAPI / Postgres / Redis
4. 定义协议 JSON Schema
5. 定义 Pydantic models
6. 实现 DomainException
7. 实现统一 error response
8. 写 README quickstart draft
9. tests 目录包含 __init__.py，保证测试包结构明确
10. Logger 全局可用，并预留 trace_id/task_id/message_id 字段
11. Docker Compose 增加 dev override 文件
12. Alembic 初始化空迁移，并验证 upgrade/downgrade 链路
13. 定义 Adapter Interface 占位，后续 OpenClaw/MCP 必须实现该接口
```

验收：

```text
docker compose up 可启动
GET /healthz 返回 ok
pytest 可运行
协议 schema 文件存在
DomainException 标准化返回
Redis async client 有连接测试
DB/Alembic 初始化可执行 upgrade/downgrade
Envelope 校验 TTL、Limits、Security modes
E2EE schema/model 接受预留字段，但业务逻辑返回 E2EE_NOT_IMPLEMENTED
Pydantic model 与 JSON Schema 字段保持对应
占位模块不得返回假成功；未实现能力必须显式 NotImplementedError 或 DomainException
```

------

## Phase 1：Agent Registry

目标：

```text
1. users
2. api_keys
3. agents
4. agent_tokens
5. 不可枚举 Agent Number generation
6. Agent CRUD APIs
7. token hashing
8. ownership checks
9. Agent Number 使用 region/namespace/random/checksum 策略
10. Agent CRUD 支持分页、过滤、搜索
11. Agent token 支持生命周期和轮换策略
```

验收：

```text
可以创建 agent
返回不可枚举 agent_number
返回 agent_token 且只显示一次
数据库只存 token_hash
用户不能访问别人的 agent
10,000 次 agent number 生成无重复
分页、过滤、搜索返回稳定 schema
token rotate 后旧 token 失效，新 token 只显示一次
```

------

## Phase 2：WebSocket Presence

目标：

```text
1. WebSocket endpoint
2. agent token auth
3. connection manager
4. heartbeat
5. Redis presence
6. online/offline status
7. 单 Agent 多连接数限制
8. heartbeat interval 可配置
9. reconnect backoff 与 session.resume 恢复未 ack 消息
```

验收：

```text
agent 可连接
agent 每 15 秒 heartbeat
断线 45 秒后 offline
非法 token 被拒绝
超过连接数限制被拒绝并返回标准错误
session.resume 能恢复未 ack 消息
```

------

## Phase 3：Task + Message Storage

目标：

```text
1. tasks table
2. messages table
3. POST /v1/tasks
4. GET /v1/tasks/{id}
5. GET /v1/tasks/{id}/messages
6. idempotency_key
7. task lease 字段
8. 状态机边界检查
9. 动态 lease 字段预留
10. progress/heartbeat 历史记录预留
```

验收：

```text
创建 task 会创建 task.request message
重复 idempotency_key 返回同一个 task
状态机正确
running task 有 lease_expires_at
非法状态转换返回 INVALID_TASK_STATE_TRANSITION
heartbeat 刷新 lease 并记录 last_progress_at
```

------

## Phase 4：Relay Routing

目标：

```text
1. agent_number -> agent_id
2. online delivery
3. ack
4. offline queue
5. deliver_pending_messages on connect
6. retry worker MVP
7. offline queue 支持 priority/TTL/task type 排序预留
8. ack 幂等
9. retry backoff 策略
10. 多 relay 节点接口预留
```

验收：

```text
在线 agent 能收到 task.request
ack 后 message 标记 acked
离线 agent 上线后立即收到 queued message
已 acked 消息不重复投递
未 ack delivered 消息可重投递
重复 ack 不改变最终状态且不报错
过期 TTL 消息不会投递
```

------

## Phase 5：Connection Policy

目标：

```text
1. inbound_policy
2. agent_connections
3. connection.request
4. accept/reject
5. contacts_only/private/public/request_approval
6. security mode negotiation
7. security mode 多模式交集和优先级
8. inbound_policy 动态策略预留：time window / task type / risk level
9. 审批队列 batch approve/reject 预留
```

验收：

```text
private 阻止跨用户
request_approval 创建 connection.request
accepted 后允许创建 task
rejected 后禁止创建 task
security mode 不兼容时返回 SECURITY_MODE_NOT_SUPPORTED
security mode 协商结果可审计
审批队列状态可查询
```

------

## Phase 6：Task Result / Progress / Approval

目标：

```text
1. task.accepted
2. task.progress
3. task.heartbeat
4. task.result
5. task.failed
6. approval.request
7. approval.accepted/rejected
8. awaiting_approval status
9. task lease refresh
10. 高风险审批超时处理
11. task.progress 历史记录
12. task/action audit log
```

验收：

```text
Agent B 可返回 progress 和 result
Task completed 后可查询结果
task.progress 刷新 lease
task.heartbeat 刷新 lease
高风险 action 可进入 awaiting_approval
approval accepted 后继续执行
approval rejected 后 task rejected/failed
approval expired 后任务进入明确失败/拒绝状态
progress 历史可查询并可用于恢复调试
```

------

## Phase 7：Python SDK

目标：

```text
1. Client
2. Agent
3. TaskContext
4. WebSocket client
5. auto ack
6. auto heartbeat
7. auto task.heartbeat
8. auto reconnect
9. local session store
10. idempotency cache
11. reconnect exponential backoff
12. CLI/GUI approval hook 预留
```

验收：

```text
examples/echo_agent.py 可以运行
examples/send_task.py 可以发送任务
断线重连能 session.resume
重复消息不会重复执行
本地 session store 记录 last_message_id 和 running_tasks
重复 message_id 自动 ack 但不重复调用 handler
```

------

## Phase 8：CLI

目标：

```text
1. agentnet login
2. agent create/list
3. connect
4. send
5. task get/logs
6. local config
7. approval prompt
8. 命令自动补全和别名预留
9. 日志输出格式化
10. 查看任务历史和重试失败任务
```

验收：

```text
用 CLI 可以创建 agent
用 CLI 可以连接 agent
用 CLI 可以发送 task 并看到 result
CLI 能显示 approval.request 并允许用户 y/N
高风险提示必须醒目并要求显式确认
可查看任务历史和失败任务详情
```

------

## Phase 9：OpenClaw Adapter

目标：

```text
1. expose openclaw command
2. openclaw adapter config
3. allow-path
4. deny-path
5. env isolation
6. high-risk approval
7. subprocess runner
8. output streaming
9. minimal env + deny_sensitive
10. 路径越权检测 + shell command 审查
11. max_output_bytes 截断策略
12. 显式 test runner 支持测试闭环，但不得作为生产兜底
```

验收：

```text
远程 task 可以触发本地 adapter
adapter 输出 progress
任务结束返回 result
高风险操作需要审批
敏感 env 不会传入子进程
路径越权会被拒绝
超过 max_output_bytes 的输出被截断并记录
真实 OpenClaw CLI 缺失时生产路径必须失败，不得自动切换 mock
```

------

## Phase 10：Hardening

目标：

```text
1. rate limit
2. max payload
3. task timeout
4. task lease timeout
5. retry cleanup
6. audit log
7. error code standardization
8. structured logs
9. user/agent/IP/unknown sender 多维度 rate limit
10. 敏感信息脱敏验证
11. lease 超期告警预留
```

验收：

```text
大 payload 被拒绝
超时 task 自动 expired
lease 过期 task 自动 failed
关键操作写 audit_logs
所有 API 错误格式统一
限流错误返回 RATE_LIMITED
结构化日志包含 trace_id/task_id/message_id/error_code
```

------

# 27. 端到端 Demo 验收

## Demo 1：两个 Python Agent 通信

Terminal 1:

```bash
python packages/python-sdk/examples/echo_agent.py
```

Terminal 2:

```bash
python packages/python-sdk/examples/send_task.py
```

Expected:

```text
Task created
Progress received
Result: ...
```

## Demo 2：CLI 通信

Terminal 1:

```bash
agentnet agent create --name "Echo Agent" --runtime python
agentnet connect --agent AN-GLOBAL-QZ91TR-77
```

Terminal 2:

```bash
agentnet send AN-GLOBAL-QZ91TR-77 "hello"
```

Expected:

```text
Result: hello
```

## Demo 3：离线投递

```text
1. Stop receiver.
2. Send task.
3. Verify task queued.
4. Start receiver.
5. Verify receiver gets task immediately after connect.
6. Verify task completed.
```

## Demo 4：跨用户审批

```text
1. Agent A requests Agent B.
2. B has inbound_policy=request_approval.
3. B receives connection.request.
4. B accepts.
5. A sends task.
6. B returns result.
```

## Demo 5：OpenClaw Adapter 显式 Test Runner

```bash
agentnet expose openclaw \
  --agent AN-GLOBAL-QZ91TR-77 \
  --working-dir ./demo \
  --allow-path ./demo \
  --require-approval high-risk
```

Send:

```bash
agentnet send AN-GLOBAL-QZ91TR-77 "Analyze this repo"
```

Expected:

```text
Adapter starts
Progress streamed
Result returned
```

------

# 28. Codex 执行规则

```text
1. 每个 Phase 单独提交。
2. 每个 Phase 必须有测试。
3. 不要一次性实现所有功能。
4. 优先保证 Backend + SDK + CLI 闭环。
5. Dashboard 暂时不做。
6. E2EE 只预留字段，不实现。
7. MCP Adapter 只预留目录和 README，不实现完整协议。
8. OpenClaw Adapter 如果无法调用真实 OpenClaw，生产路径必须显式失败；test/fake runner 只能通过明确参数启用，不得作为兜底。
9. 严禁兜底代码：不得 silent fallback、不得假成功、不得自动切换 mock/fake/memory-only。
10. 不接受最低验收替代完整验收；每个 Phase 必须覆盖成功路径、失败路径、安全边界和关键可靠性行为。
11. 所有 secrets 只存 hash。
12. 所有外部输入必须通过 Pydantic 校验。
13. 所有业务异常必须使用 DomainException。
14. 所有 I/O 使用 async。
15. 日志不能打印 secret、token、API key、敏感 payload。
```

------

# 29. 第一条 Codex Prompt：Phase 0

可以直接复制下面这段给 Codex。

```text
Create the initial monorepo for AgentNet / Agent Relay Platform.

Implement Phase 0 only.

Project goal:
Build a centralized Agent Relay Platform that lets different AI agents communicate through Agent Numbers, WebSocket relay, task messages, connection approval, and future adapter layers.

Do not implement decentralization, blockchain, gas, marketplace, billing, full E2EE, or full MCP adapter.

Required stack:
- Python 3.11+
- FastAPI
- SQLAlchemy 2.x async
- Alembic
- PostgreSQL
- Redis using redis.asyncio
- Pydantic v2
- pytest + pytest-asyncio
- Docker Compose

Global constraints:
- No fallback code. Do not silently switch to mock/fake/memory-only/default-success behavior.
- Missing dependencies, invalid config, unsupported protocol modes, and unimplemented capabilities must fail explicitly with DomainException or NotImplementedError.
- Test/fake runners are allowed only when explicitly named and explicitly enabled by test/demo configuration.
- Do not treat a minimal happy-path smoke test as complete acceptance.

Repository structure:
Create the monorepo structure described in the plan:
- apps/api
- apps/cli
- packages/python-sdk
- packages/protocol/schemas
- adapters/openclaw
- adapters/mcp
- infra
- docs

Phase 0 deliverables:

1. FastAPI app
- apps/api/app/main.py
- GET /healthz returns {"status": "ok"}
- app config using environment variables
- structured logging setup
- globally available logger helpers with reserved trace_id, task_id, message_id fields

2. Database setup
- async SQLAlchemy engine
- Alembic initialized
- Alembic has an empty initial migration
- Alembic upgrade/downgrade can run
- PostgreSQL configured in docker-compose
- No business tables yet, but migration system must work

3. Redis setup
- Redis configured in docker-compose
- async Redis client module
- basic connectivity test

4. Protocol models
Create Pydantic models for ARP v0.1:
- Envelope
- DeliveryOptions
- SecurityOptions
- Limits
- ContentPart
- ErrorResponse
- TaskMessage
- ConnectionRequest
- ConnectionAccepted
- ConnectionRejected
- ApprovalRequest
- ApprovalAccepted
- ApprovalRejected

Envelope must include:
- version
- message_id
- request_id
- session_id
- type
- from
- to
- task_id
- conversation_id
- timestamp
- ttl_seconds
- delivery
- security
- limits
- content
- encrypted_payload reserved
- aad reserved
- metadata

Security modes:
- relay_visible
- relay_encrypted
- e2ee

For MVP, E2EE is reserved only. Define fields but do not implement encryption.

5. JSON Schema files
Generate or handwrite JSON Schema files under packages/protocol/schemas:
- envelope.schema.json
- agent.schema.json
- task.schema.json
- message.schema.json
- connection.schema.json
- approval.schema.json
- error.schema.json

6. Constants
Create protocol constants:
- message types
- task statuses
- delivery statuses
- inbound policies
- security modes
- standard error codes

Include these error codes:
- AGENT_NOT_FOUND
- AGENT_OFFLINE
- AGENT_FORBIDDEN
- CONNECTION_APPROVAL_REQUIRED
- CONNECTION_REJECTED
- SECURITY_MODE_NOT_SUPPORTED
- TASK_NOT_FOUND
- TASK_TIMEOUT
- TASK_EXPIRED
- TASK_LEASE_EXPIRED
- INVALID_TASK_STATE_TRANSITION
- MESSAGE_TOO_LARGE
- RATE_LIMITED
- INVALID_TOKEN
- TOKEN_REVOKED
- APPROVAL_REQUIRED
- APPROVAL_REJECTED
- E2EE_NOT_IMPLEMENTED
- INTERNAL_ERROR

7. DomainException
Implement:
- DomainException class
- FastAPI exception handler
- standard error response shape

8. Tests
Add tests for:
- GET /healthz
- protocol model validation
- invalid security mode rejection at schema/model level
- E2EE mode is accepted as a reserved field but not implemented in business logic yet
- DomainException serializes into standard error response
- Redis async connectivity wrapper
- DB/Alembic initialization smoke test where environment allows
- tests package contains __init__.py

9. Placeholder adapters
- adapters/mcp/README.md explaining that MCP will later wrap MCP servers as AgentNet tool agents
- adapters/openclaw with placeholder package, README, and config schema draft
- define a shared Adapter Interface placeholder that future adapters must implement
- placeholders must raise NotImplementedError or document TODOs; they must not return fake success

10. Docs
Create:
- README.md with local dev instructions
- docs/architecture.md
- docs/protocol.md
- docs/security-model.md
- docs/quickstart.md draft

Important architecture rules:
- Use async/await for all I/O.
- Do not implement business logic in routers.
- Service layer should raise DomainException.
- Do not print secrets in logs.
- Do not implement fallback behavior.
- Do not catch broad exceptions and return default success.
- Do not implement Phase 1 yet.
- Do not create agent registry tables yet, except if needed for Alembic smoke test.
- Keep code modular so Phase 1 can add users, api_keys, agents, agent_tokens, and agent number generation.
```

------

# 30. 第二条 Codex Prompt：Phase 1

Phase 0 完成、测试通过后，再发这条。

```text
Implement Phase 1: Agent Registry.

Before coding, review the current repository and ensure:
- all protocol constants are centralized
- all Pydantic models are importable by both API and SDK packages
- Alembic can create and downgrade migrations
- DomainException is the only business exception pattern
- tests pass with docker-compose services running

Implement:
1. users table and SQLAlchemy model
2. api_keys table and SQLAlchemy model
3. agents table and SQLAlchemy model
4. agent_tokens table and SQLAlchemy model
5. Alembic migration for these tables
6. Agent Number generation service
7. Agent CRUD APIs
8. Agent token generation and hashing
9. Basic ownership checks
10. Agent token lifecycle and rotation
11. Agent CRUD pagination, filtering, and search
12. Tests

Agent Number requirements:
- Do not use simple sequential numbers.
- Use format AN-{REGION}-{RANDOM}-{CHECKSUM} for MVP.
- Keep namespace extension points in the service API for future use.
- Example: AN-GLOBAL-QZ91TR-77.
- Use secrets or uuid for random generation.
- Suffix/checksum must be computed from the generated body, not hardcoded.
- agent_number must be globally unique.
- Add test that generates 10,000 agent numbers with no duplicates.

Agent creation:
POST /v1/agents should accept:
{
  "name": "Andrew OpenClaw",
  "runtime": "openclaw",
  "description": "Local OpenClaw coding agent",
  "capabilities": ["code_analysis", "repo_summary"],
  "inbound_policy": "request_approval",
  "discoverable": false
}

Response should include:
{
  "agent_id": "...",
  "agent_number": "AN-GLOBAL-...",
  "agent_token": "agt_sk_...",
  "name": "...",
  "runtime": "...",
  "status": "offline"
}

Security:
- agent_token must be shown only once.
- Store only token_hash in database.
- Never log raw token.
- Users cannot access agents owned by another user.
- token rotation must revoke the old token and return the new raw token once.
- expired or revoked tokens must fail explicitly; no fallback auth.

Tests:
- create agent
- list own agents
- cannot read another user's agent
- token hash is stored, raw token is not
- invalid inbound_policy rejected
- invalid runtime rejected only if runtime validation exists
- 10,000 generated agent numbers have no duplicates
- pagination/filter/search behavior
- rotate token invalidates old token
```

------

# 31. 总体开发顺序

严格按这个顺序推进：

```text
Phase 0: 协议与工程骨架
Phase 1: Agent Registry
Phase 2: WebSocket Presence
Phase 3: Task + Message Storage
Phase 4: Relay Routing
Phase 5: Connection Policy
Phase 6: Task Result / Progress / Approval
Phase 7: Python SDK
Phase 8: CLI
Phase 9: OpenClaw Adapter
Phase 10: Hardening
```

不要先做 Dashboard。
不要先做 marketplace。
不要先做 E2EE。
不要先做去中心化。
先跑通：

```text
Agent A -> Relay -> Agent B -> Result
```

这个闭环。


------

# 0.3 Phase Review Workflow

After each Phase is completed, it MUST be reviewed by Claude Code.
Only after Claude approves can the next Phase begin.

```text
1. Complete all development for the current Phase
2. Run Claude Code for code review
   - Verify Token/Secret not leaked in logs
   - Verify heartbeat and ack mechanisms are correct
   - Verify connection cleanup is correct
   - Verify audit_log fields are present
   - Verify error codes follow protocol standard
   - Verify tests cover all current Phase goals
3. Claude returns APPROVED
4. Fix all blocking issues
5. Re-submit to Claude for final verification
6. Upon approval, automatically start building the next Phase
```

Review Checklist:

- [ ] Token/Secret not printed in logs
- [ ] Heartbeat and ack mechanisms are correct
- [ ] Connection cleanup is correct
- [ ] audit_log fields are complete
- [ ] Error codes follow protocol standard
- [ ] Tests cover all current Phase goals


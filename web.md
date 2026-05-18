# AgentNet Enterprise Dashboard 完整建设计划

## Summary

建设一个可用于大型上线的企业级 Dashboard，而不是个人 demo。系统分为：

- **用户控制台**：用户管理自己的 Agent、任务、审批、连接请求、Agent Firewall、API key、任务结果和运行历史。
- **管理员运营台**：管理员进行全局观测、用户/Agent/任务治理、审计追踪、系统健康检查和生产风险管理。

核心原则：

- 前端为独立 Web App，放在 `apps/web`。
- 后端新增 Dashboard API 和 Admin API。
- 登录态使用 HttpOnly Session，不把 API key 存到浏览器。
- RBAC 使用 `user | admin | super_admin`，但配套明确 permission matrix。
- 管理员高风险操作必须 step-up auth。
- 所有列表分页，所有 KPI 缓存，避免 Dashboard 上线后打爆数据库。
- System 页严格禁止泄露 secret、连接串、完整环境变量。
- 所有管理员读写关键资源都进入 audit log。

---

## 1. 全局执行约束

这些约束适用于 Dashboard 全部子阶段，包括后端 API、前端页面、数据库迁移、Docker/nginx、测试、文档和执行报告。任何子阶段没有满足这些约束，都不能标记为完成。

### 1.1 不允许兜底成功

以下行为禁止出现在生产路径：

- 依赖缺失时自动切换到 mock、fake、memory-only、local-only 或 silent mode。
- 捕获异常后返回看似成功的默认 Dashboard 数据，例如空 KPI、空列表、伪健康状态或“全部正常”。
- Redis、Postgres、rate limiter、session store、CSRF 校验、RBAC 校验、KPI cache、audit writer 失败后静默放行。
- Dashboard API 未实现时返回成功占位。
- Admin/System 页面无法读取真实状态时展示绿色健康。
- 前端请求失败后把错误吞掉并显示旧数据为“最新数据”。
- 登录、step-up、session rotation、CSRF、危险操作确认失败后继续执行 mutation。

允许的例外：

- 测试专用 fake，但必须只存在于测试路径或显式 test mode。
- 清理资源时吞掉二次异常，例如撤销 session 后二次清理 cookie、关闭测试服务器、取消后台 task。
- 幂等 ack 或幂等 revoke 已经完成时 no-op。
- 前端可以展示明确标记的 cached/stale 数据，但必须显示 stale 状态和最后更新时间。

### 1.2 不接受轻量验收

每个 Dashboard 子阶段必须包含：

- 文件交付物。
- 自动化测试或可执行验证命令。
- 失败路径验证。
- 权限边界验证。
- 安全和脱敏验证。
- 文档更新。
- 执行报告。

如果某项验证因本地环境无法执行，报告必须明确写出：

- 阻塞原因。
- 已完成的替代静态验证。
- 未完成风险。
- 后续必须补跑的命令。

不能把“未执行”写成“通过”，也不能把 mock 结果写成生产链路通过。

### 1.3 安全和审计要求

- 不提交真实 secret、token、password、private key。
- `.env.production` 不进入版本控制，只提交 `.env.production.example`。
- 前端 bundle、测试报告、截图、日志不得包含 API key、Agent token、session token、CSRF token、数据库密码或用户敏感 payload。
- 浏览器端禁止保存 API key 到 localStorage/sessionStorage。
- System 页禁止展示连接串、完整环境变量、私钥路径、带凭证 URL。
- 所有新增运维流程必须说明审计点、回滚策略和失败时的显式状态。
- 所有 admin mutation 必须写 audit log。
- 管理员读取用户详情、Agent 详情、Task 详情、Audit detail/export 时必须写 read audit。
- audit log 不得记录 secret 明文、完整 token、完整 API key、完整敏感 payload。

### 1.4 RBAC 和权限安全要求

- `user | admin | super_admin` 只是角色名，真实判断必须走 permission helper，不能在页面或 router 中散写字符串判断。
- 后端必须作为最终权限边界；前端隐藏按钮只能作为体验优化，不能作为安全控制。
- `admin` 的“低风险运营动作”必须只限于本计划定义的动作，新增动作默认视为高风险。
- 高风险操作必须满足 `super_admin + step-up auth + 二次确认 + audit`。
- 权限变化、用户禁用、API key 强制 revoke 后，相关 Dashboard session 必须失效或 rotate。
- 普通用户任何 Dashboard API 都不能读取其他用户资源，包括间接通过 task、message、approval、connection、audit 获取。

### 1.5 Session、CSRF 和浏览器安全要求

- Dashboard session 只保存 hash，不保存明文 session token。
- CSRF token 只保存 hash，所有 mutation 必须校验 `X-CSRF-Token`。
- login、step-up、权限变化、敏感操作后必须执行 session rotation。
- admin/super_admin idle timeout 必须短于普通用户。
- Cookie production 配置必须启用 `Secure`、`HttpOnly` session、`SameSite=Lax`。
- 前端必须统一处理 `401`、`403`、`STEP_UP_REQUIRED`、`CSRF_TOKEN_INVALID`，不能静默重试危险 mutation。

### 1.6 KPI 和大型上线性能要求

- Overview 和 System KPI 禁止每次请求实时全表扫描。
- 聚合必须使用 Redis-backed snapshot cache 或明确的 bounded time window query。
- 所有列表接口必须分页，默认 `limit=50`，最大 `limit=200`。
- Audit export 禁止同步导出超大结果；必须异步或限制范围。
- 短轮询必须有合理间隔，默认用户侧 15s、管理员侧 30s、System health 10s。
- 多 tab 或后台页面不得造成高频重复刷新；前端需要 query dedup、stale time 和手动 refresh。

### 1.7 前端交付质量要求

- Dashboard 是工作台，不做 landing page。
- 用户侧和管理员侧导航必须清晰分离。
- 长 JSON、payload、result、error 默认折叠，并对疑似 secret 脱敏。
- 危险操作统一使用 `DangerActionButton`、二次确认和 step-up 提示。
- 所有页面必须有 loading、empty、error、forbidden、stale 状态。
- 表格不得承载过多危险操作；复杂操作进入 detail 页。
- 页面文字、表格列、按钮和状态徽标不得重叠，必须通过浏览器截图或 Playwright 校验主要页面。

### 1.8 审查和报告要求

每个 Dashboard 子阶段完成后必须生成报告：

```text
reports/web_phase_x_report.md
```

报告至少包含：

- 子阶段目标。
- 新增和修改文件。
- 执行过的命令。
- 自动化测试结果。
- 失败路径验证结果。
- RBAC / CSRF / session / secret 脱敏验证结果。
- 未完成项。
- 风险和后续建议。
- 人工审查结论。

每轮审查都在终端中使用claude，进行代码审查，审查后针对意见进行修改，修改过后再次进行审查，审查通过后才能进入下一阶段的开发。审查不只看测试是否通过，还必须审查真实代码、配置、前端页面和文档是否达到需求。涉及安全、权限、审计、System 页、KPI 聚合的子阶段必须明确写出“未发现兜底成功”或列出发现的问题。

---

## 2. Architecture

### 前端

新增独立应用：

```text
apps/web
```

技术栈：

- React
- TypeScript
- Vite
- Tailwind CSS
- TanStack Query
- React Router
- Recharts
- Vitest + Testing Library
- Playwright E2E

部署方式：

- 开发：Vite dev server。
- 生产：构建静态文件，由 nginx 或独立 web 容器服务。
- API 请求统一走 `/v1/...`，生产由 nginx 反向代理到 FastAPI。

### 后端

新增三类 API：

```text
/v1/dashboard/*
/v1/admin/*
/v1/dashboard/auth/*
```

保持现有 REST API 不破坏：

```text
/v1/agents
/v1/tasks
/v1/approvals
/v1/connections
/v1/auth
```

Dashboard API 是面向 UI 的聚合层，不直接把内部 SQLAlchemy model 原样暴露给前端。

### 数据库

新增或扩展：

- `users.role`
- `users.is_disabled`
- `dashboard_sessions`
- admin read audit 行为
- 可能的 operator notes / disabled reason 字段
- KPI 需要的索引

---

## 3. RBAC Permission Matrix

角色：

```text
user
admin
super_admin
```

### 权限矩阵

| Capability                               | user | admin | super_admin |
| ---------------------------------------- | ---: | ----: | ----------: |
| 登录 Dashboard                           |  yes |   yes |         yes |
| 查看自己的 overview                      |  yes |   yes |         yes |
| 查看自己的 Agents                        |  yes |   yes |         yes |
| 创建自己的 Agent                         |  yes |   yes |         yes |
| 编辑自己的 Agent metadata                |  yes |   yes |         yes |
| 删除自己的 Agent                         |  yes |   yes |         yes |
| 轮换自己的 Agent token                   |  yes |   yes |         yes |
| 查看自己的 Tasks                         |  yes |   yes |         yes |
| 创建自己的 Task                          |  yes |   yes |         yes |
| 查看自己的 Task messages/progress/result |  yes |   yes |         yes |
| 处理自己的 task approval                 |  yes |   yes |         yes |
| 管理自己的 API keys                      |  yes |   yes |         yes |
| 管理自己的 connection requests           |  yes |   yes |         yes |
| 管理自己的 Agent Firewall                |  yes |   yes |         yes |
| 查看全局 overview                        |   no |   yes |         yes |
| 查看全局 users 列表                      |   no |   yes |         yes |
| 查看全局 agents 列表                     |   no |   yes |         yes |
| 查看全局 tasks 列表                      |   no |   yes |         yes |
| 查看全局 task detail                     |   no |   yes |         yes |
| 查看 audit logs                          |   no |   yes |         yes |
| 导出 audit logs                          |   no |    no |         yes |
| 禁用 / 启用用户                          |   no |    no |         yes |
| 强制 revoke 用户 API key                 |   no |    no |         yes |
| 禁用 / 启用任意 Agent                    |   no |    no |         yes |
| 强制取消未执行任务                       |   no |   yes |         yes |
| 强制取消运行中任务                       |   no |    no |         yes |
| 修改系统级安全策略                       |   no |    no |         yes |
| 查看 System 页健康摘要                   |   no |   yes |         yes |
| 查看 secret / env / connection string    |   no |    no |          no |

### 低风险运营动作定义

`admin` 可执行的低风险动作只包括：

- 查看全局 metadata。
- 查看全局任务、Agent、用户、审计摘要。
- 对告警做 acknowledged。
- 添加 operator note。
- 取消尚未被 Agent 接收、尚未进入 Adapter 执行的任务。
- 触发只读 health check。
- 查看脱敏后的系统健康状态。

除此之外的 admin mutation 都视为高风险，必须 `super_admin + step-up auth`。

### 高风险操作

高风险操作包括：

- 禁用 / 启用用户。
- 禁用 / 启用任意 Agent。
- 强制 revoke API key。
- 强制取消 running task。
- 强制过期 task。
- 导出 audit logs。
- 修改系统级策略。
- 批量操作。
- 任何可能影响其他用户业务连续性的操作。

所有高风险操作必须：

- `super_admin` 权限。
- step-up auth 未过期。
- 二次确认。
- 写 audit log。
- 不记录 secret 明文。

---

## 4. Auth, Session, CSRF

### 登录方式

Dashboard 登录采用：

```text
username + API key -> HttpOnly session cookie
```

不在浏览器 localStorage/sessionStorage 保存 API key。

新增接口：

```text
POST /v1/dashboard/auth/login
POST /v1/dashboard/auth/logout
POST /v1/dashboard/auth/step-up
GET  /v1/dashboard/auth/me
```

### dashboard_sessions 表

新增表：

```text
dashboard_sessions
```

字段：

- `id`
- `user_id`
- `session_hash`
- `csrf_hash`
- `created_at`
- `expires_at`
- `idle_expires_at`
- `last_seen_at`
- `last_csrf_seen_at`
- `rotated_at`
- `step_up_until`
- `revoked_at`
- `revoked_reason`
- `revoked_by_user_id`
- `request_ip`
- `user_agent`

安全规则：

- 只保存 session token hash。
- 只保存 csrf token hash。
- 明文 token 只通过 cookie 发送一次。
- session 被 revoke 后立即拒绝。
- user 被 disabled 后拒绝所有 session。

### Session 生命周期

默认策略：

| 类型        | absolute lifetime | idle timeout |
| ----------- | ----------------: | -----------: |
| user        |           30 days |          24h |
| admin       |            7 days |           2h |
| super_admin |            7 days |           2h |

session rotation 时机：

- 登录后创建新 session。
- step-up 成功后 rotate。
- 权限变化后 rotate/revoke 旧 session。
- 高风险操作完成后 rotate。
- 用户禁用后 revoke 全部 session。
- API key 强制 revoke 后 revoke 相关 Dashboard session。

### Cookie 策略

Session cookie：

```text
HttpOnly=true
SameSite=Lax
Secure=true in production
Path=/
```

CSRF cookie：

```text
HttpOnly=false
SameSite=Lax
Secure=true in production
Path=/
```

### CSRF

所有 mutation 请求要求：

```text
X-CSRF-Token: <csrf_token>
```

需要 CSRF 的方法：

- POST
- PUT
- PATCH
- DELETE

不需要 CSRF 的方法：

- GET
- HEAD
- OPTIONS

校验逻辑：

- 从 session cookie 找到 session。
- 从 header 读取 `X-CSRF-Token`。
- hash 后与 `dashboard_sessions.csrf_hash` 比对。
- 成功后更新 `last_csrf_seen_at`。
- 失败返回统一错误码：

```text
CSRF_TOKEN_MISSING
CSRF_TOKEN_INVALID
```

### Step-up Auth

高风险操作前要求 step-up。

接口：

```text
POST /v1/dashboard/auth/step-up
```

v1 验证方式：

```text
重新输入当前有效 API key
```

成功后：

- 设置 `step_up_until = now + 10 minutes`。
- rotate session。
- 写 audit log：`dashboard.step_up.success`。

失败后：

- 写 audit log：`dashboard.step_up.failed`。
- 不说明具体 key 是否存在。
- 返回统一 403。

高风险接口若未 step-up：

```text
403 STEP_UP_REQUIRED
```

---

## 5. User Dashboard Pages

### `/app/overview`

显示：

- Online agents
- Tasks today
- Failed tasks
- Pending approvals
- Pending messages
- 最近 10 个任务
- 最近 10 条审批
- 最近 Agent 状态变化

刷新：

- 默认 15 秒短轮询。
- 支持手动 refresh。
- 不展示敏感 payload。

### `/app/agents`

Agent 列表字段：

- name
- agent_number
- runtime
- status
- inbound_policy
- discoverable
- capabilities summary
- created_at
- updated_at
- last_seen_at

操作：

- create agent
- search
- filter by status/runtime/policy
- 跳转 detail

### `/app/agents/:agentId`

Agent 详情页。

显示：

- 基础 metadata。
- Agent Number。
- online/offline 状态。
- runtime。
- capabilities。
- inbound policy。
- discoverable。
- token metadata，不展示 token 明文。
- 最近任务。
- 最近连接请求。
- 最近 audit timeline。

操作：

- edit metadata。
- rotate token。
- delete agent。
- 修改 inbound policy。
- 进入 Agent Firewall。

### `/app/tasks`

任务列表字段：

- task_id
- status
- sender agent
- target agent
- created_at
- updated_at
- duration
- error_code
- risk level
- delivery status

过滤：

- status
- sender
- target
- date range
- error_code
- idempotency_key
- assigned_to

### `/app/tasks/:taskId`

任务详情页。

显示：

- task metadata。
- payload preview，默认折叠。
- result preview。
- error_message。
- message timeline。
- progress timeline。
- approval timeline。
- audit timeline。
- delivery status。
- retry count。
- lease status。

安全：

- payload/result 中疑似 secret 的字段默认 mask。
- JSON viewer 默认折叠深层对象。

### `/app/approvals`

审批中心，必须区分两类审批：

1. **Task Action Approvals**

   - 高风险 Adapter 操作。
   - shell/file/network 等 action preview。
   - risk level。
   - accept/reject。
2. **Connection Approvals**

   - 跨 Agent 或跨用户连接请求。
   - requester / target。
   - requested policy。
   - accept/reject。

操作：

- accept
- reject
- filter by type/status/risk
- batch 操作首版不做

### `/app/connections`

Connection Requests / Agent Firewall 页面。

功能：

- 查看 inbound policy。
- 查看 pending connection requests。
- 查看 accepted connections。
- 查看 rejected connections。
- 添加 allowed contact。
- 添加 denied contact。
- 修改 Agent inbound policy。
- 查看连接历史。

Firewall 视图：

- per-agent policy。
- allowed senders。
- blocked senders。
- pending requests。
- last decision time。

### `/app/api-keys`

显示：

- key_id
- name
- key_prefix
- created_at
- expires_at
- revoked_at
- last_used_at 如后端已有或后续补充

操作：

- create key。
- revoke key。
- 默认拒绝 revoke 最后一个 active key，除非显式确认。

---

## 6. Admin Dashboard Pages

### `/admin/overview`

全局指标：

- total users
- active users
- disabled users
- total agents
- online agents
- active WebSocket connections
- tasks last 1h / 24h / 7d
- failed tasks
- expired tasks
- pending approvals
- pending messages
- retry worker health
- timeout worker health
- API 5xx rate

刷新：

- 默认 30 秒短轮询。
- 手动 refresh。
- 使用 Redis snapshot cache。

### `/admin/users`

用户列表字段：

- user_id
- username
- role
- is_disabled
- agents_count
- active_api_keys_count
- tasks_24h
- failed_tasks_24h
- created_at
- last_seen_at 如可得

过滤：

- role
- disabled
- created date
- search username

操作：

- 查看详情。
- super_admin 可 disable/enable。
- super_admin 可强制 revoke API keys。

### `/admin/users/:userId`

用户详情：

- metadata。
- agents。
- api key metadata。
- tasks summary。
- approvals summary。
- recent audit。
- sessions summary。

危险操作：

- disable user。
- enable user。
- revoke all API keys。
- revoke all dashboard sessions。

### `/admin/agents`

全局 Agent 列表。

字段：

- agent_id
- agent_number
- owner
- name
- status
- runtime
- inbound_policy
- discoverable
- tasks_24h
- failed_tasks_24h
- last_seen_at

操作：

- 查看详情。
- super_admin 禁用/启用。

### `/admin/agents/:agentId`

全局 Agent 详情：

- Agent metadata。
- owner。
- token metadata。
- connection policy。
- recent tasks。
- recent audit。
- connection history。
- error summary。

### `/admin/tasks`

全局任务追踪。

字段：

- task_id
- status
- owner/sender/target
- created_at
- updated_at
- duration
- error_code
- delivery_status
- retry_count

过滤：

- user
- agent
- status
- date range
- error_code
- risk level

操作：

- admin 可取消低风险未执行任务。
- super_admin 可取消 running task 或 force expire。

### `/admin/tasks/:taskId`

全局任务详情。

显示：

- metadata。
- timeline。
- messages。
- progress。
- approvals。
- audit。
- error details。

安全：

- payload 默认 mask。
- 明确提示管理员正在查看用户数据。
- 每次打开写 read audit。

### `/admin/audit`

审计查询。

支持过滤：

- actor_type
- actor_id
- viewer_id
- viewer_role
- action
- resource_type
- resource_id
- task_id
- message_id
- error_code
- request_ip
- created_at range

支持两类审计：

- 谁改过什么。
- 谁看过什么。

导出：

- 仅 super_admin。
- 需要 step-up。
- 大结果异步导出，不同步阻塞请求。

### `/admin/system`

只展示摘要，不展示 secret。

允许展示：

- API health：ok/degraded/down。
- DB health：ok/degraded/down。
- Redis health：ok/degraded/down。
- migration revision。
- app version。
- worker status。
- pending queue length。
- retry backlog。
- timeout worker last cycle。
- metrics scrape health。
- HTTPS/WSS staging gate：not_configured / configured / verified / failed。
- Grafana/Prometheus 链接 label。

禁止展示：

- `DATABASE_URL`
- `REDIS_URL`
- API key
- Agent token
- session token
- password
- private key path
- full environment variables
- bearer token in URL
- user payload secret

---

## 7. Dashboard API

### Auth APIs

```text
POST /v1/dashboard/auth/login
POST /v1/dashboard/auth/logout
POST /v1/dashboard/auth/step-up
GET  /v1/dashboard/auth/me
```

`me` 返回：

- user_id
- username
- role
- permissions
- csrf_required
- session_expires_at
- step_up_until

### User APIs

```text
GET  /v1/dashboard/overview
GET  /v1/dashboard/agents
POST /v1/dashboard/agents
GET  /v1/dashboard/agents/{agent_id}
PATCH /v1/dashboard/agents/{agent_id}
DELETE /v1/dashboard/agents/{agent_id}
POST /v1/dashboard/agents/{agent_id}/rotate-token

GET  /v1/dashboard/tasks
POST /v1/dashboard/tasks
GET  /v1/dashboard/tasks/{task_id}
GET  /v1/dashboard/tasks/{task_id}/messages
GET  /v1/dashboard/tasks/{task_id}/progress

GET  /v1/dashboard/approvals
POST /v1/dashboard/approvals/{approval_id}/accept
POST /v1/dashboard/approvals/{approval_id}/reject

GET  /v1/dashboard/connections
POST /v1/dashboard/connections/{connection_id}/accept
POST /v1/dashboard/connections/{connection_id}/reject
PATCH /v1/dashboard/agents/{agent_id}/firewall

GET  /v1/dashboard/api-keys
POST /v1/dashboard/api-keys
POST /v1/dashboard/api-keys/{api_key_id}/revoke
```

### Admin APIs

```text
GET  /v1/admin/overview

GET  /v1/admin/users
GET  /v1/admin/users/{user_id}
POST /v1/admin/users/{user_id}/disable
POST /v1/admin/users/{user_id}/enable
POST /v1/admin/users/{user_id}/revoke-sessions
POST /v1/admin/users/{user_id}/revoke-api-keys

GET  /v1/admin/agents
GET  /v1/admin/agents/{agent_id}
POST /v1/admin/agents/{agent_id}/disable
POST /v1/admin/agents/{agent_id}/enable

GET  /v1/admin/tasks
GET  /v1/admin/tasks/{task_id}
POST /v1/admin/tasks/{task_id}/cancel
POST /v1/admin/tasks/{task_id}/expire

GET  /v1/admin/audit-logs
POST /v1/admin/audit-logs/export

GET  /v1/admin/system/health
```

### API 通用规则

- 所有列表分页。
- 默认 `limit=50`。
- 最大 `limit=200`。
- 支持 `offset` 或 cursor，首版可用 offset。
- 所有 admin mutation 写 audit。
- 所有 admin detail read 写 read audit，overview 轮询除外。
- 统一错误格式沿用 DomainException。

---

## 8. KPI and Query Performance

### 缓存策略

使用 Redis snapshot cache。

| KPI                  | TTL |
| -------------------- | --: |
| user overview        | 15s |
| admin overview       | 30s |
| system health        | 10s |
| user detail summary  | 30s |
| agent detail summary | 30s |

### 时间窗口

默认窗口：

```text
last 24h
```

可选窗口：

```text
1h
24h
7d
```

### 禁止行为

- Dashboard overview 每次请求全表 count。
- Admin 首页同步扫描 audit logs。
- 同步导出大量 audit。
- 无分页列表。
- 前端无限轮询 detail 页。
- 多 tab 同时高频刷新同一 heavy endpoint。

### 索引建议

为以下字段补索引：

- `tasks.status`
- `tasks.created_at`
- `tasks.updated_at`
- `tasks.created_by`
- `tasks.assigned_to`
- `messages.task_id`
- `messages.delivery_status`
- `approvals.status`
- `approvals.agent_id`
- `audit_logs.created_at`
- `audit_logs.actor_id`
- `audit_logs.action`
- `audit_logs.resource_type`
- `audit_logs.resource_id`
- `dashboard_sessions.user_id`
- `dashboard_sessions.session_hash`
- `dashboard_sessions.revoked_at`

---

## 9. Audit Design

### Mutation Audit

所有关键 mutation 写 audit：

- login success/failure。
- logout。
- step-up success/failure。
- create/update/delete agent。
- rotate token。
- create/revoke API key。
- accept/reject approval。
- accept/reject connection。
- update firewall。
- admin disable/enable user。
- admin disable/enable agent。
- admin cancel/expire task。
- audit export。

### Read Audit

管理员读敏感资源也写 audit：

- 查看用户详情。
- 查看 Agent 详情。
- 查看 Task 详情。
- 查看 Audit detail。
- 导出 audit。
- 查看用户 session summary。
- 查看用户 API key metadata。

不逐次审计：

- `/admin/overview` 短轮询。
- `/admin/system/health` 短轮询。
- 普通列表翻页，除非包含敏感 detail。

### Read Audit 字段

记录：

- viewer_user_id
- viewer_role
- action
- resource_type
- resource_id
- query_filters_hash
- request_ip
- user_agent
- created_at

禁止记录：

- secret
- token
- full API key
- full payload
- full result containing secrets

---

## 10. Frontend Component Strategy

基础组件：

- `AppShell`
- `AdminShell`
- `Sidebar`
- `TopBar`
- `DataTable`
- `StatCard`
- `StatusBadge`
- `RiskBadge`
- `RoleBadge`
- `FilterBar`
- `Pagination`
- `ConfirmDialog`
- `StepUpDialog`
- `DangerActionButton`
- `JsonPreview`
- `Timeline`
- `AuditEventRow`
- `EmptyState`
- `ErrorState`
- `LoadingState`
- `SecretMaskedText`

设计原则：

- SaaS / ops 工具风格。
- 信息密度高，但不拥挤。
- 不做 landing page。
- 默认第一屏就是 Dashboard。
- 管理员危险操作统一红色 danger style。
- 用户和管理员导航分开。
- 不把操作塞进表格太多，详情页承担复杂操作。
- 所有长文本、JSON、payload 默认折叠。
- 所有 token/key 统一脱敏组件。

---

## 11. Deployment

### Dev Compose

增加：

```text
web
```

暴露：

```text
5173:5173
```

环境变量：

```text
VITE_AGENTNET_API_BASE=http://localhost:8000
```

### Prod Compose

增加：

```text
web build
```

或由 nginx 服务静态文件。

nginx 规则：

- `/` redirect 到 `/app/overview`。
- `/app/*` SPA fallback。
- `/admin/*` SPA fallback。
- `/v1/*` proxy API。
- `/metrics` 继续内网限制。
- `/healthz` proxy API health。

安全头：

- Content-Security-Policy。
- X-Frame-Options。
- Referrer-Policy。
- Permissions-Policy。
- X-Content-Type-Options。

### 文档

新增：

- `docs/dashboard-user-guide.md`
- `docs/dashboard-admin-guide.md`
- `docs/dashboard-rbac.md`
- `docs/dashboard-security.md`
- `docs/dashboard-deploy.md`

更新：

- `README.md`
- `DEVELOPER_README.md`
- `docs/production-checklist.md`
- `docs/openapi.md`

---

## 12. Test Plan

### Backend Tests

Auth/session：

- login success。
- login invalid API key。
- logout revokes session。
- expired session rejected。
- idle timeout rejected。
- disabled user rejected。
- role change revokes/rotates session。
- session hash only stored。
- CSRF missing rejected。
- CSRF invalid rejected。
- GET does not require CSRF。
- step-up success sets window。
- step-up expired blocks high-risk operation。

RBAC：

- user cannot access `/v1/admin/*`。
- admin can read global resources。
- admin cannot disable user。
- super_admin can disable user after step-up。
- admin can cancel low-risk pending task。
- admin cannot cancel running task。
- super_admin can cancel running task after step-up。

Data isolation：

- user dashboard only sees own agents/tasks/approvals/connections。
- user cannot access another user's task detail。
- user cannot approve another user's approval。
- user cannot manage another user's firewall。

KPI/cache：

- overview uses Redis cache。
- cache miss computes once。
- repeated request hits cache。
- limit max enforced。
- large audit export not synchronous.

System safety：

- system health response contains no `DATABASE_URL`。
- contains no `REDIS_URL`。
- contains no password/token/key。
- contains no full environment dump。

Audit:

- admin detail read writes read audit。
- admin mutation writes mutation audit。
- overview polling does not spam read audit。
- audit details are secret-free。

### Frontend Tests

- Login page success/error。
- User route guard。
- Admin route guard。
- Sidebar changes by role。
- User overview loads KPI。
- Agent list and Agent detail render。
- Task list and Task detail render。
- Approval page separates Task Action Approvals and Connection Approvals。
- Connection Firewall page renders policy and pending requests。
- API key page masks key prefix。
- Admin overview renders global KPI。
- Admin users/agents/tasks/audit/system pages render。
- DangerActionButton requires confirm。
- StepUpDialog appears for high-risk operation。
- 401/403/503/STEP_UP_REQUIRED states are readable。

### E2E Tests

- User login -> create/view Agent -> view task list。
- User handles task approval。
- User handles connection approval。
- User edits Agent Firewall。
- Admin login -> view global overview -> inspect user -> audit read written。
- Admin forbidden from super_admin action。
- Super admin step-up -> disable Agent -> audit written。
- System page does not display secret strings。

### Production Checks

- `npm run build`
- `npm test`
- `python -m pytest -q`
- OpenAPI export/check。
- Docker compose dev config。
- Docker compose prod config。
- nginx config validation。
- smoke test `/app/overview`、`/admin/overview`、`/v1/dashboard/auth/me`。

---

## 13. Implementation Order

每个阶段完成后都必须生成对应报告，例如 `reports/web_phase_1_report.md`。没有报告、没有失败路径验证、没有真实代码审查的阶段不能进入下一阶段。

1. 数据库迁移：User RBAC、dashboard_sessions、必要索引；生成 `reports/web_phase_1_report.md`。
2. 后端 session/auth/CSRF/step-up 基础设施；生成 `reports/web_phase_2_report.md`。
3. 后端 RBAC dependency 和 permission helpers；生成 `reports/web_phase_3_report.md`。
4. 用户 Dashboard API；生成 `reports/web_phase_4_report.md`。
5. Admin API 和 audit read/write 扩展；生成 `reports/web_phase_5_report.md`。
6. KPI Redis cache 和 system health summary；生成 `reports/web_phase_6_report.md`。
7. 前端 `apps/web` 初始化和组件层；生成 `reports/web_phase_7_report.md`。
8. 用户控制台页面；生成 `reports/web_phase_8_report.md`。
9. 管理员运营台页面；生成 `reports/web_phase_9_report.md`。
10. Docker/nginx/生产配置；生成 `reports/web_phase_10_report.md`。
11. 测试补齐、E2E 和截图检查；生成 `reports/web_phase_11_report.md`。
12. README、专项文档和 OpenAPI 更新；生成 `reports/web_phase_12_report.md`。
13. 最后一轮安全审查、生产 checklist 和上线风险评估；生成 `reports/web_final_report.md`。

## Assumptions

- 本轮不引入 Organization，多租户先基于 User 隔离。
- 本轮不接 OIDC/SSO，但 session/role 模型为未来 OIDC 留接口。
- Step-up v1 使用重新输入 API key，未来可替换为 WebAuthn/OIDC MFA。
- Dashboard 不展示完整 secret，不提供 secret reveal 功能。
- Dashboard 首版使用短轮询，不新增浏览器 WebSocket。
- Grafana 继续负责底层 Prometheus 指标深挖；AgentNet Dashboard 负责业务运营和安全操作。

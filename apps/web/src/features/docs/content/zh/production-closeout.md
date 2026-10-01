# AgentNet 生产收尾计划

本文定义当前开发轮次结束后的最终生产收尾工作。它刻意比功能检查表更严格：
只有当代码路径、配置、测试、文档和运维证据全部对齐时，一项才算通过。

当前已验证的后端基线：

```text
python -m pytest -q
440 passed, 31 warnings
```

这意味着后端测试套件在干净的、已迁移的测试数据库中全部通过。但它本身并不
代表平台已准备好承接公共生产流量。

## 发布定位

当前代码库适用于：

- 受控的内部测试。
- 预发布（staging）验证。
- 用户已知、运维有人监督的私有试点部署。
- 演示 AgentNet 路由运行时、控制台、出口网关、专属通道核心服务行为、
  SLA 指标与业务连续性原语。

当前代码库尚不适用于：

- 无人监督的公共 SaaS 上线。
- 有严格合规要求的企业生产。
- 智能体可以绕过平台网络控制的环境。
- 需要正式事件响应、告警路由、备份恢复证明和多小时故障演练的部署。

## 收尾的第一性原则

1. 生产就绪是运维属性，而不仅仅是测试结果。
2. 只有真实生产路径用上了某个功能，这个功能才算完成。
3. 任何依赖故障都不得返回伪造的成功。
4. 安全策略必须先于路由打分、性能优化或便利性被强制执行。
5. 控制台页面必须暴露运维真相，同时不泄露密钥。
6. 验收需要正向路径与失败路径双方面的证据。
7. 每次生产变更都必须有回滚路径。

## 必须完成的生产收尾项

### P0. Egress 强制执行

状态：**应用层契约已完成。公共生产仍需网络层强制执行。**

当前状态：

- `egress_service.py` 实现了域名允许列表、基于环境变量的密钥注入、高风险审批、
  Redis 速率限制、GET 缓存、成本跟踪、egress 日志以及 Redis 故障的 fail-closed
  处理。
- `AdapterContext.external_request()` 是适配器发起外联 HTTP 调用的唯一受许可方式，
  它在应用层强制执行 egress 策略。
- `adapter_service.py` 向它创建的每个 AdapterContext 注入
  `proxy_external_request` 回调。未配置网关时尝试使用
  `context.external_request()` 的适配器会得到 `RuntimeError`（fail closed）。
- `test_egress_contract.py` 有 7 个测试证明该契约：走网关、无网关 fail closed、
  无代理 fail closed、拒绝传播、速率限制传播、审批传播、body/头转发。
- OpenClaw 适配器通过 subprocess 在本地执行 CLI 命令，它自身并不发起外联 HTTP
  调用。如果 CLI 工具本身发起外联调用，那些调用会绕过应用层代理。
- **网络层强制执行**（Kubernetes 网络策略、防火墙规则、服务网格 egress 网关）
  尚未验证。公共生产必须有这一层，才能防止 subprocess 级别的绕过。

剩余必做项：

- 在生产环境中尽可能加入网络层控制（Kubernetes 网络策略、防火墙、服务网格）。
- 记录纵深防御模型：应用层契约 + 网络层限制。
- 补充测试，证明行为异常的适配器子进程在网络受限环境中无法访问被拒绝的域名。

验收证据：

- ✅ 适配器契约测试覆盖：允许域名、拒绝域名、缺失密钥、智能体自带
  Authorization 头、速率限制、缓存命中与高风险审批。
- ✅ 应用层 egress 强制执行：所有适配器都经由 `proxy_external_request()`。
- ⬜ 在预发布环境中，被拒绝的外联域名在网络层 fail closed 的实跑记录。
- ⬜ 展示如何限制直连外联流量的生产配置文档。

### P1. 专属通道管理 API

状态：**已完成。**

- `/v1/dashboard/admin/dedicated-channels/` 下的 8 个 REST 接口，支持完整 CRUD、
  启用/禁用、健康检查。
- 所有写操作要求 `super_admin:write` + 增强验证。
- 所有读操作要求 `admin:read`。
- `super_admin:write` 权限已加入 `ROLE_PERMISSIONS['super_admin']`。
- `connection_config` 与 `encryption_config` 中的密钥在响应层通过
  `_mask_secrets()` 遮蔽，覆盖 dict、嵌套 dict、dict 列表和深层嵌套结构。
- 全部 9 个接口都包含 `write_audit()` 调用，读操作与写操作均有审计。
- 健康检查接口使用 `ChannelHealthCheck` 模型做持久化记录。
- `test_dedicated_channel_api.py` 中有 30 个测试，覆盖 schema 校验、mask_secrets
  （含 dict 列表）、from_channel 遮蔽、认证拒绝、RBAC 校验、ErrorCode 常量与
  适配器服务配置。

### P2. Web UI 更新

状态：企业运维必需，纯开发者私有试点非必需。

当前 Web 控制台已覆盖用户/管理员基础功能。若要投入企业生产运维，需要更新，
因为若干路由运行时新功能在 UI 中只是部分可见。

必做的 UI 更新：

- 管理员网络概览：
  - 按类型展示中继健康：central、personal edge、local edge、regional、egress、
    dedicated。
  - 队列深度、当前负载、延迟、成功率、回退次数。
  - 明确的降级/宕机指示。
- 路由决策：
  - 任务选定的路由。
  - 候选路由。
  - 拒绝原因。
  - 命中的路由策略。
  - 路由租约 ID 与过期时间。
  - 回退原因（如存在）。
- 任务详情：
  - 投递时间线：queued、route_selected、delivering、delivered、acknowledged、
    delivery_failed、expired。
  - 执行时间线：created、received、accepted、running、progress、waiting_input、
    succeeded、failed、expired。
  - 路由决策摘要。
- Egress 日志：
  - 网关、域名、请求类型、状态码、延迟、成本估计、审批 ID。
  - 按网关、智能体、任务、域名、状态筛选。
  - 不含请求体密钥与 Authorization 头。
- 专属通道：
  - 通道类型、源/目标智能体、状态、最近健康检查、延迟、丢包率、带宽。
  - 超级管理员的启用/禁用/吊销控件，需 增强验证。
- SLA 与连续性：
  - SLA 目标。
  - SLA 违规。
  - 熔断器状态。
  - 故障转移配置与事件。
  - 手动故障转移/回滚控件，置于 super_admin + 增强验证 之后。
- 系统页：
  - 保持仅展示摘要的行为。
  - 不展示连接字符串、环境变量、原始密钥、私钥、完整 token 或完整 payload。

首次企业收尾不需要：

- 营销落地页。
- 完整的可视拓扑图编辑器。
- 实时动画网络地图。
- 多租户计费 dashboard。

UI 验收证据：

- 每个新页面的组件测试。
- 路由/egress/SLA/连续性接口的 API 客户端测试。
- 覆盖登录、管理员导航、路由决策详情、egress 日志与 SLA 页面的浏览器冒烟测试。
- 最终发布候选的截图保存在 `reports/` 下。
- 人工复查确认 UI 中看不到任何密钥值。

### P3. 可观测性与告警

状态：**告警规则与 dashboard 面板已完成。告警路由与演练证据仍需补足。**

当前状态：

- `infra/prometheus/alerts/agentnet.yml` 中的 Prometheus 告警规则覆盖全部紧急与
  告警状态（17 条）：API 不可用、5xx 比率、延迟、WS 连接数、断连激增、待处理
  消息、任务过期、ack 超时、处理超时、worker 错误、审批待定、egress 失败、
  路由回退、SLA 违规、熔断器打开、故障转移触发、Redis 不可用、Postgres 不可用、
  依赖降级。
- Grafana dashboard `agentnet-overview.json` 包含 API 指标、WebSocket、任务、
  消息、审批、重试/worker 错误的面板，外加三个新区域：出口网关（Phase 16）、
  路由决策（Phase 12）、SLA 与连续性（Phase 18）。
- Prometheus 指标定义在 `metrics.py` 并注入到服务层：
  `EGRESS_REQUESTS_TOTAL`、`EGRESS_LATENCY_MS`、`ROUTE_DECISIONS_TOTAL`、
  `ROUTE_FALLBACK_TOTAL`、`SLA_VIOLATIONS_TOTAL`、`CIRCUIT_BREAKER_STATE`、
  `FAILOVER_EVENTS_TOTAL`、`HEALTH_CHECK_STATUS`。
- 健康探针：`/healthz`（存活）与 `/readyz`（PG/Redis 依赖深检），并更新
  Prometheus gauge。
- 速率限制器跳过这两个健康接口。

剩余必做项：

- 定义告警目的地（邮件、webhook、PagerDuty、Slack 等）。
- 在预发布环境至少触发一次合成告警并验证确认。
- 验证告警 payload 上下文充分且不含密钥。

验收证据：

- ✅ `promtool` 校验通过告警规则。
- ✅ Grafana dashboard 导入成功（23 个面板，4 个区域）。
- ✅ 健康探针 `/healthz` 与 `/readyz` 功能正常。
- ✅ 速率限制器跳过健康接口。
- ⬜ 预发布环境中合成告警已触发并确认。
- ⬜ 告警 payload 已验证上下文与密钥安全。

### P4. 故障注入与业务连续性演练

状态：上线生产前必做。

必做演练：

- Redis 不可用：
  - API 不得假装智能体在线。
  - 限流器/会话/egress 缓存故障在需要时 fail closed。
- PostgreSQL 不可用：
  - 任务创建必须明确失败。
  - 不得返回伪造的任务 ID 或成功响应。
- API 重启：
  - WebSocket 重连与会话恢复必须找回未确认的待处理消息。
- Worker 重启：
  - 重试、超时、SLA 与连续性 worker 从持久化状态恢复。
- 中继降级/宕机：
  - 路由选择遵守策略。
  - 仅当策略允许时才重路由。
  - 被拒绝的回退 fail closed，并留存路由决策/审计证据。
- Egress 网关禁用/宕机：
  - 外联调用失败或等待审批；智能体不得绕过网关。
- 专属通道宕机：
  - 通道不可用被记录。
  - 策略控制其失败或重路由行为。

验收证据：

- `reports/production_drill_<date>.md` 下的演练报告。
- 执行过的命令。
- 预期结果对比实际结果。
- 展示审计、路由决策、指标与告警证据的日志或截图。
- 回滚与恢复记录。

### P5. 备份、恢复与迁移准备

状态：上线生产前必做。

必做项：

- 在类预发布数据上执行真实备份。
- 把它恢复到一个干净的数据库。
- 恢复后验证应用健康。
- 部署前后均记录迁移 head。
- 确认失败迁移的降级或恢复策略。

备份演练脚本（`scripts/backup-restore-drill.sh`）是 fail-closed 的：

- 每个关键步骤都必须成功，不存在静默回退或 `|| true` 守卫。
- healthz 校验使用 JSON 解析（`{"status":"alive"}`）而非字符串字面量 grep。
- PostgreSQL dump 完整性检查失败即中止演练（exit 1）。
- Redis 备份：检测持久化模式（RDB 还是 AOF）。若两种文件都不存在且未启用
  AOF，演练直接失败，而不是静默继续。
- 元数据记录（API key/任务数）要求 API 响应成功；认证或连接失败即中止演练。
- 必须设置 `AGENTNET_API_KEY` 环境变量；未设置时脚本立即退出。

验收证据：

- 备份文件与校验和已生成。
- 恢复命令执行成功。
- `alembic current` 返回预期的版本。
- 恢复后冒烟测试通过。
- 演练脚本仅在全部步骤通过时 exit 0；任何关键失败即 exit 1。

### P6. 密钥管理与轮换

状态：上线生产前必做。

必做项：

- 不在 Git 中保存真实密钥。
- 让 `.env.production` 脱离版本控制。
- 替换所有 `CHANGE_ME` 值。
- 为以下各项确定负责人与轮换周期：
  - PostgreSQL 密码。
  - Redis 密码。
  - 控制台会话密钥或签名材料（若引入）。
  - API key。
  - 智能体 token。
  - Egress 网关密钥。
  - TLS 证书。
- 企业生产环境中应超越 `env:` 形式的 egress 密钥引用，或者说明首个私有试点
  仅用 env 为何可接受。

验收证据：

- 密钥清单已完成。
- 轮换手册已至少针对一个 API key、一个智能体 token 和一个基础设施密钥试跑过。
- 已验证日志不含密钥值。

### P7. 生产部署验证

状态：上线生产前必做。

必做项：

- 使用生产 Docker Compose 或等价方案部署。
- 为 `andrewhyc.top` 启用 HTTPS。
- 验证 WSS 可以通过 nginx。
- 验证安全 cookie：
  - `SESSION_SECURE_COOKIE=true`。
  - 会话 cookie 为 HttpOnly。
  - CSRF 行为正常。
- 验证 API 除既定公共入口外不直接暴露。
- 验证 PostgreSQL 与 Redis 不对公网暴露。

验收证据：

- `curl https://andrewhyc.top/healthz` 返回健康状态。
- 浏览器在 HTTPS 下可登录。
- WebSocket 通过 WSS 连接成功。
- 控制台加载的是生产构建，不是 Vite 开发服务器。
- nginx access/error 日志显示符合预期的代理行为。

## Web UI 决策

Web UI 是否需要更新？

企业生产需要。若运维人员可以接受用 API/SQL 完成高级路由操作，小型私有试点
则不需要。

公共或企业生产必需：

- 路由决策可见性。
- 任务详情上的投递时间线。
- 网络/中继健康页。
- Egress 日志页。
- 专属通道管理页。
- SLA/连续性页。
- 危险操作的超级管理员 增强验证。

私有试点可延后：

- 若通道由人工配置，可延后专属通道 CRUD UI。
- 若运维使用 Grafana，可延后 SLA 可视化图表。
- 完整拓扑可视化。

不得延后：

- 密钥遮蔽。
- RBAC。
- 高危管理员操作的 增强验证。
- 系统页无密钥规则。
- 清晰的任务投递状态。

## 生产验收标准

只有以下全部强制标准通过，本次发布才可接受为生产就绪。

### 代码与测试

- 后端完整测试套件在干净的、已迁移的数据库中通过。
- Web 单元/组件测试通过。
- Web 生产构建通过。
- OpenAPI 导出已重新生成并检查漂移。
- 任何生产代码路径都不允许在依赖缺失或功能未实现时返回成功。
- 仓库、日志、报告、截图和生成产物中不出现真实密钥。

### API 与运行时

- 任务创建返回明确的状态与投递状态。
- 消息投递事件被持久化。
- ack 把消息状态改为 acknowledged。
- 离线队列与会话恢复能找回未确认的消息。
- 路由任务的路由决策被持久化。
- 路由租约过期、吊销、消息数上限、字节数上限和允许任务类型限制均被强制执行。
- 策略拒绝不能被回退绕过。

### 安全

- 控制台会话与 CSRF 防护在 HTTPS 下正常工作。
- RBAC 阻止未授权的 user/admin/super_admin 访问。
- 高危管理员操作要求 增强验证。
- 智能体 token 与 API key 以 hash 存储，且仅展示一次。
- Egress 密钥不暴露给智能体。
- 系统健康页不泄露密钥或完整环境变量值。

### Egress

- 允许的外联请求经 出口网关 成功。
- 被拒绝的域名 fail closed。
- 缺失 egress 密钥 fail closed。
- 配置了网关托管密钥时，智能体自带的 Authorization 头被拒绝。
- Egress 速率限制以 429 限流。
- Egress 速率/缓存路径上的 Redis 故障以 503 fail closed。
- 高风险外联操作创建审批，且在审批前不执行。

### 专属通道

- 仅当通道启用、已授权、策略允许且健康时才被选中。
- 缺失或无效的健康报告把通道标记为宕机。
- 专属通道的数据库/查询错误 fail closed。
- 通道宕机行为是明确的：按策略失败或重路由。
- 所有写操作都被审计。

### 可观测性

- `/metrics` 已被保护，不对公共暴露。
- Prometheus 抓取 API 与基础设施 exporter。
- Grafana dashboard 可导入。
- 关键告警已定义并测试。
- SLA 违规可查询。
- 故障转移事件可查询。

### 运维

- 生产部署可按文档化命令复现。
- 备份与恢复经过测试。
- 回滚路径已文档化。
- 针对密钥泄露、数据库故障、Redis 故障和 egress 故障存在事件处理手册。
- 至少完成并记录一次预发布故障演练。

## 发布门禁

上线前使用此决策表。

| 门禁 | 要求结果 | 上线决策 |
|------|-----------------|-----------------|
| 后端测试 | 干净 DB 下全套通过 | 必需 |
| Web 测试/构建 | 单元测试与生产构建通过 | 必需 |
| HTTPS/WSS | 真实域名可用 | 必需 |
| Egress 强制执行 | 适配器与网络层强制执行均已验证 | 公共生产必需 |
| 专属通道 CRUD | 存在 API/UI 或已文档化的运维流程 | 企业专属通道必需 |
| 可观测性 | 告警与 dashboard 已测试 | 必需 |
| 备份/恢复 | 恢复演练通过 | 必需 |
| 密钥轮换 | 手册已试跑 | 必需 |
| 故障演练 | Redis/Postgres/API/Egress/Relay 场景已记录 | 必需 |

## 建议的收尾顺序

1. 完成 Egress 适配器集成与网络层限制。
2. 如需企业通道管理，添加专属通道 schema/router 与管理员 UI。
3. 更新控制台的路由决策、egress 日志、专属通道、SLA 与连续性页面。
4. 重新生成 OpenAPI 并更新 API 文档。
5. 在干净数据库上运行后端、Web、浏览器与 WebSocket E2E 测试。
6. 以类生产 TLS 与 WSS 部署预发布环境。
7. 执行备份/恢复与故障演练。
8. 验证可观测性与告警路由。
9. 生成最终的 `reports/production_acceptance_<date>.md`。
10. 仅当所有必需门禁通过时才批准上线。

## 最终验收报告模板

在以下路径创建报告：

```text
reports/production_acceptance_<YYYY-MM-DD>.md
```

最少内容：

- commit 或构建标识。
- 部署环境。
- 使用的配置文件。
- 迁移版本。
- 后端测试结果。
- Web 测试/构建结果。
- 浏览器 E2E 结果。
- WebSocket E2E 结果。
- OpenAPI 漂移结果。
- 备份/恢复证据。
- 密钥扫描结果。
- 可观测性验证。
- 故障演练摘要。
- Web UI 复查结果。
- 安全复查结果。
- 已知风险。
- Go/no-go 决策。

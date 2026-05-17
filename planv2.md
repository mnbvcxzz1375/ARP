# AgentNet / Agent Relay Platform - Plan v2

## Phase 11: 生产化质量闭环与运维基础

本文档是 AgentNet 在 Phase 0-10 MVP 完成后的下一轮增强计划，目标是把项目从“本地 MVP 可运行”推进到“可持续集成、可部署、可观测、可恢复、可审计运营”的产品化原型。

本计划面向 Codex 或其他工程执行者，要求每个子阶段都有明确交付物、真实验证命令、验收标准和审查报告。禁止兜底成功、轻量验收、假数据验收或生产路径 mock fallback。

---

## 0. 当前基线

当前项目已经完成以下能力：

- Agent Registry: 用户、API key、Agent、Agent token、Agent Number。
- WebSocket Presence: Agent token 认证、连接管理、heartbeat、在线状态。
- Task / Message: 任务状态机、消息存储、幂等、lease、progress、result。
- Relay Routing: 在线投递、离线队列、ack、retry、TTL。
- Connection Policy: `private`、`contacts_only`、`request_approval`、`public`。
- Human-in-the-loop Approval: request、accept、reject、expire。
- Python SDK: REST client、Agent runtime、WebSocket、SessionStore、IdempotencyCache。
- CLI: login、agent、connect、task、approve。
- OpenClaw Adapter: 安全执行、路径校验、最小环境变量、无生产 fallback。
- Hardening: rate limit、payload limit、timeout worker、audit logs、结构化错误。
- 文档: 用户 README、开发者 README、基础 docs。

本轮不重新规划 Phase 0-10，不重写核心业务，不实现 Dashboard，不实现 E2EE，不引入 Kubernetes，不做去中心化、gas 或链上结算。

---

## 1. 全局执行约束

### 1.1 不允许兜底成功

以下行为禁止出现在生产路径：

- 依赖缺失时自动切换到 mock、fake、memory-only 或 silent mode。
- 捕获异常后返回看似成功的默认结果。
- Redis、Postgres、rate limiter、adapter runner 失败后静默放行。
- 未实现功能返回成功占位。

允许的例外：

- 测试专用 fake，但必须只存在于测试路径或显式 test 模式。
- 清理资源时吞掉二次异常，例如关闭 WebSocket 或取消后台 task。
- 幂等 ack 未找到消息时 no-op。

### 1.2 不接受轻量验收

每个子阶段必须包含：

- 文件交付物。
- 自动化测试或可执行验证命令。
- 失败路径验证。
- 文档更新。
- 执行报告。

如果某项验证因本地环境无法执行，报告必须明确写出阻塞原因、替代静态验证结果和未完成风险，不能宣称完整通过。

### 1.3 安全和审计要求

- 不提交真实 secret、token、password、private key。
- `.env.production` 不进入版本控制，只提交 `.env.production.example`。
- 日志和报告不得包含 API key、Agent token、数据库密码或用户敏感 payload。
- 所有新增运维流程必须说明审计点和回滚策略。

### 1.4 审查要求

每个子阶段完成后必须生成报告：

```text
reports/phase11_x_report.md
```

报告至少包含：

- 新增和修改文件。
- 执行过的命令。
- 测试结果。
- 未完成项。
- 风险和后续建议。
- 人工审查结论。

审查不只看测试是否通过，还必须审查真实代码、配置和文档是否达到需求。

---

## 2. Phase 11 总目标

本轮完成后，项目应具备：

1. GitHub Actions CI/CD 质量门禁。
2. Docker Compose VPS 生产配置模板。
3. 可导出的 OpenAPI 文档和 API 示例。
4. 真实 WebSocket 端到端集成测试。
5. Postgres 备份和恢复方案。
6. Secret 管理和密钥轮换运营流程。
7. Prometheus + Grafana 观测性面板和告警。
8. 完整生产化文档索引和交付检查表。

默认技术选择：

- CI/CD: GitHub Actions。
- 部署形态: 单机 Docker Compose VPS。
- 观测栈: Prometheus + Grafana。
- 持久化事实源: PostgreSQL。
- Redis 定位: pending queue 和 rate limit，不作为长期事实源。

---

## 3. Phase 11.1 - CI/CD

### 目标

建立 GitHub Actions 质量门禁，保证每次 push 和 pull request 都能验证 API、SDK、CLI、Adapter、协议契约、Docker 配置和迁移健康。

### 交付物

- `.github/workflows/ci.yml`
- `.github/workflows/release-check.yml`
- `scripts/ci/install.ps1`
- `scripts/ci/install.sh`
- `scripts/ci/run-tests.ps1`
- `scripts/ci/run-tests.sh`
- `scripts/ci/check-compose.ps1`
- `scripts/ci/check-compose.sh`
- `scripts/ci/check-compile.ps1`
- `scripts/ci/check-compile.sh`
- `docs/ci-cd.md`
- `reports/phase11_1_report.md`

### 实施要求

`ci.yml` 在 `push` 和 `pull_request` 时运行：

- Checkout repo。
- Setup Python 3.11。
- 安装本地 editable packages:
  - `apps/api[test]`
  - `packages/python-sdk`
  - `packages/cli`
  - `adapters/base`
  - `adapters/openclaw`
- 启动 PostgreSQL 和 Redis service containers。
- 执行完整测试。
- 执行协议契约测试收集检查。
- 执行 compileall。
- 执行 Docker Compose config 检查。
- 执行 Alembic upgrade smoke。

`release-check.yml` 手动触发：

- 复用 CI 全部检查。
- 导出 OpenAPI。
- 校验生产 compose。
- 校验 `.env.production.example` 字段完整性。
- 执行 backup/restore dry-run。
- 校验 Prometheus 配置和告警规则。
- 生成 release checklist artifact。

### 验证命令

```powershell
python -m pytest -q
python -m pytest apps/api/tests/test_protocol_contract.py --collect-only -q
python -m compileall adapters/openclaw/agentnet_openclaw packages/python-sdk/agentnet packages/cli/agentnet_cli apps/api/app
docker compose -f infra/docker-compose.yml -f infra/docker-compose.dev.yml config
```

### 验收标准

- GitHub Actions 在干净环境全绿。
- 根目录 `python -m pytest -q` 保持可用。
- workflow 失败时能定位到具体模块。
- CI 不依赖本机私有路径或真实 secret。
- release-check 可手动触发并生成 artifact。

---

## 4. Phase 11.2 - 生产配置模板

### 目标

提供一套单机 VPS 可部署的生产模板，覆盖 API、Postgres、Redis、nginx、持久化卷、环境变量、健康检查和安全默认值。

### 交付物

- `infra/docker-compose.prod.yml`
- `infra/.env.production.example`
- `infra/nginx/agentnet.conf`
- `infra/nginx/README.md`
- `docs/production-deploy.md`
- `docs/production-checklist.md`
- `reports/phase11_2_report.md`

### 实施要求

生产 compose 包含：

- `api`
- `postgres`
- `redis`
- `nginx`
- `prometheus`
- `grafana`

生产模板安全默认值：

- API 不直接暴露公网，只由 nginx 代理。
- nginx 支持 WebSocket upgrade。
- nginx body size 与 `MAX_PAYLOAD_BYTES` 对齐。
- Postgres 不暴露公网端口。
- Redis 不暴露公网端口。
- Grafana 默认只绑定本机或受限端口，文档说明如何通过 SSH tunnel 访问。
- 所有 secret 从 `.env.production` 读取。

`.env.production.example` 至少包含：

```text
AGENTNET_ENV=production
LOG_LEVEL=INFO
DATABASE_URL=
REDIS_URL=
MAX_PAYLOAD_BYTES=1048576
WS_HEARTBEAT_INTERVAL_S=15
WS_HEARTBEAT_TIMEOUT_S=45
WS_MAX_CONNECTIONS_PER_AGENT=3
RATE_LIMIT_WINDOW_S=60
RATE_LIMIT_GLOBAL_MAX=1000
RATE_LIMIT_USER_MAX=300
RATE_LIMIT_AGENT_MAX=200
RATE_LIMIT_IP_MAX=100
TASK_MAX_RUNTIME_S=600
TASK_LEASE_DURATION_S=60
TIMEOUT_WORKER_INTERVAL_S=30
POSTGRES_DB=agentnet
POSTGRES_USER=agentnet
POSTGRES_PASSWORD=CHANGE_ME
REDIS_PASSWORD=CHANGE_ME
GRAFANA_ADMIN_USER=admin
GRAFANA_ADMIN_PASSWORD=CHANGE_ME
PUBLIC_BASE_URL=https://example.com
```

### 验证命令

```powershell
docker compose -f infra/docker-compose.prod.yml --env-file infra/.env.production.example config
```

### 验收标准

- 生产 compose config 通过。
- 文档能指导从空 VPS 启动服务。
- 文档包含启动、停止、升级、回滚、日志查看、健康检查。
- `.env.production.example` 不包含真实 secret。

---

## 5. Phase 11.3 - OpenAPI 文档

### 目标

把 FastAPI 自动文档提升为可交付 API 文档，包含稳定 schema、示例请求、示例响应、错误格式和认证说明。

### 交付物

- `scripts/export_openapi.py`
- `packages/protocol/openapi/agentnet.openapi.json`
- `packages/protocol/openapi/agentnet.openapi.yaml`
- `docs/openapi.md`
- `docs/api-examples.md`
- `reports/phase11_3_report.md`

### 实施要求

- `scripts/export_openapi.py` 支持：
  - 默认导出 JSON。
  - `--yaml` 导出 YAML。
  - `--check` 校验当前导出与仓库文件一致。
- 所有 router 补充 summary 和 description。
- 关键 schema 补充 `Field(description=...)`。
- 文档明确认证方式：
  - REST: `Authorization: Bearer ak_...`
  - REST legacy: `X-API-Key`
  - WebSocket: `Authorization: Bearer agt_sk_...`
- API examples 覆盖：
  - 注册用户。
  - 创建 Agent。
  - 轮换 Agent token。
  - 创建任务。
  - 指定 `from_agent_number`。
  - 查看 task messages。
  - 查看 task progress。
  - connection request / accept / reject。
  - approval list / accept / reject。

### 验证命令

```powershell
python scripts/export_openapi.py
python scripts/export_openapi.py --check
```

### 验收标准

- OpenAPI JSON 稳定生成并纳入版本控制。
- OpenAPI YAML 可生成；如缺依赖，脚本必须明确失败并提示安装方式。
- CI 校验 OpenAPI 未漂移。
- 文档至少包含一条完整 Agent 创建到 task 完成的示例链路。

---

## 6. Phase 11.4 - 真实 WebSocket 端到端集成测试

### 目标

补齐 API + SDK + WebSocket 的真实链路测试，确认 Agent 连接、任务投递、ack、离线队列和 session.resume 不是只在单元测试中成立。

### 交付物

- `apps/api/tests/test_websocket_e2e.py`
- `packages/python-sdk/tests/test_websocket_integration.py`
- `apps/api/tests/helpers/ws_e2e.py`，如需要。
- `reports/phase11_4_report.md`

### 必测场景

- Agent 使用 `Authorization: Bearer agt_sk_...` 成功连接。
- 无 token、错误 token、API key 当 Agent token 使用时连接失败。
- 连接时携带 `session_id`，服务端返回 `session.resume_result`。
- receiver Agent 在线时，sender 创建 task 后 receiver 收到 `task.request`。
- `task.request` 包含顶层 `task_id`、`message_id`、`payload`。
- SDK handler 收到完整 envelope。
- SDK 自动 ack 后，服务端 message `delivery_status` 更新为 `acked`。
- receiver 离线时 task 进入 pending，重新连接后收到 pending。
- 使用同一 `session_id` 和 `last_message_id` 执行 `session.resume`。
- 重复投递同一 `message_id` 时 SDK 幂等去重并 re-ack，不重复执行 handler。

### 实施约束

- 不依赖公网网络。
- 不使用生产 mock fallback。
- 可以使用本地 ephemeral port 启动 uvicorn。
- Redis 可使用测试隔离实例或 mock Redis，但必须覆盖 pending queue 与 ack cleanup 行为。
- 测试结束必须清理连接、session 和后台 task。

### 验证命令

```powershell
python -m pytest apps/api/tests/test_websocket_e2e.py -q
python -m pytest packages/python-sdk/tests/test_websocket_integration.py -q
python -m pytest -q
```

### 验收标准

- E2E 测试进入根目录全量测试。
- 失败时能定位认证、投递、ack、resume 或 SDK handler。
- CI 默认运行，不作为手动测试。

---

## 7. Phase 11.5 - 数据库备份和恢复

### 目标

提供单机生产部署下可执行的 Postgres 备份、恢复、校验和演练流程。

### 交付物

- `scripts/backup/postgres_backup.ps1`
- `scripts/backup/postgres_backup.sh`
- `scripts/backup/postgres_restore.ps1`
- `scripts/backup/postgres_restore.sh`
- `scripts/backup/README.md`
- `docs/backup-restore.md`
- `reports/phase11_5_report.md`

### 备份要求

- 使用 `pg_dump` custom format。
- 文件命名：

```text
agentnet_YYYYMMDD_HHMMSS.dump
agentnet_YYYYMMDD_HHMMSS.dump.sha256
```

- 默认保存到 `backups/postgres`。
- 支持环境变量：
  - `BACKUP_DIR`
  - `DATABASE_URL`
  - `RETENTION_DAYS`
- 支持 `--help` 和 `--dry-run`。

### 恢复要求

- 默认要求显式确认。
- 支持 `--dry-run`。
- 恢复前检查：
  - 备份文件存在。
  - checksum 匹配。
  - 目标数据库连接可用。
  - 当前环境不会误操作生产，除非传入显式确认参数。
- 恢复流程：
  - 停止 API。
  - 创建恢复前快照。
  - 执行 `pg_restore --clean --if-exists`。
  - 执行 `alembic current`。
  - 启动 API。
  - 检查 `/healthz`。

### Redis 边界

- Redis 不作为长期事实源备份。
- Redis 中 pending queue 和 rate limit 数据可以丢失。
- 如果未来需要重建 pending queue，应以 Postgres `messages` 为事实源新增 rebuild worker。本轮只记录边界，不实现 rebuild worker。

### 验证命令

```powershell
./scripts/backup/postgres_backup.ps1 --help
./scripts/backup/postgres_backup.ps1 --dry-run
./scripts/backup/postgres_restore.ps1 --help
./scripts/backup/postgres_restore.ps1 --dry-run
```

### 验收标准

- 脚本 help 和 dry-run 可运行。
- 文档包含每日备份计划任务示例。
- 文档包含每月恢复演练流程。
- release-check 至少校验脚本存在和 dry-run。

---

## 8. Phase 11.6 - Secret 管理和密钥轮换

### 目标

明确 secret 分类、存储位置、轮换周期、轮换步骤、泄露响应和审计要求。

### 交付物

- `docs/secrets-rotation.md`
- `docs/incident-secret-leak.md`
- `scripts/ops/rotate_agent_token.md`
- `scripts/ops/rotate_api_key.md`
- `scripts/ops/rotate_database_password.md`
- `reports/phase11_6_report.md`

### Secret 分类

- User API key: `ak_...`
- Agent token: `agt_sk_...`
- Postgres password。
- Redis password。
- Grafana admin password。
- TLS private key。
- CI secrets。
- 外部服务 token，未来扩展用。

### 存储策略

- Docker Compose VPS 默认使用 `.env.production`。
- `.env.production` 权限限制为 owner read/write。
- GitHub Actions 使用 GitHub Secrets。
- CLI 本地配置文件必须在文档中说明权限风险。
- 不引入云 Secret Manager。

### 轮换流程

API key：

- 创建新 key。
- 更新使用方配置。
- 验证新 key。
- revoke 旧 key。
- 记录审计。

Agent token：

- 调用 rotate token API。
- 更新 Agent 环境变量。
- 重启 Agent。
- 验证 WebSocket 连接。
- 验证旧 token 失效。

数据库密码：

- 进入维护窗口。
- 备份数据库。
- 更新数据库密码。
- 更新 `.env.production`。
- 重启 API。
- 验证健康检查。

泄露响应：

- 立即 revoke 或 rotate。
- 检查 audit logs。
- 检查异常 task、approval、connection。
- 检查 CI logs 是否泄露。
- 生成 incident note。

### 验收标准

- 文档可指导 API key 和 Agent token 真实轮换。
- 文档包含建议轮换周期：
  - API key: 90 天或人员变动。
  - Agent token: 90 天或机器变更。
  - DB password: 180 天或泄露。
- 文档明确明文 token 只在创建或轮换时显示一次。

---

## 9. Phase 11.7 - 观测性面板和告警

### 目标

建立 Prometheus + Grafana 观测模板，覆盖 API 健康、请求量、错误率、任务状态、WebSocket 连接、队列和 worker。

### 交付物

- `apps/api/app/metrics.py`
- API `/metrics` endpoint。
- `infra/prometheus/prometheus.yml`
- `infra/prometheus/alerts/agentnet.yml`
- `infra/grafana/provisioning/datasources/prometheus.yml`
- `infra/grafana/provisioning/dashboards/agentnet.yml`
- `infra/grafana/dashboards/agentnet-overview.json`
- `docs/observability.md`
- `reports/phase11_7_report.md`

### 指标要求

HTTP：

- `agentnet_http_requests_total`
- `agentnet_http_request_duration_seconds`
- `agentnet_http_errors_total`

WebSocket：

- `agentnet_ws_connections_active`
- `agentnet_ws_connections_total`
- `agentnet_ws_disconnects_total`
- `agentnet_ws_auth_failures_total`

Task：

- `agentnet_tasks_created_total`
- `agentnet_tasks_completed_total`
- `agentnet_tasks_failed_total`
- `agentnet_tasks_expired_total`
- `agentnet_task_duration_seconds`

Message：

- `agentnet_messages_delivered_total`
- `agentnet_messages_acked_total`
- `agentnet_messages_retried_total`
- `agentnet_messages_expired_total`
- `agentnet_pending_messages`

Approval：

- `agentnet_approvals_pending`
- `agentnet_approvals_accepted_total`
- `agentnet_approvals_rejected_total`
- `agentnet_approvals_expired_total`

Worker：

- `agentnet_retry_worker_cycles_total`
- `agentnet_timeout_worker_cycles_total`
- `agentnet_worker_errors_total`

### Dashboard 要求

Grafana overview dashboard 至少包含：

- API request rate。
- API p95 latency。
- API 4xx/5xx error rate。
- Active WebSocket connections。
- Task status distribution。
- Task completion / failure / expiry trend。
- Pending messages。
- Retry count。
- Approval pending count。
- Worker errors。

### 告警要求

Prometheus alerts 至少包含：

- API 5xx error rate 高。
- API p95 latency 高。
- Active WebSocket connections 突然归零。
- Pending messages 持续增长。
- Task expired rate 高。
- Worker errors 大于 0。
- Redis unavailable。
- Postgres unavailable。
- Approval pending 超时。

### 验证命令

```powershell
docker compose -f infra/docker-compose.prod.yml --env-file infra/.env.production.example config
promtool check config infra/prometheus/prometheus.yml
promtool check rules infra/prometheus/alerts/agentnet.yml
```

如本地没有 `promtool`，报告必须写明未执行原因，CI 或 release-check 必须执行。

### 验收标准

- `/metrics` 能被 Prometheus scrape。
- Grafana 自动加载 datasource 和 dashboard。
- 告警规则通过 `promtool` 校验。
- 文档说明如何查看面板、调整阈值、处理常见告警。

---

## 10. Phase 11.8 - 文档交付和总验收

### 目标

整理所有生产化文档，形成用户、开发者、运维三类入口，并完成 Phase 11 总验收。

### 交付物

- 更新 `README.md`。
- 更新 `DEVELOPER_README.md`。
- 更新 `docs/quickstart.md`。
- 新增或更新：
  - `docs/ci-cd.md`
  - `docs/production-deploy.md`
  - `docs/production-checklist.md`
  - `docs/openapi.md`
  - `docs/api-examples.md`
  - `docs/backup-restore.md`
  - `docs/secrets-rotation.md`
  - `docs/incident-secret-leak.md`
  - `docs/observability.md`
- `reports/phase11_final_report.md`

### 文档要求

每篇文档必须包含：

- 目的。
- 前置条件。
- 操作步骤。
- 验证命令。
- 常见失败原因。
- 安全注意事项。

命令格式：

- 默认提供 PowerShell。
- 运维脚本同时提供 Bash。

禁止：

- 写虚假能力。
- 写未实现功能为已完成。
- 写真实 secret。
- 写私有机器路径。

### 总体验证命令

```powershell
python -m pytest -q
python -m pytest apps/api/tests/test_protocol_contract.py --collect-only -q
python -m pytest apps/api/tests/test_websocket_e2e.py -q
python -m compileall adapters/openclaw/agentnet_openclaw packages/python-sdk/agentnet packages/cli/agentnet_cli apps/api/app
docker compose -f infra/docker-compose.yml -f infra/docker-compose.dev.yml config
docker compose -f infra/docker-compose.prod.yml --env-file infra/.env.production.example config
python scripts/export_openapi.py --check
```

备份、恢复和观测性验证：

```powershell
./scripts/backup/postgres_backup.ps1 --dry-run
./scripts/backup/postgres_restore.ps1 --dry-run
promtool check config infra/prometheus/prometheus.yml
promtool check rules infra/prometheus/alerts/agentnet.yml
```

### 总验收标准

- Phase 11.1-11.8 报告全部存在。
- 所有可执行验证通过。
- CI 全绿。
- 生产 compose config 通过。
- OpenAPI 导出稳定。
- WebSocket E2E 进入 CI。
- 备份恢复文档和 dry-run 通过。
- Secret rotation 文档可操作。
- Prometheus/Grafana 配置可启动和校验。
- README 和 DEVELOPER_README 指向全部新文档。

---

## 11. 推荐执行顺序

严格按以下顺序执行：

1. Phase 11.1 CI/CD。
2. Phase 11.2 生产配置模板。
3. Phase 11.3 OpenAPI 文档。
4. Phase 11.4 WebSocket E2E。
5. Phase 11.5 数据库备份和恢复。
6. Phase 11.6 Secret 管理和密钥轮换。
7. Phase 11.7 观测性面板和告警。
8. Phase 11.8 文档交付和总验收。

原因：

- CI 先行，后续每一步都有质量门禁。
- 生产配置先行，OpenAPI、备份、观测性都需要稳定部署形态。
- WebSocket E2E 在基础 CI 和配置稳定后补，避免测试环境反复变化。
- 备份、Secret、观测性最后补齐运营闭环。
- 文档交付必须最后做，确保描述的是最终真实状态。

---

## 12. Phase 报告模板

每个子阶段报告使用以下结构：

```markdown
# Phase 11.X Report

## Summary

## Files Changed

## Commands Run

## Test Results

## Manual Review Notes

## Security Review

## Known Gaps

## Acceptance Checklist

## Next Phase Readiness
```

`Acceptance Checklist` 必须逐条对应本计划中的验收标准。

---

## 13. 最终输出要求

Phase 11 完成后，项目必须能回答以下问题：

- 如何在 CI 中证明这套系统没有回归？
- 如何在单机 VPS 上部署？
- 如何查 API 文档和示例？
- 如何证明 WebSocket Agent 真实收发任务？
- 如何备份和恢复数据库？
- 如何轮换 API key、Agent token 和数据库密码？
- 如何查看系统健康、任务积压、错误率和告警？
- 出问题时应该看哪份文档、执行哪个命令？

只有以上问题都有真实文件、真实命令和真实验证结果，本轮 Phase 11 才算完成。

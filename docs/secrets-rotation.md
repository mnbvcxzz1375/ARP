# Secret 管理和密钥轮换

本文定义 AgentNet 单机 Docker Compose 部署的 secret 分类、存储位置、轮换周期、轮换步骤和审计要求。

## 目的

降低 API key、Agent token、数据库密码、Redis 密码、Grafana 密码、TLS 私钥和 CI secret 泄露后的影响范围，并保证轮换过程可审计、可验证、可回滚。

## Secret 分类

| 类型 | 示例 | 用途 | 明文显示策略 |
| --- | --- | --- | --- |
| User API key | `ak_...` | REST API 认证 | 创建时显示一次 |
| Agent token | `agt_sk_...` | WebSocket Agent 认证 | 创建或轮换时显示一次 |
| Postgres password | `POSTGRES_PASSWORD` | 数据库认证 | 只存在于 `.env.production` 和运维 secret store |
| Redis password | `REDIS_PASSWORD` | Redis 认证 | 只存在于 `.env.production` |
| Grafana admin password | `GRAFANA_ADMIN_PASSWORD` | Grafana 初始管理员 | 只存在于 `.env.production` |
| TLS private key | `privkey.pem` | HTTPS 终止 | 仅服务器 root/运维用户可读 |
| CI secrets | GitHub Secrets | CI/CD 发布和外部集成 | 不写入日志 |
| 外部服务 token | 未来扩展 | Adapter 或集成调用 | 按对应服务策略管理 |

## 存储策略

- Docker Compose VPS 默认使用 `infra/.env.production`。
- `infra/.env.production` 必须被 `.gitignore` 忽略。
- Linux 权限建议：

```bash
chmod 600 infra/.env.production
chown deploy:deploy infra/.env.production
```

- GitHub Actions 使用 GitHub Secrets，不把 secret 写入 workflow 文件。
- CLI 本地配置可能保存 API key，开发者机器应启用磁盘加密和系统账户保护。
- 本轮不引入云 Secret Manager，后续如迁移云平台再加入。

## 建议轮换周期

| Secret | 周期 | 触发条件 |
| --- | --- | --- |
| User API key | 90 天 | 人员变更、机器丢失、疑似泄露 |
| Agent token | 90 天 | 机器迁移、Agent 镜像泄露、疑似泄露 |
| Postgres password | 180 天 | 运维人员变更、备份泄露、疑似泄露 |
| Redis password | 180 天 | 与 Postgres password 同步运营 |
| Grafana admin password | 180 天 | 管理员变更、疑似泄露 |
| TLS private key | 证书周期 | 私钥泄露、证书更新 |
| CI secrets | 90 天或供应商建议 | runner 日志泄露、权限变化 |

## API key 轮换

当前版本支持通过 REST API 和 CLI 创建、列出、撤销 API key。生产轮换按下列原则执行：

1. 为用户创建新 API key。
2. 更新所有调用方配置。
3. 使用新 key 调用 `/v1/agents` 验证。
4. 撤销旧 key。
5. 检查旧 key 访问返回 401。

验证命令：

```powershell
agentnet key create --name rotated-2026-05
agentnet key list
agentnet key revoke <old_api_key_id>
curl.exe -s "$env:PUBLIC_BASE_URL/v1/agents" -H "Authorization: Bearer ak_NEW"
curl.exe -i "$env:PUBLIC_BASE_URL/v1/agents" -H "Authorization: Bearer ak_OLD"
```

审计点：

- 创建新 key 的操作者。
- key prefix。
- revoke 时间。
- 受影响系统。

## Agent token 轮换

1. 调用 rotate token API：

```powershell
curl.exe -s -X POST "$env:PUBLIC_BASE_URL/v1/agents/$env:AGENT_ID/rotate-token" `
  -H "Authorization: Bearer $env:API_KEY"
```

2. 保存响应中的新 `agt_sk_...`，旧 token 立即视为失效。
3. 更新 Agent 运行环境变量 `AGENTNET_AGENT_TOKEN`。
4. 重启 Agent。
5. 验证 WebSocket 连接成功。
6. 使用旧 token 连接，确认返回 `INVALID_TOKEN`。

审计点：

- Agent ID / Agent Number。
- 轮换发起人。
- 轮换时间。
- Agent 重启时间。
- 旧 token 验证失败结果。

## Postgres password 轮换

1. 进入维护窗口。
2. 执行数据库备份：

```powershell
./scripts/backup/postgres_backup.ps1
```

3. 停止 API：

```powershell
docker compose -f infra/docker-compose.prod.yml --env-file infra/.env.production stop api
```

4. 在 Postgres 中修改密码。
5. 更新 `infra/.env.production` 的 `POSTGRES_PASSWORD` 和 `DATABASE_URL`。
6. 启动 API：

```powershell
docker compose -f infra/docker-compose.prod.yml --env-file infra/.env.production up -d api
```

7. 验证：

```powershell
curl.exe http://localhost/healthz
docker compose -f infra/docker-compose.prod.yml --env-file infra/.env.production exec api alembic current
```

回滚：

- 如 API 无法连接数据库，恢复旧密码和旧 `.env.production`，重启 API。
- 如数据库状态异常，按 `docs/backup-restore.md` 执行恢复。

## Redis password 轮换

Redis 中数据不是长期事实源。轮换可接受短暂丢失 pending queue、presence 和 rate limit 状态：

1. 进入维护窗口。
2. 停止 API 和 Redis。
3. 更新 `REDIS_PASSWORD` 和 `REDIS_URL`。
4. 重建 Redis 容器。
5. 启动 API。
6. 检查 `/healthz` 和 WebSocket 连接。

## 泄露响应

发生 secret 泄露时，按 `docs/incident-secret-leak.md` 执行。最低动作：

- 立即 revoke 或 rotate。
- 检查 audit logs。
- 检查异常 task、approval、connection。
- 检查 CI logs 是否泄露。
- 生成 incident note。

## 常见失败原因

- 新 key 未同步到所有调用方，导致部分服务 401。
- 默认拒绝撤销最后一个 active API key；确实需要锁定账号时必须显式传入 `allow_last_key=true` 或 CLI `--allow-last-key`。
- Agent token 轮换后未重启 Agent。
- `.env.production` 更新了 `POSTGRES_PASSWORD` 但忘记更新 `DATABASE_URL`。
- 轮换过程中没有维护窗口，导致任务投递中断。

## 安全注意事项

- 不要在 Slack、issue、README、报告或截图里贴完整 token。
- 明文 token 只应在创建或轮换时显示一次。
- 运维命令历史可能保存 secret，生产机器应控制 shell history。

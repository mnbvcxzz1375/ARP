# 数据库备份和恢复

本文说明 AgentNet 单机 Docker Compose 部署下的 PostgreSQL 备份、恢复、校验和演练流程。

## 目的

PostgreSQL 是 AgentNet 的长期事实源，保存用户、API key hash、Agent、任务、消息、审批和审计日志。Redis 只保存 pending queue、presence 和 rate limit 等短期状态，本轮不做 Redis 长期备份。

## 前置条件

- 已安装 `pg_dump` 和 `pg_restore`，版本建议与生产 Postgres 主版本一致。
- 已设置 `DATABASE_URL`，指向目标数据库。
- 生产环境执行前已进入维护窗口，并确认最近一次备份可用。

## 备份

PowerShell:

```powershell
$env:DATABASE_URL = "postgresql://agentnet:CHANGE_ME@localhost:5432/agentnet"
./scripts/backup/postgres_backup.ps1
```

Bash:

```bash
export DATABASE_URL="postgresql://agentnet:CHANGE_ME@localhost:5432/agentnet"
./scripts/backup/postgres_backup.sh
```

默认输出：

```text
backups/postgres/agentnet_YYYYMMDD_HHMMSS.dump
backups/postgres/agentnet_YYYYMMDD_HHMMSS.dump.sha256
```

Dry-run:

```powershell
./scripts/backup/postgres_backup.ps1 --dry-run
```

## 每日计划任务示例

Windows Task Scheduler 可运行：

```powershell
powershell.exe -ExecutionPolicy Bypass -File E:\AgentNet\scripts\backup\postgres_backup.ps1
```

Linux cron 示例：

```cron
15 2 * * * cd /opt/agentnet && DATABASE_URL='postgresql://agentnet:***@postgres:5432/agentnet' ./scripts/backup/postgres_backup.sh >> /var/log/agentnet-backup.log 2>&1
```

## 恢复

恢复会先验证 checksum，再创建恢复前快照，然后执行 `pg_restore --clean --if-exists`。

PowerShell:

```powershell
$env:DATABASE_URL = "postgresql://agentnet:CHANGE_ME@localhost:5432/agentnet"
./scripts/backup/postgres_restore.ps1 --file backups/postgres/agentnet_YYYYMMDD_HHMMSS.dump --yes
```

Bash:

```bash
export DATABASE_URL="postgresql://agentnet:CHANGE_ME@localhost:5432/agentnet"
./scripts/backup/postgres_restore.sh --file backups/postgres/agentnet_YYYYMMDD_HHMMSS.dump --yes
```

Dry-run:

```powershell
./scripts/backup/postgres_restore.ps1 --dry-run
```

## 生产恢复操作顺序

1. 宣布维护窗口，暂停外部流量。
2. 停止 API 容器：

```powershell
docker compose -f infra/docker-compose.prod.yml --env-file infra/.env.production stop api
```

3. 执行 restore 脚本。
4. 检查迁移版本：

```powershell
docker compose -f infra/docker-compose.prod.yml --env-file infra/.env.production exec api alembic current
```

5. 启动 API：

```powershell
docker compose -f infra/docker-compose.prod.yml --env-file infra/.env.production up -d api
```

6. 检查健康：

```powershell
curl.exe http://localhost/healthz
```

## 每月恢复演练

1. 复制最近一次 `.dump` 和 `.sha256` 到隔离测试环境。
2. 启动空 Postgres。
3. 设置测试环境 `DATABASE_URL`。
4. 执行 restore dry-run。
5. 执行真实 restore。
6. 运行 `alembic current` 和 `/healthz`。
7. 抽查用户、Agent、task、message、approval、audit log 表。
8. 记录演练结果、耗时、失败原因和改进项。

## 常见失败原因

- `pg_dump was not found on PATH`: 没有安装 PostgreSQL client tools。
- checksum mismatch: 备份文件损坏或 `.sha256` 不匹配，禁止恢复。
- authentication failed: `DATABASE_URL` 用户、密码或主机错误。
- restore 被拒绝: 真实恢复必须显式传入 `--yes`。

## 安全注意事项

- `.dump` 可能包含敏感业务数据和 hash，按生产数据等级保护。
- 不要把 `DATABASE_URL` 明文写入仓库。
- 备份目录应限制为运维用户可读写。
- 恢复前快照不能替代正式备份，但可用于误恢复后的紧急回滚。

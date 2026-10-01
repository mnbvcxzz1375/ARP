# 快速开始

本文给出 AgentNet 本地开发最快启动路径。

## 前置条件

- Python 3.11+
- Docker Desktop
- PowerShell

## 1. 安装本地包

在仓库根目录执行：

```powershell
python -m pip install -e "apps/api[test]"
python -m pip install -e packages/python-sdk
python -m pip install -e packages/cli
python -m pip install -e adapters/base
python -m pip install -e adapters/openclaw
```

## 2. 启动 Postgres 和 Redis

```powershell
docker compose -f infra/docker-compose.yml up -d postgres redis
```

## 3. 初始化数据库

```powershell
cd apps/api
alembic upgrade head
cd ../..
```

## 4. 启动 API

```powershell
cd apps/api
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

另开终端检查：

```powershell
curl.exe http://localhost:8000/healthz
```

期望：

```json
{"status":"ok"}
```

## 5. 注册用户

```powershell
$BASE_URL = "http://localhost:8000"

curl.exe -s -X POST "$BASE_URL/v1/auth/register" `
  -H "Content-Type: application/json" `
  -d "{\"username\":\"alice\",\"key_name\":\"local-dev\"}"
```

保存返回的 `api_key`：

```powershell
$API_KEY = "ak_REPLACE_ME"
```

## 6. 创建 Agent

```powershell
curl.exe -s -X POST "$BASE_URL/v1/agents" `
  -H "Authorization: Bearer $API_KEY" `
  -H "Content-Type: application/json" `
  -d "{\"name\":\"echo-agent\",\"runtime\":\"python-sdk\",\"capabilities\":[\"echo\"],\"inbound_policy\":\"public\"}"
```

保存返回的：

- `agent_number`
- `agent_token`

## 7. 查看 API 文档

浏览器打开：

```text
http://localhost:8000/docs
```

导出并校验 OpenAPI：

```powershell
python scripts/export_openapi.py
python scripts/export_openapi.py --yaml
python scripts/export_openapi.py --check
```

更多示例见 `docs/api-examples.md`。

## 8. 跑测试

```powershell
python -m pytest -q
```

重点验证：

```powershell
python -m pytest apps/api/tests/test_websocket_e2e.py -q
python -m pytest packages/python-sdk/tests/test_websocket_integration.py -q
```

## 9. 生产化文档入口

- CI/CD: `docs/ci-cd.md`
- 生产部署: `docs/production-deploy.md`
- 生产检查表: `docs/production-checklist.md`
- OpenAPI: `docs/openapi.md`
- API 示例: `docs/api-examples.md`
- 备份恢复: `docs/backup-restore.md`
- Secret 轮换: `docs/secrets-rotation.md`
- 泄露响应: `docs/incident-secret-leak.md`
- 观测性: `docs/observability.md`

## 常见失败原因

- Docker 未启动，Postgres/Redis 无法连接。
- 没有执行 `alembic upgrade head`，数据库表不存在。
- REST 使用了 `agt_sk_...`，应使用 `ak_...`。
- WebSocket 使用了 `ak_...`，应使用 `agt_sk_...`。
- Redis 不可用时限流会 fail-closed，API 可能返回 503。

## 安全注意事项

- 不要提交 `.env.production`。
- 不要把 `ak_...` 或 `agt_sk_...` 写入 issue、日志、报告或截图。
- `/metrics` 只应在内部网络或 SSH tunnel 下访问。

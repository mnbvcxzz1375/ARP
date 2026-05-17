# 观测性和告警

本文说明 AgentNet 的 Prometheus `/metrics`、Prometheus 配置、Grafana dashboard 和告警规则。

## 目的

让运维者能观察 API 请求、错误率、延迟、WebSocket 连接、任务状态、消息积压、审批积压和 worker 错误。

## 前置条件

- 已完成生产 compose 配置。
- 使用 observability profile 启动 Prometheus 和 Grafana。

```powershell
docker compose -f infra/docker-compose.prod.yml --env-file infra/.env.production --profile observability up -d
```

## 指标入口

API 暴露内部 `/metrics`：

```powershell
curl.exe http://localhost:8000/metrics
```

生产 nginx 默认阻止公网访问 `/metrics`。Prometheus 在内部网络抓取 `api:8000/metrics`。

## Prometheus

配置文件：

- `infra/prometheus/prometheus.yml`
- `infra/prometheus/alerts/agentnet.yml`

Prometheus scrape jobs:

- `agentnet-api`: API `/metrics`。
- `postgres`: Postgres exporter。
- `redis`: Redis exporter。
- `prometheus`: Prometheus 自身。

校验：

```powershell
promtool check config infra/prometheus/prometheus.yml
promtool check rules infra/prometheus/alerts/agentnet.yml
```

如果本机没有 `promtool`，在 Prometheus 容器中执行等价检查。

## Grafana

Grafana 默认绑定本机：

```text
http://127.0.0.1:3000
```

远程 VPS 推荐 SSH tunnel：

```powershell
ssh -L 3000:127.0.0.1:3000 deploy@example.com
```

自动加载：

- datasource: `infra/grafana/provisioning/datasources/prometheus.yml`
- dashboard provider: `infra/grafana/provisioning/dashboards/agentnet.yml`
- dashboard: `infra/grafana/dashboards/agentnet-overview.json`

## Dashboard 面板

Overview dashboard 包含：

- API request rate。
- API p95 latency。
- API 5xx error rate。
- Active WebSocket connections。
- Task status counters。
- Pending messages。
- Pending approvals。
- Retry count and worker errors。

## 告警

当前 Prometheus rules 包含：

- API 5xx error rate 高。
- API p95 latency 高。
- Active WebSocket connections 长时间为 0。
- Pending messages 持续增长。
- Task expired rate 高。
- Worker errors 大于 0。
- Redis exporter unavailable。
- Postgres exporter unavailable。
- Approval pending 超时。

## 常见处理

- API 5xx: 查看 API 日志、最近部署、数据库连接。
- p95 latency 高: 检查 Postgres、Redis、任务 payload 大小和慢查询。
- WebSocket 为 0: 确认 Agent 是否应在线，检查 token 轮换和网络。
- Pending messages 增长: 检查 receiver Agent 在线状态和 ack 是否正常。
- Approval pending: 联系审批人或检查 CLI approval 流程。
- Worker errors: 查看 retry worker 和 timeout worker 日志。
- Postgres exporter down: 检查 `postgres_exporter` 容器、`POSTGRES_PASSWORD` 和数据库健康。
- Redis exporter down: 检查 `redis_exporter` 容器、`REDIS_PASSWORD` 和 Redis 健康。

## 安全注意事项

- `/metrics` 不应公开到公网。
- Grafana 初始密码必须替换，且只通过本机端口或 SSH tunnel 访问。
- Dashboard 不应展示完整 token、payload secret 或用户敏感内容。

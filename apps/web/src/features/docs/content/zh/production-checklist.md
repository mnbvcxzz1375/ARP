# 生产检查表

在 VPS 上运行 AgentNet 之前，请逐项核对本检查表。

更严格的生产收尾门禁、Web UI 决策与最终验收标准，见：

- [生产收尾计划](production-closeout.md)

## 环境

- [ ] 已安装 Docker Engine。
- [ ] Docker Compose 可用。
- [ ] 域名 DNS 已指向服务器。
- [ ] 防火墙仅按需放行 SSH、HTTP 和 HTTPS。
- [ ] `infra/.env.production` 已存在且未提交到版本库。
- [ ] 所有 `CHANGE_ME` 值都已替换。

## Compose 校验

```powershell
docker compose -f infra/docker-compose.prod.yml --env-file infra/.env.production config
```

- [ ] Compose 配置校验通过。
- [ ] API 没有对外端口映射。
- [ ] Postgres 没有对外端口映射。
- [ ] Redis 没有对外端口映射。
- [ ] nginx 是唯一的公共 HTTP 入口。

## 数据库

```powershell
docker compose -f infra/docker-compose.prod.yml --env-file infra/.env.production exec api alembic upgrade head
docker compose -f infra/docker-compose.prod.yml --env-file infra/.env.production exec api alembic current
```

- [ ] 迁移执行到 head。
- [ ] `alembic current` 显示预期版本。

## 健康

```powershell
curl http://localhost/healthz
```

- [ ] 健康接口返回 `{"status":"ok"}`。
- [ ] API 日志不含密钥明文。
- [ ] nginx 日志显示代理正常。

## Token 与密钥

- [ ] API key 不存于代码或 shell 历史记录中。
- [ ] Agent token 不存于代码或 shell 历史记录中。
- [ ] 数据库密码为本部署专用且唯一。
- [ ] Redis 密码为本部署专用且唯一。
- [ ] Grafana 管理员密码为本部署专用且唯一。

## 回滚准备

- [ ] 已记录当前代码版本。
- [ ] 已记录当前迁移版本。
- [ ] 已明确备份方案。
- [ ] 已明确恢复方案。

## 可观测性

- [ ] 可观测性 profile 在 Phase 11.7 完成前保持关闭，或仅用于内部测试。
- [ ] Grafana 未在无 TLS、无认证的情况下暴露在公网。
- [ ] `/metrics` 不对公网开放。

## 控制台安全

- [ ] 控制台会话 cookie 为 HttpOnly、SameSite=Lax、Secure=true
- [ ] 控制台 CSRF 防护已启用
- [ ] 控制台管理员页面要求 admin 或 super_admin 角色
- [ ] 控制台高危管理操作要求增强验证
- [ ] 控制台系统健康页不暴露 DATABASE_URL、REDIS_URL、token 或密码
- [ ] 普通控制台用户无法访问管理员接口（403）
- [ ] SecretMaskedText 组件在 UI 中遮蔽密钥
- [ ] API key 仅返回一次（创建时）
- [ ] Agent token 仅返回一次（创建/轮换时）

## 控制台性能

- [ ] 概览页按合理间隔轮询（用户 15s，管理员 30s，系统健康 10s）
- [ ] 所有列表均分页（默认 50，上限 200）
- [ ] 已配置 TanStack Query 重试（默认重试 1 次）

## 路由运行时收尾

- [ ] 出口网关 由适配器强制执行，而不仅仅是作为一个服务可用。
- [ ] 网络级外联绕过已被阻断，或在私有试点范围内被明确记录。
- [ ] 专属通道（Dedicated Channel）存在 CRUD/API 或经批准的运维流程。
- [ ] 路由决策与投递时间线对运维人员可见。
- [ ] SLA 违规、熔断器状态和故障转移事件对运维人员可见。
- [ ] Redis/Postgres/API/worker/egress/relay 故障演练均有记录。
- [ ] 已在 `reports/` 下生成最终生产验收报告。

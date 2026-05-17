# Secret 泄露响应流程

本文说明 AgentNet 发现 API key、Agent token、数据库密码、Redis 密码、Grafana 密码、TLS 私钥或 CI secret 泄露后的处置流程。

## 目的

在最短时间内切断被泄露 secret 的访问能力，确认影响范围，恢复服务，并留下可追溯记录。

## 事件分级

| 级别 | 示例 | 响应 |
| --- | --- | --- |
| P0 | 数据库密码、TLS 私钥、CI deploy token 泄露 | 立即维护窗口，轮换，审计访问 |
| P1 | User API key 或 Agent token 泄露 | 立即 revoke/rotate，检查异常操作 |
| P2 | Grafana admin password 泄露 | 轮换密码，检查 dashboard 和 datasource |

## 立即动作

1. 记录发现时间、发现人和泄露位置。
2. 不要在更多渠道复制完整 secret。
3. 截断证据，只保留 prefix、hash 或脱敏截图。
4. 确认 secret 类型。
5. 按类型执行 revoke 或 rotate。

## API key 泄露

1. 创建替代 key。
2. 更新调用方。
3. revoke 旧 key。
4. 查询 audit logs：
   - 异常 task 创建。
   - 异常 agent 创建或删除。
   - 异常 connection 或 approval 操作。
5. 用旧 key 验证 401。

## Agent token 泄露

1. 调用 Agent token rotate API。
2. 更新 Agent 环境变量。
3. 重启 Agent。
4. 检查旧 token WebSocket 连接是否返回 `INVALID_TOKEN`。
5. 检查该 Agent 近期 task、message、approval 和 connection。

## 数据库密码泄露

1. 立即进入维护窗口。
2. 执行备份。
3. 轮换数据库密码。
4. 更新 `.env.production`。
5. 重启 API。
6. 检查数据库连接来源和异常查询。
7. 如怀疑数据被篡改，按备份恢复流程进入取证和恢复。

## CI secret 泄露

1. 在 GitHub Secrets 中删除或替换 secret。
2. 取消正在运行的可疑 workflow。
3. 检查 Actions logs 是否包含明文。
4. 轮换下游系统 token。
5. 检查最近发布产物是否可信。

## Incident Note 模板

```markdown
# Secret Leak Incident

## Summary

## Timeline

## Secret Type

## Exposure Source

## Immediate Containment

## Rotation / Revocation Steps

## Audit Findings

## User Impact

## Follow-up Actions
```

## 验证命令

```powershell
curl.exe -i "$env:PUBLIC_BASE_URL/v1/agents" -H "Authorization: Bearer ak_OLD"
curl.exe -s "$env:PUBLIC_BASE_URL/healthz"
docker compose -f infra/docker-compose.prod.yml --env-file infra/.env.production logs --tail 200 api
```

## 安全注意事项

- 事件记录不得包含完整 secret。
- 对外沟通只描述影响范围和处置状态。
- 如果泄露来自 git commit，轮换 secret 后仍需清理历史或限制仓库访问，因为删除文件不足以消除泄露。

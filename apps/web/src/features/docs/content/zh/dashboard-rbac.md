# AgentNet 控制台 RBAC 指南

## 角色

| 角色 | 权限范围 |
|------|--------|
| `user` | 自身资源：智能体、任务、审批、连接、API key |
| `admin` | user + 全局读权限 + 取消待处理任务 |
| `super_admin` | admin + 禁用用户/智能体、吊销密钥、取消运行中任务、导出审计日志、修改安全策略 |

## 权限常量

所有权限校验都经过 `has_permission()`，代码中绝不直接比较角色字符串。

**自身资源权限**（所有角色）：
- `agent:read:own`、`agent:create`、`agent:edit:own`、`agent:delete:own`、`agent:rotate-token:own`
- `task:read:own`、`task:create`、`task:read:detail:own`
- `approval:handle:own`
- `connection:manage:own`、`firewall:manage:own`
- `apikey:manage:own`

**全局读权限**（admin 起）：
- `overview:read:global`、`user:read:global`、`agent:read:global`
- `task:read:global`、`task:read:detail:global`
- `audit:read`

**超级管理员权限**：
- `user:disable`、`agent:disable`、`apikey:revoke:global`
- `task:cancel:running`、`audit:export`
- `security:modify`、`system:read`

## 高危操作

要求 `super_admin` 且通过增强验证：
- 禁用/启用用户
- 禁用/启用智能体
- 强制吊销 API key
- 取消运行中任务
- 强制过期任务
- 导出审计日志
- 修改系统安全策略

## 增强验证

高危操作要求在最近 10 分钟内重新输入一次有效的 API key。

```bash
# 执行高危操作前先完成增强验证
curl -X POST /v1/dashboard/auth/step-up \
  -H "Cookie: agentnet_session=..." \
  -d '{"api_key": "ak_..."}'
```

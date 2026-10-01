# 安全模型

本文描述 AgentNet 当前已实现的安全机制。核心原则是：显式失败、
凭证 hash、后端权限为准、操作可审计。

## 已实现的关键安全点

凭证与存储：

- API key 只保存 hash，明文只在创建时返回一次
- 智能体 token 只保存 hash，明文只在创建或轮换时返回一次
- Dashboard session 只保存 hash
- CSRF token 只保存 hash
- 数据库与日志中不出现明文 secret

会话与传输：

- Dashboard session cookie 使用 HttpOnly
- 生产 cookie 配置支持 `Secure` 和 `SameSite=Lax`
- 智能体 token 通过 `Authorization` header 发送，不放在 URL 参数里

权限与审计：

- RBAC 分离 `user`、`admin`、`super_admin`
- 高风险操作要求 增强验证、CSRF、二次确认，并写审计日志
- 关键读操作和变更操作写审计日志
- System health 响应会脱敏，不暴露内部细节
- 控制台 UI 统一脱敏 token-like 文本

可靠性：

- 外部输入先用 Pydantic 校验，再进入业务逻辑
- 业务失败使用 `DomainException` 和标准错误响应
- 限流器 fail-closed，依赖失败不会静默放行
- Redis 或 PostgreSQL 依赖失败时不能静默成功

## E2EE 状态

E2EE 字段在协议层预留，但当前未实现。信封接受 `security.mode = e2ee`，
业务校验会返回 `E2EE_NOT_IMPLEMENTED`。相关预留代码见
`packages/python-sdk/agentnet/crypto.py`。

## 生产路径禁止事项

贡献者必须遵守：

- 依赖缺失时自动切换 mock、fake、memory-only 或 silent mode
- 未实现功能返回成功占位
- Redis、PostgreSQL、限流器、session store、CSRF、适配器 runner
  失败后静默放行
- 日志、截图、报告、前端 bundle、审计中出现 secret 明文
- 浏览器保存 API key
- System 页面展示连接串、完整环境变量或 secret

允许的例外：

- 测试路径中的 test-only fake
- 清理资源时吞掉二次清理异常
- 已完成 ack 或 revoke 的幂等 no-op

## 相关文档

- [docs/dashboard-security.md](dashboard-security.md)：控制台安全模型
- [docs/secrets-rotation.md](secrets-rotation.md)：密钥轮换
- [docs/openclaw-adapter.md](openclaw-adapter.md)：适配器安全机制
- [docs/production-checklist.md](production-checklist.md)：生产检查表

# AgentNet 控制台安全指南

## 认证

- 登录：`用户名 + API key` → HttpOnly 会话 cookie
- 会话 cookie：`SameSite=Lax`、`Secure=true`（生产环境）、`HttpOnly=true`
- CSRF cookie：`SameSite=Lax`、`Secure=true`（生产环境）、`HttpOnly=false`（JS 需要读取）
- 会话 token 仅以 SHA-256 hash 存储
- CSRF token 仅以 SHA-256 hash 存储

## CSRF 防护

所有发往 `/v1/dashboard/*` 的 POST/PUT/PATCH/DELETE 请求都必须携带
`X-CSRF-Token` 头。前端通过 Axios 拦截器读取 CSRF cookie 并设置该头。

## 密钥处理

| 密钥 | 存储形式 | 返回时机 |
|------|----------|----------|
| API key | SHA-256 hash | 仅创建时返回一次 |
| Agent token | SHA-256 hash | 仅创建/轮换时返回一次 |
| 会话 token | SHA-256 hash | 仅通过 Set-Cookie |
| CSRF token | SHA-256 hash | 仅通过 Set-Cookie |

## 数据隔离

- 用户只能看到自己的智能体、任务、审批、连接和 API key。
- 管理员可以读取全局数据，但缺少相应权限时不能修改。
- API key 归属性在服务层强制校验。

## 安全响应头（生产 nginx）

| 头 | 值 |
|--------|-------|
| X-Frame-Options | DENY |
| X-Content-Type-Options | nosniff |
| Referrer-Policy | strict-origin-when-cross-origin |
| Permissions-Policy | camera=(), microphone=(), geolocation=() |

## 生产检查清单

- [ ] 替换 `.env.production` 中的所有默认密码
- [ ] 启用 TLS 并使用有效证书
- [ ] 设置 `SESSION_SECURE_COOKIE=true`
- [ ] 验证 CSRF 防护生效
- [ ] 测试管理员隔离（普通用户无法访问管理员接口）
- [ ] 验证系统健康页不泄露任何密钥

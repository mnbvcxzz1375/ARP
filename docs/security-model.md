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

非交互式 E2EE 已落地（M2）。算法：发送方一次性 X25519 ephemeral +
接收方长期 KEM 公钥（`agents.public_keys` 组合列 `{kem, sig, v}`）派生
共享密钥，HKDF-SHA256 + AES-256-GCM 加密，Ed25519 签名绑 from 身份。
原语见 `packages/python-sdk/agentnet/crypto.py`。

标记机制与平台约束：

- 标记块（`security` / `encrypted_payload` / `aad`）复用信封已有保留字段，
  不新建 schema 文件；其唯一事实来源是**发送方信封**——`create_task`
  时并入 `Message.content` 逐字存储，投递时由 routing_service **原样复制**
  到 `ws_payload.security`，平台从不构造、改写或推断（不会升降级 mode、
  不会重生成 nonce）。
- 先校验后落库：`app/protocol/validators.py` 在任务创建时校验信封结构；
  缺 `encrypted_payload` 的纯 e2ee 标记仍是保留形态（501
  `E2EE_NOT_IMPLEMENTED`），缺 nonce / 密文非 base64 / aad 非对象一律 400
  且不留任何持久化残留。
- 三处密文存储一致：`Message.content`、`task.result`（接收方回写密文信封，
  `handlers._handle_task_result` 原样存储不做内容级解析）、
  `ws:session_pending` 队列存投递 JSON 原字符串；重连重投
  `deliver_pending_on_connect` 重放同一字符串，`message_id` 是明文路由
  字段，ack 幂等 Lua 与 SDK 去重在密文模式行为不变。
- 协商 fail closed：`connection_service` 从接收方 `public_keys` 推导
  支持模式，无密钥的老 agent 请求 e2ee 返回 400
  `SECURITY_MODE_NOT_SUPPORTED` 且无 pending Connection 残留、不撞
  `uq_pending_connection` 唯一索引；含 `relay_visible` 的请求按优先级
  回退。同 owner / PUBLIC 链路无平台协商记录，模式判定完全由信封
  security 块承载。
- 读取侧降级：非 `relay_visible` 且结构合法的密文返回加密标志 + 原样
  密文；非法 enc（缺 nonce / 密文非 base64）返回 `encrypted_parse_error`
  标志而非 500；每条消息按自身 security 块独立判定，明文历史与密文新
  消息交错可读（明文永久明文、密文永久密文）。
- 伪装防护误判率为零：判定只看顶层标记块，payload 内同名字段
  （`payload.security` / `payload.encrypted_payload` 等）永远不会把
  明文判成密文。
- 解密失败 fail closed：SDK 解不开密文时回发 `DECRYPT_FAILED` 的
  `task.failed`，任务按失败状态机终结，不会对不可验证字节调用 handler。
  签名验证使用 aad 中携带的发送方签名公钥（TOFU 语义，密钥轮换/吊销
  与身份绑定验证属于后续里程碑）。

未实现（后续里程碑）：Double Ratchet、密钥轮换/吊销、TOFU 身份验证、
TS SDK、密文场景内容级风控、public_keys 发布/管理 API（当前测试与
演练以直接写列方式发布密钥）。

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

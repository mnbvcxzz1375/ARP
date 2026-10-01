# Agent Relay 协议 v0.1

ARP v0.1 为 REST 创建的消息、WebSocket 流量与 SDK 内部实现使用共享的
Envelope（信封）结构。

必填基线字段包括：

- `version`：当前为 `arp-0.1`
- `message_id`
- `type`
- `timestamp`
- `delivery`
- `security`
- `limits`
- `content`

安全模式包括：

- `relay_visible`
- `relay_encrypted`
- `e2ee`

E2EE 字段在 Phase 0 预留。模型接受 `security.mode = e2ee`，
但业务校验会返回 `E2EE_NOT_IMPLEMENTED`。

规范 JSON Schema 文件位于 `packages/protocol/schemas`。

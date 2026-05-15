# Agent Relay Protocol v0.1

ARP v0.1 uses a shared Envelope for REST-created messages, WebSocket traffic,
and SDK internals.

Required baseline fields include:

- `version`: currently `arp-0.1`
- `message_id`
- `type`
- `timestamp`
- `delivery`
- `security`
- `limits`
- `content`

Security modes are:

- `relay_visible`
- `relay_encrypted`
- `e2ee`

E2EE fields are reserved in Phase 0. The model accepts `security.mode = e2ee`,
but business validation returns `E2EE_NOT_IMPLEMENTED`.

Canonical JSON Schema files live in `packages/protocol/schemas`.


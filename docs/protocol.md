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

The envelope's reserved E2EE fields now carry non-interactive sealed task
requests and results. The sender supplies the `security`, `encrypted_payload`
and `aad` fields; the relay validates and forwards the encrypted envelope
without reconstructing its security marker. A bare `e2ee` marker without an
encrypted payload still returns `E2EE_NOT_IMPLEMENTED`; malformed ciphertext
envelopes fail validation. Key management and identity-binding limitations
are documented in the [security model](security-model.md#e2ee-状态).

Canonical JSON Schema files live in `packages/protocol/schemas`.


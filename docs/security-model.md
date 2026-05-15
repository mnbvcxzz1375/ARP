# Security Model

The MVP security model is relay-centered:

- Secrets must not be logged.
- Tokens and API keys will be stored as hashes only.
- External inputs are validated with Pydantic before service logic.
- Business failures use `DomainException` and a standard error response.
- E2EE is reserved at the protocol level but not implemented in Phase 0.

Later phases add ownership checks, inbound policies, connection approval,
high-risk local action approval, rate limits, message size limits, and audit
logs.


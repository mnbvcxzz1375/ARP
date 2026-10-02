"""Agent API schemas: published E2EE public keys."""

from pydantic import BaseModel, Field


class PublicKeys(BaseModel):
    """An agent's published composite public keys (E2EE trust root).

    - ``kem``: base64-encoded X25519 public key (32 raw bytes) — the
      recipient key for non-interactive E2EE key agreement.
    - ``sig``: base64-encoded Ed25519 public key (32 raw bytes) — the
      sender identity key used to verify sealed-message signatures.
    - ``v``: key-bundle version. Currently 1.
    """

    kem: str = Field(min_length=1, description="Base64 X25519 KEM public key.")
    sig: str = Field(min_length=1, description="Base64 Ed25519 signing public key.")
    v: int = Field(default=1, ge=1, le=1, description="Key bundle version.")

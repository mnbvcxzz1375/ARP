"""E2EE trust-root primitives for AgentNet (M1 key model).

  - X25519 KEM key agreement — the sender derives a one-shot shared
    secret from an ephemeral X25519 keypair and the recipient's
    long-lived KEM public key (published in the agent's
    ``public_keys`` column as ``{"kem": <base64>, "sig": <base64>, "v": 1}``).
  - Ed25519 signatures binding the sender's ``from`` identity to the
    ciphertext (signature is carried inside the ``aad`` object).
  - AES-256-GCM AEAD for the payload itself.
  - HKDF-SHA256 for key derivation.

The wire marking reuses the envelope's existing reserved fields
(``security`` / ``encrypted_payload`` / ``aad``); see
``SealedMessage.to_envelope_fields``.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
from dataclasses import dataclass
from typing import Any

from cryptography.exceptions import InvalidSignature, InvalidTag
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ed25519, x25519
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

# --- algorithm identifiers -------------------------------------------------

PUBLIC_KEYS_VERSION = 1
KEM_ALGORITHM = "X25519"
SIGNATURE_ALGORITHM = "Ed25519"
AEAD_ALGORITHM = "AES-256-GCM"
KDF_ALGORITHM = "HKDF-SHA256"

#: Algorithm string placed in ``security.encryption`` of the envelope.
ENCRYPTION_ALGORITHM = f"{KEM_ALGORITHM}+{KDF_ALGORITHM}+{AEAD_ALGORITHM}"

KEY_SIZE = 32  # X25519 / Ed25519 / AES-256 key material size in bytes
NONCE_SIZE = 12  # AES-256-GCM standard nonce size
SESSION_KEY_SIZE = 32

SIGNING_CONTEXT = b"agentnet-e2ee-v1"

# --- base64 helpers --------------------------------------------------------


def b64encode(data: bytes) -> str:
    """Standard-alphabet base64 encoding (used for all wire fields)."""
    return base64.standard_b64encode(data).decode("ascii")


def b64decode(data: str) -> bytes:
    """Decode a standard-alphabet base64 string."""
    return base64.standard_b64decode(data.encode("ascii"))


# --- key generation --------------------------------------------------------


def generate_kem_keypair() -> tuple[bytes, bytes]:
    """Generate an X25519 KEM keypair.

    Returns ``(private_key_bytes, public_key_bytes)`` — raw 32-byte
    encodings. The public half is what an agent publishes in
    ``public_keys.kem``; the private half never leaves the owner.
    """
    private = x25519.X25519PrivateKey.generate()
    public = private.public_key()
    private_bytes = private.private_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PrivateFormat.Raw,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public_bytes = public.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    return private_bytes, public_bytes


def generate_signing_keypair() -> tuple[bytes, bytes]:
    """Generate an Ed25519 signing keypair.

    Returns ``(private_key_bytes, public_key_bytes)`` — raw encodings.
    The public half is published in ``public_keys.sig``.
    """
    private = ed25519.Ed25519PrivateKey.generate()
    public = private.public_key()
    private_bytes = private.private_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PrivateFormat.Raw,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public_bytes = public.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    return private_bytes, public_bytes


# --- signatures ------------------------------------------------------------


def sign(private_key_bytes: bytes, message: bytes) -> bytes:
    """Sign *message* with an Ed25519 private key."""
    private = ed25519.Ed25519PrivateKey.from_private_bytes(private_key_bytes)
    return private.sign(message)


def verify_signature(
    public_key_bytes: bytes, message: bytes, signature: bytes
) -> bool:
    """Verify an Ed25519 signature. Returns ``False`` on any failure
    (bad key, bad signature) instead of raising."""
    try:
        public = ed25519.Ed25519PublicKey.from_public_bytes(public_key_bytes)
        public.verify(signature, message)
        return True
    except (InvalidSignature, ValueError):
        return False


# --- fingerprints ----------------------------------------------------------


def key_fingerprint(public_key_bytes: bytes) -> str:
    """SHA-256 fingerprint (hex) of a raw public key.

    Used as ``security.key_id`` to identify which recipient KEM key a
    ciphertext was sealed to, and as the peer key state recorded by
    ``SessionStore``.
    """
    return hashlib.sha256(public_key_bytes).hexdigest()


# --- key derivation --------------------------------------------------------


def derive_session_key(
    my_private_key_bytes: bytes,
    their_public_key_bytes: bytes,
    *,
    salt: bytes | None = None,
    info: bytes | None = None,
    length: int = SESSION_KEY_SIZE,
) -> bytes:
    """X25519 ECDH + HKDF-SHA256 derivation of a symmetric session key."""
    private = x25519.X25519PrivateKey.from_private_bytes(my_private_key_bytes)
    public = x25519.X25519PublicKey.from_public_bytes(their_public_key_bytes)
    shared = private.exchange(public)
    kdf = HKDF(
        algorithm=hashes.SHA256(),
        length=length,
        salt=salt,
        info=info if info is not None else ENCRYPTION_ALGORITHM.encode("ascii"),
    )
    return kdf.derive(shared)


# --- AEAD ------------------------------------------------------------------


def aes_gcm_encrypt(
    key: bytes,
    nonce: bytes,
    plaintext: bytes,
    aad: bytes,
) -> bytes:
    """AES-256-GCM encrypt; *aad* is authenticated but not encrypted."""
    if len(key) != KEY_SIZE:
        raise ValueError(f"AES-256-GCM key must be {KEY_SIZE} bytes")
    if len(nonce) != NONCE_SIZE:
        raise ValueError(f"AES-256-GCM nonce must be {NONCE_SIZE} bytes")
    return AESGCM(key).encrypt(nonce, plaintext, aad)


def aes_gcm_decrypt(
    key: bytes,
    nonce: bytes,
    ciphertext: bytes,
    aad: bytes,
) -> bytes | None:
    """AES-256-GCM decrypt; returns ``None`` on tag mismatch (never raises)."""
    try:
        return AESGCM(key).decrypt(nonce, ciphertext, aad)
    except (InvalidTag, ValueError):
        return None


# --- combined key bundle ---------------------------------------------------


@dataclass(frozen=True)
class AgentPublicKeys:
    """An agent's published key bundle: X25519 KEM + Ed25519 signing."""

    kem: bytes
    sig: bytes
    version: int = PUBLIC_KEYS_VERSION

    def to_json_dict(self) -> dict[str, Any]:
        """Serialize to the ``public_keys`` column shape."""
        return {
            "kem": b64encode(self.kem),
            "sig": b64encode(self.sig),
            "v": self.version,
        }

    @classmethod
    def from_json_dict(cls, data: dict[str, Any]) -> "AgentPublicKeys":
        """Parse a ``public_keys`` column value. Raises ``ValueError`` on
        malformed input (wrong base64, wrong key size, unknown version)."""
        if not isinstance(data, dict):
            raise ValueError("public_keys must be an object")
        try:
            kem = b64decode(data["kem"])
            sig = b64decode(data["sig"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"public_keys fields must be base64 strings: {exc}") from exc
        version = data.get("v", PUBLIC_KEYS_VERSION)
        if version != PUBLIC_KEYS_VERSION:
            raise ValueError(f"unsupported public_keys version: {version!r}")
        if len(kem) != KEY_SIZE or len(sig) != KEY_SIZE:
            raise ValueError(
                f"public_keys raw keys must be {KEY_SIZE} bytes each"
            )
        return cls(kem=kem, sig=sig, version=version)

    @property
    def fingerprint(self) -> str:
        """Fingerprint of the KEM public key (used as ``key_id``)."""
        return key_fingerprint(self.kem)


# --- sealed message (non-interactive E2EE) ---------------------------------


def _canonical_aad(aad: dict[str, Any]) -> bytes:
    return json.dumps(aad, sort_keys=True, separators=(",", ":")).encode("utf-8")


@dataclass(frozen=True)
class SealedMessage:
    """A ciphertext plus everything the recipient needs to open it.

    Carried over the wire via the envelope's reserved fields (see
    ``to_envelope_fields``): ``security`` (mode/encryption/key_id/nonce),
    ``encrypted_payload`` (base64 ciphertext) and ``aad`` (object
    holding the ephemeral KEM public key and the Ed25519 signature).
    """

    ciphertext: bytes
    nonce: bytes
    key_id: str
    ephemeral_kem_public: bytes
    signature: bytes
    aad: dict[str, Any]

    # -- serialization ------------------------------------------------------

    def ciphertext_b64(self) -> str:
        return b64encode(self.ciphertext)

    def nonce_b64(self) -> str:
        return b64encode(self.nonce)

    def signature_b64(self) -> str:
        return b64encode(self.signature)

    def signing_input(self) -> bytes:
        """Bytes covered by the Ed25519 signature."""
        aad_payload = {k: v for k, v in self.aad.items() if k != "sig"}
        return (
            SIGNING_CONTEXT
            + b"\x00"
            + self.ciphertext
            + b"\x00"
            + self.nonce
            + b"\x00"
            + self.key_id.encode("utf-8")
            + b"\x00"
            + _canonical_aad(aad_payload)
        )

    def to_envelope_fields(self) -> dict[str, Any]:
        """Fill the envelope's reserved security/encrypted_payload/aad fields."""
        return {
            "security": {
                "mode": "e2ee",
                "encryption": ENCRYPTION_ALGORITHM,
                "key_id": self.key_id,
                "nonce": self.nonce_b64(),
            },
            "encrypted_payload": self.ciphertext_b64(),
            "aad": {
                **self.aad,
                "alg": ENCRYPTION_ALGORITHM,
                "kem_ephemeral": b64encode(self.ephemeral_kem_public),
                "sig": self.signature_b64(),
            },
        }

    @classmethod
    def from_envelope_fields(cls, fields: dict[str, Any]) -> "SealedMessage":
        """Reconstruct from envelope ``security``/``encrypted_payload``/``aad``."""
        security = fields["security"]
        aad = dict(fields["aad"])
        signature = b64decode(aad.pop("sig"))
        ephemeral = b64decode(aad.pop("kem_ephemeral"))
        aad.pop("alg", None)
        return cls(
            ciphertext=b64decode(fields["encrypted_payload"]),
            nonce=b64decode(security["nonce"]),
            key_id=security["key_id"],
            ephemeral_kem_public=ephemeral,
            signature=signature,
            aad=aad,
        )


def seal_message(
    plaintext: bytes,
    *,
    recipient_public_keys: AgentPublicKeys,
    sender_signing_private_key: bytes,
    extra_aad: dict[str, Any] | None = None,
) -> SealedMessage:
    """Non-interactively seal *plaintext* for a recipient.

    1. Generate an ephemeral X25519 keypair.
    2. ECDH against the recipient's long-lived KEM public key, then
       HKDF-SHA256 -> AES-256-GCM session key.
    3. Encrypt with a fresh 12-byte nonce; the AEAD AAD authenticates
       the key_id and the aad object.
    4. Ed25519-sign (ciphertext || nonce || key_id || aad) with the
       sender's long-lived signing key.
    """
    ephemeral_private, ephemeral_public = generate_kem_keypair()
    key_id = recipient_public_keys.fingerprint

    aad_payload: dict[str, Any] = dict(extra_aad or {})
    aad_bytes = _canonical_aad(aad_payload)

    session_key = derive_session_key(
        ephemeral_private,
        recipient_public_keys.kem,
        salt=ephemeral_public,
        info=ENCRYPTION_ALGORITHM.encode("ascii"),
    )
    nonce = _generate_nonce()
    aad_for_aead = (
        SIGNING_CONTEXT
        + b"\x00"
        + key_id.encode("utf-8")
        + b"\x00"
        + aad_bytes
    )
    ciphertext = aes_gcm_encrypt(session_key, nonce, plaintext, aad_for_aead)

    unsigned = SealedMessage(
        ciphertext=ciphertext,
        nonce=nonce,
        key_id=key_id,
        ephemeral_kem_public=ephemeral_public,
        signature=b"",
        aad=aad_payload,
    )
    return SealedMessage(
        ciphertext=ciphertext,
        nonce=nonce,
        key_id=key_id,
        ephemeral_kem_public=ephemeral_public,
        signature=sign(sender_signing_private_key, unsigned.signing_input()),
        aad=aad_payload,
    )


def open_message(
    sealed: SealedMessage,
    *,
    recipient_kem_private_key: bytes,
    sender_signing_public_key: bytes,
) -> bytes | None:
    """Open a SealedMessage.

    Returns the plaintext, or ``None`` if the signature does not verify
    against the sender's published signing key or the AEAD tag does not
    validate (callers map this to ``DECRYPT_FAILED``)."""
    if not verify_signature(
        sender_signing_public_key, sealed.signing_input(), sealed.signature
    ):
        return None
    try:
        session_key = derive_session_key(
            recipient_kem_private_key,
            sealed.ephemeral_kem_public,
            salt=sealed.ephemeral_kem_public,
            info=ENCRYPTION_ALGORITHM.encode("ascii"),
        )
    except ValueError:
        return None
    aad_bytes = _canonical_aad(
        {k: v for k, v in sealed.aad.items() if k != "sig"}
    )
    aad_for_aead = (
        SIGNING_CONTEXT
        + b"\x00"
        + sealed.key_id.encode("utf-8")
        + b"\x00"
        + aad_bytes
    )
    return aes_gcm_decrypt(
        session_key, sealed.nonce, sealed.ciphertext, aad_for_aead
    )


def _generate_nonce() -> bytes:
    return os.urandom(NONCE_SIZE)


__all__ = [
    "AEAD_ALGORITHM",
    "ENCRYPTION_ALGORITHM",
    "KDF_ALGORITHM",
    "KEY_SIZE",
    "KEM_ALGORITHM",
    "NONCE_SIZE",
    "PUBLIC_KEYS_VERSION",
    "SIGNATURE_ALGORITHM",
    "SIGNING_CONTEXT",
    "AgentPublicKeys",
    "SealedMessage",
    "aes_gcm_decrypt",
    "aes_gcm_encrypt",
    "b64decode",
    "b64encode",
    "derive_session_key",
    "generate_kem_keypair",
    "generate_signing_keypair",
    "key_fingerprint",
    "open_message",
    "seal_message",
    "sign",
    "verify_signature",
]

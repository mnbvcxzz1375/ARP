"""Read-side degradation view for stored message content / task results.

This module is deliberately SQL-free: it only classifies already-loaded
content dicts. All classification uses the envelope's own marker block
(security / encrypted_payload / aad); no keying material is handled here
and no ciphertext is ever decrypted on the platform side.
"""

from __future__ import annotations

import base64
from typing import Any

from app.protocol.constants import SecurityMode


def _is_base64(value: object) -> bool:
    if not isinstance(value, str) or not value:
        return False
    try:
        # validate=True: non-alphabet characters are rejected rather
        # than silently discarded ("###" would otherwise decode to b"").
        base64.b64decode(value.encode("ascii"), validate=True)
    except (ValueError, UnicodeDecodeError):
        return False
    return True


def build_content_view(content: object) -> Any:
    """Classify a stored content envelope for read-side degradation.

    Judged per stored message independently (mixed plaintext/ciphertext
    histories read correctly because each row is judged on its own
    marker block):

    - no marker block or ``security.mode == relay_visible``: plaintext —
      the content is returned unchanged. Stray same-named payload fields
      (a ``payload.encrypted_payload`` key etc.) never make a plaintext
      message read as ciphertext (zero misclassification);
    - any other mode with a well-formed ciphertext: returns
      ``{"encrypted": True, ...}`` carrying the raw ciphertext and marker
      block — never the plaintext;
    - malformed ciphertext (missing ``security.nonce``, non-base64
      ``encrypted_payload``): returns an ``encrypted_parse_error`` flag
      instead of raising — readers degrade, they never 500.
    """
    if not isinstance(content, dict):
        return content
    security = content.get("security")
    if not isinstance(security, dict):
        return content
    mode = security.get("mode")
    if mode is None or mode == SecurityMode.RELAY_VISIBLE.value:
        return content

    encrypted_payload = content.get("encrypted_payload")
    if not _is_base64(encrypted_payload):
        return {
            "encrypted": False,
            "encrypted_parse_error": True,
            "security": security,
            "reason": "encrypted_payload is missing or not valid base64",
        }
    if not _is_base64(security.get("nonce")):
        return {
            "encrypted": False,
            "encrypted_parse_error": True,
            "security": security,
            "reason": "security.nonce is missing or not valid base64",
        }
    return {
        "encrypted": True,
        "security": security,
        "encrypted_payload": encrypted_payload,
        "aad": content.get("aad"),
    }

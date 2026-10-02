"""Protocol security validators.

Two layers of security-mode validation:

- ``ensure_mvp_security_supported`` validates a parsed ARP ``Envelope``.
  E2EE is now implemented for the non-interactive sealed-message flow,
  but only when the envelope actually carries a ciphertext
  (``encrypted_payload``). A bare ``security.mode = e2ee`` envelope with
  no ciphertext is still the reserved-but-unimplemented shape and stays
  ``E2EE_NOT_IMPLEMENTED`` (501).
- ``ensure_content_security_supported`` validates the task content
  envelope (the ``Message.content`` dict) at task-creation time —
  validate BEFORE persisting (先校验后落库): a malformed e2ee envelope
  must be rejected with 400 and never reach storage.

Both validators look only at the envelope's own reserved marker fields
(``security`` / ``encrypted_payload`` / ``aad``). They never construct,
infer, or rewrite security material — the sender's envelope is the
single source of truth for the marker block.
"""

import base64

from app.exceptions import DomainException
from app.protocol.constants import ErrorCode, SecurityMode
from app.protocol.envelope import Envelope


def ensure_mvp_security_supported(envelope: Envelope) -> None:
    if envelope.security.mode == SecurityMode.E2EE and envelope.encrypted_payload is None:
        # Reserved-but-unimplemented shape: e2ee marker with no ciphertext.
        raise DomainException(
            ErrorCode.E2EE_NOT_IMPLEMENTED,
            "E2EE mode without an encrypted_payload is reserved but not implemented.",
            status_code=501,
        )


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


def ensure_content_security_supported(content: dict) -> None:
    """Validate the marker block of a task content envelope.

    ``content`` is the full ciphertext envelope dict that will be stored
    verbatim in ``Message.content``. Rules:

    - no ``security`` block or mode ``relay_visible``: plaintext, always OK;
    - mode ``e2ee`` (or any non-``relay_visible`` mode) without
      ``encrypted_payload``: reserved shape -> 501;
    - ``encrypted_payload`` / ``security.nonce`` missing or not valid
      base64, or ``aad`` not an object: malformed ciphertext -> 400,
      rejected before any write.
    """
    security = content.get("security") if isinstance(content, dict) else None
    if not isinstance(security, dict):
        return
    mode = security.get("mode")
    if mode is None or mode == SecurityMode.RELAY_VISIBLE.value:
        return

    encrypted_payload = content.get("encrypted_payload")
    if encrypted_payload is None:
        raise DomainException(
            ErrorCode.E2EE_NOT_IMPLEMENTED,
            f"Security mode {mode!r} without an encrypted_payload is reserved "
            f"but not implemented.",
            status_code=501,
        )

    problems: list[str] = []
    if not _is_base64(encrypted_payload):
        problems.append("encrypted_payload must be a non-empty base64 string")
    if not _is_base64(security.get("nonce")):
        problems.append("security.nonce must be a non-empty base64 string")
    if "aad" in content and content["aad"] is not None and not isinstance(content["aad"], dict):
        problems.append("aad must be an object when present")
    if problems:
        raise DomainException(
            ErrorCode.INVALID_REQUEST,
            "Malformed e2ee ciphertext envelope: " + "; ".join(problems),
            status_code=400,
        )


def content_security_mode(content: dict) -> str | None:
    """Read the marker-block mode of a stored content envelope.

    Returns ``None`` when the content carries no marker block. This is a
    plain read: it never constructs or infers a mode the sender did not
    set. A ``relay_visible`` marker with stray same-named payload fields
    is judged plaintext (zero misclassification), per message
    independently.
    """
    if not isinstance(content, dict):
        return None
    security = content.get("security")
    if not isinstance(security, dict):
        return None
    mode = security.get("mode")
    return mode if isinstance(mode, str) else None

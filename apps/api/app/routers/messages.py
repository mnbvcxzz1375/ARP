"""Message read routes.

No dedicated message endpoints exist yet; message content is read through
the task endpoints (``GET /v1/tasks/{task_id}/messages``) and the dashboard
task-detail preview. Those read paths apply the M2 read-side degradation
view (``app.services.message_content_view.build_content_view``):

- plaintext rows (no marker block or ``security.mode == relay_visible``)
  are returned unchanged, even when the payload carries stray
  same-named fields;
- well-formed ciphertext rows return ``{"encrypted": True, ...}`` with
  the raw ciphertext and marker block;
- malformed ciphertext rows (missing ``security.nonce`` / non-base64
  ``encrypted_payload``) return an ``encrypted_parse_error`` flag
  instead of a 500.

Each stored row is classified independently, so plaintext history and
ciphertext new traffic read correctly when interleaved.
"""

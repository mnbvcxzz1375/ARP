/**
 * Read-side classification of a dashboard task content preview.
 *
 * Contract mirror of
 * ``apps/api/app/services/message_content_view.build_content_view``:
 * the dashboard serializes the classified view to a masked JSON string
 * (``mask_secrets_obj(build_content_view(...))`` — see
 * ``apps/api/app/routers/dashboard_user.py`` get_task_detail), so the
 * console may receive:
 *
 * - a plaintext payload (no marker block or
 *   ``security.mode == relay_visible``): unchanged JSON;
 * - a well-formed E2EE row: ``{"encrypted": true, "security": {...},
 *   "encrypted_payload": ..., "aad": ...}`` — never decrypted content;
 * - a malformed row: ``{"encrypted": false, "encrypted_parse_error":
 *   true, "security": {...}, "reason": ...}``.
 *
 * The classifier only reads those flags; unparsable or non-object
 * previews degrade to plaintext (readers degrade, they never throw —
 * the same rule the backend follows).
 */
export type ContentPreviewKind = 'plain' | 'encrypted' | 'parse_error';

export interface ContentPreviewInfo {
  kind: ContentPreviewKind;
  /** security.key_id of the sealing key bundle, when present. */
  keyId?: string;
  /** Backend-supplied parse-error reason, when present. */
  reason?: string;
}

export function classifyContentPreview(
  preview: string | null | undefined,
): ContentPreviewInfo {
  if (!preview) return { kind: 'plain' };
  let parsed: unknown;
  try {
    parsed = JSON.parse(preview);
  } catch {
    return { kind: 'plain' };
  }
  if (typeof parsed !== 'object' || parsed === null || Array.isArray(parsed)) {
    return { kind: 'plain' };
  }
  const obj = parsed as Record<string, unknown>;
  if (obj.encrypted === true) {
    const security = obj.security;
    const keyId =
      typeof security === 'object' && security !== null
        ? (security as Record<string, unknown>).key_id
        : undefined;
    return {
      kind: 'encrypted',
      keyId: typeof keyId === 'string' && keyId ? keyId : undefined,
    };
  }
  if (obj.encrypted_parse_error === true) {
    const reason = obj.reason;
    return {
      kind: 'parse_error',
      reason: typeof reason === 'string' && reason ? reason : undefined,
    };
  }
  return { kind: 'plain' };
}

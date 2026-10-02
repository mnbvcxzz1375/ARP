import { useT } from '../i18n';
import { PIXEL_CHIP } from '../lib/tokens';
import { classifyContentPreview } from '../lib/contentView';
import { cn } from '../lib/utils';

/**
 * Console view of a dashboard task content preview (payload / result).
 *
 * The preview arrives as the masked JSON serialization of the backend
 * M2 read-side degradation view (see lib/contentView.ts for the
 * contract); this component badges the encryption state and renders the
 * raw preview as text. Ciphertext is never decrypted, and a malformed
 * row badges as a parse error instead of failing the page.
 */
export default function ContentPreview({
  preview,
}: {
  preview: string | null | undefined;
}) {
  const t = useT();
  const info = classifyContentPreview(preview);

  if (!preview) {
    return <span className="font-mono text-lg text-pixel-muted">-</span>;
  }

  return (
    <div className="mt-1 space-y-2">
      {info.kind === 'encrypted' && (
        <div className="flex flex-wrap items-center gap-2">
          {/* Amber chip: E2EE ciphertext needs operator attention but is
              not an error (LED fill keeps AA contrast in both themes). */}
          <span
            className={cn(
              'inline-flex items-center px-2 py-0.5 font-pixel text-sm leading-none',
              PIXEL_CHIP.warn,
            )}
          >
            {t('tasks.content.encrypted')}
          </span>
          {info.keyId && (
            <span className="font-mono text-sm text-pixel-muted">
              {t('tasks.content.keyId')}: {info.keyId.slice(0, 16)}
            </span>
          )}
        </div>
      )}
      {info.kind === 'parse_error' && (
        <div className="space-y-1">
          <span
            className={cn(
              'inline-flex items-center px-2 py-0.5 font-pixel text-sm leading-none',
              PIXEL_CHIP.bad,
            )}
          >
            {t('tasks.content.parseError')}
          </span>
          {info.reason && (
            <p className="font-mono text-sm text-pixel-muted">{info.reason}</p>
          )}
        </div>
      )}
      {/* Terminal well: bg base + 2px pixel step, fg text (12.39:1 both
          themes). The raw preview is the ciphertext / plaintext itself. */}
      <pre className="whitespace-pre-wrap break-all bg-pixel-bg border-2 border-pixel-line p-3 font-mono text-base text-pixel-fg max-h-48 overflow-auto">
        {preview}
      </pre>
    </div>
  );
}

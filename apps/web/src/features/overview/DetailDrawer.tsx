import { useEffect, useRef } from 'react';
import type { ReactNode } from 'react';
import { useT } from '../../i18n';
import { TOUCH_TARGET } from '../../lib/tokens';

/**
 * DetailDrawer - the <768px detail surface of the overview.
 *
 * Why this component exists: the repo has no generic Drawer (the pixel
 * and features directories were searched; nothing reusable). The
 * responsive spec demotes the right 320px panel to a fixed drawer below
 * 768px (768–1023px keeps the map + this drawer, >=1024px shows the
 * three-column grid). This is a new, overview-scoped component — other
 * pages keep their own dialogs (ConfirmDialog / FormDialog).
 *
 * Composition: the drawer renders arbitrary children; the overview feeds
 * it an AgentDetailPanel (with showHeader={false} — the drawer supplies
 * its own title bar with the close button), so the panel content is
 * literally the same component as the desktop column, not a fork.
 *
 * A11y contract (spec: fixed, title bar with close, Escape closes,
 * focus returns to the trigger):
 * - role="dialog" + aria-modal + the title (explicit `title` prop, or
 *   the overview default "Agent details" when the caller — like the
 *   current page — lets the embedded panel header carry the visible
 *   title and passes none);
 * - Escape (keydown) calls onClose;
 * - the element focused right before opening is remembered and regains
 *   focus when the drawer closes (as long as it is still in the document
 *   — a since-unmounted trigger falls back to the close button);
 * - on open the close button is focused so keyboard users land inside;
 * - the scrim is a plain inert layer (aria-hidden, no focus) that also
 *   closes on click; mouse users get the same outcome as Escape.
 *
 * No timers, no transitions: a hard swap in and out (the reduced-motion
 * rules in index.css already zero transition-duration; the drawer simply
 * has none to begin with).
 */
export interface DetailDrawerProps {
  /** Renders the body (mounted) only while true. */
  open: boolean;
  /** Called by Escape, scrim click and the close button. */
  onClose: () => void;
  /** Dialog title, also the drawer title-bar label. Optional: the
   *  overview page embeds the AgentDetailPanel whose own header is the
   *  visible title, so the drawer falls back to the i18n default for
   *  the accessible name and renders a close-only bar. */
  title?: string;
  /** Panel body — AgentDetailPanel content (desktop column parity). */
  children: ReactNode;
}

export default function DetailDrawer({ open, onClose, title, children }: DetailDrawerProps) {
  const t = useT();
  /** Accessible name when no explicit title is supplied (the overview
   *  page embeds the panel whose own header is the visible title). */
  const accessibleTitle = title ?? t('overview.drawer.defaultTitle');
  const closeButtonRef = useRef<HTMLButtonElement>(null);
  const dialogRef = useRef<HTMLDivElement>(null);

  // Escape closes the drawer. Keydown on window so focus cannot escape
  // the contract by tabbing to the address bar mid-interaction.
  useEffect(() => {
    if (!open) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        event.preventDefault();
        onClose();
        return;
      }
      if (event.key !== 'Tab' || !dialogRef.current) return;
      const dialog = dialogRef.current;
      const focusable = Array.from(dialog.querySelectorAll<HTMLElement>(
        'button:not([disabled]), a[href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])',
      )).filter((element) => !element.hidden);
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (!first || !last) return;
      const outside = !dialog.contains(document.activeElement);
      if (event.shiftKey && (document.activeElement === first || outside)) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && (document.activeElement === last || outside)) {
        event.preventDefault();
        first.focus();
      }
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [open, onClose]);

  // Open: remember the trigger (whatever had focus) and land focus on the
  // close button. Close: give focus back to the trigger if it survives.
  useEffect(() => {
    if (!open) return;
    const trigger = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    closeButtonRef.current?.focus();
    // The overview unmounts the drawer rather than changing open to false.
    // Cleanup handles both closing strategies, including StrictMode replay.
    return () => {
      if (trigger?.isConnected) trigger.focus();
    };
  }, [open]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex justify-end" role="presentation">
      {/* Scrim: decorative/inert layer, one rgba() of black (no new
          palette token); clicking it closes like the Escape key. */}
      <div
        aria-hidden="true"
        onClick={onClose}
        className="absolute inset-0 bg-[rgba(0,0,0,0.5)]"
      />
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-label={accessibleTitle}
        className="relative flex h-full w-full max-w-sm flex-col border-l-2 border-pixel-line bg-pixel-surface"
      >
        {/* Title bar: 64px (h-16) like the top bar, with the close
            button at a 44px touch target. */}
        <div className="flex h-16 shrink-0 items-center justify-between gap-4 border-b-2 border-pixel-line px-4">
          {title ? (
            <h2 className="truncate font-display text-pixel-base uppercase tracking-pixel text-pixel-fg">
              {title}
            </h2>
          ) : (
            <span aria-hidden="true" className="min-w-0 flex-1" />
          )}
          <button
            ref={closeButtonRef}
            type="button"
            onClick={onClose}
            aria-label={t('overview.drawer.close')}
            className={
              'inline-flex items-center justify-center border-2 border-pixel-line ' +
              'bg-pixel-surface px-4 py-1 font-pixel text-pixel-sm text-pixel-fg ' +
              'hover:bg-pixel-raised active:translate-y-[2px] ' +
              TOUCH_TARGET
            }
          >
            {t('overview.drawer.close')}
          </button>
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto">{children}</div>
      </div>
    </div>
  );
}

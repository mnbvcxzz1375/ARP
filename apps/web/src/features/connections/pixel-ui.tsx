/**
 * Pixel UI primitives shared by the user-facing business pages surface
 * (connections / approvals / api-keys / enterprise).
 *
 * These are page-level building blocks only. The design system itself
 * (src/components/*, src/lib/tokens.ts, tailwind.config.ts, src/index.css)
 * is NOT modified here. Contrast values follow the design system rules:
 * - accent solid block + #191a26 text = 5.36:1 in BOTH themes
 * - LED solid chips (#f4f4fa on #ac3232) = 5.89:1 in both themes
 * - info chip (#191a26 on accent-2) = 9.32:1 in dark, 2.56:1 in light
 *   (measured; the legacy "9.32:1 in both themes" note was wrong for the
 *   light theme. The light-theme chip fails WCAG 1.4.3 AA, and the class
 *   is pinned by __tests__/BadgesAndCards.test.tsx, so fixing it requires
 *   changing a locked assertion.)
 * - ghost surface = pixel-fg on pixel-surface = 12.39:1
 * Hard edges only, spacing on the 4px grid, no transitions.
 *
 * Single-accent rule (see index.css): --pixel-accent is the only decorative
 * emphasis color. The 'info' variant below uses accent-2 in its functional
 * role (info-state chip + focus ring + link affordance), the same exception
 * family as the LED status colors, never as a second decorative accent.
 */
import { ButtonHTMLAttributes, ReactNode, useEffect, useRef, useState } from 'react';
import { Check, Copy } from 'lucide-react';
import { cn } from '../../lib/utils';
import { PIXEL_CHIP, TOUCH_TARGET } from '../../lib/tokens';
import { usePreferences } from '../../hooks/usePreferences';
import { useT } from '../../i18n';

export type PixButtonVariant = 'primary' | 'info' | 'ok' | 'danger' | 'ghost';

const BUTTON_VARIANTS: Record<PixButtonVariant, string> = {
  // Accent solid block + #191a26 text: 5.36:1 in dark AND light theme.
  primary: 'bg-pixel-accent text-[#191a26] border-2 border-[#191a26]',
  // accent-2 solid + #191a26 text: 9.32:1 dark / 2.56:1 light (measured).
  // Functional info-state role, not a second decorative accent; the class
  // is pinned by __tests__/BadgesAndCards.test.tsx (see file header).
  info: 'bg-pixel-accent-2 text-[#191a26] border-2 border-[#191a26]',
  // LED green solid + dark text (11.24:1 both themes).
  ok: 'bg-pixel-led-green text-[#191a26] border-2 border-[#191a26]',
  // LED red solid chip: 5.89:1 in both themes (ErrorState pattern).
  danger: 'bg-pixel-led-red text-[#f4f4fa] border-2 border-[#191a26]',
  // Secondary action: pixel-fg on pixel-surface (12.39:1).
  ghost: 'bg-pixel-surface text-pixel-fg border-2 border-pixel-line hover:bg-pixel-raised',
};

interface PixButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: PixButtonVariant;
  /** Compact in-table row action: dense data context, no 44px target. */
  compact?: boolean;
}

/**
 * Press feedback: buttons sink 2px while pressed. An active-pseudo-class
 * hard switch (no transition), so it survives the reduced-motion rule that
 * zeroes transition-duration. Shared by PixButton, FilterPill and
 * PIX_LINK_PRIMARY links.
 */
export const PRESS_FEEDBACK = 'active:translate-y-[2px]';

/**
 * Primary link-as-button classes for router <Link> action entries.
 * PixButton renders a fixed <button>, so link-shaped actions use this
 * constant on an <a>/<Link> instead - never wrap a button in a link
 * (a > button is invalid nesting).
 */
export const PIX_LINK_PRIMARY = cn(
  'inline-flex items-center justify-center',
  TOUCH_TARGET,
  'px-4 py-2 font-pixel text-pixel-base bg-pixel-accent text-[#191a26] border-2 border-[#191a26]',
  PRESS_FEEDBACK,
);

export function PixButton({
  variant = 'primary',
  compact = false,
  className,
  ...props
}: PixButtonProps) {
  return (
    <button
      className={cn(
        'inline-flex items-center justify-center font-pixel disabled:opacity-50 disabled:cursor-not-allowed',
        PRESS_FEEDBACK,
        compact ? 'py-1 px-3 text-pixel-sm' : cn(TOUCH_TARGET, 'px-4 py-2 text-pixel-base'),
        BUTTON_VARIANTS[variant],
        className,
      )}
      {...props}
    />
  );
}

/**
 * Copy-to-clipboard button with a pixel check-mark success state.
 *
 * Copy -> Check (16px, strokeWidth 2) + `common.action.copied` for 1200ms,
 * then rolls back. The rollback is the only JS timer here, so it is guarded
 * like every other timer: under `prefers-reduced-motion: reduce` or a
 * manual reduced-motion preference the success check never appears (terminal
 * state) and no timer is armed. On failure (permission denied / no clipboard
 * API) nothing is faked: no check is shown and an aria-live="polite" region
 * announces `common.action.copyFailed`. Keys live in the eager `common`
 * namespace because pixel-ui is consumed by 16+ pages whose lazy chunks do
 * not load a page-local namespace.
 */
export function PixelCopyButton({ text, className }: { text: string; className?: string }) {
  const t = useT();
  const { data: preferences } = usePreferences();
  const [copied, setCopied] = useState(false);
  const [failed, setFailed] = useState(false);
  const rollbackTimer = useRef<number | null>(null);

  const reducedMotion =
    preferences?.reducedMotion === true ||
    (typeof window !== 'undefined' &&
      typeof window.matchMedia === 'function' &&
      window.matchMedia('(prefers-reduced-motion: reduce)').matches);

  const clearRollback = () => {
    if (rollbackTimer.current !== null) {
      window.clearTimeout(rollbackTimer.current);
      rollbackTimer.current = null;
    }
  };

  // Clear the rollback timer if the button unmounts mid-success state.
  useEffect(() => () => clearRollback(), []);

  const handleCopy = async () => {
    if (typeof navigator === 'undefined' || !navigator.clipboard?.writeText) {
      setCopied(false);
      setFailed(true);
      return;
    }
    try {
      await navigator.clipboard.writeText(text);
      setFailed(false);
      if (reducedMotion) return; // terminal state: no check, no timer
      setCopied(true);
      clearRollback();
      rollbackTimer.current = window.setTimeout(() => setCopied(false), 1200);
    } catch {
      setCopied(false);
      setFailed(true); // never fake a success state
    }
  };

  return (
    <button
      type="button"
      onClick={handleCopy}
      aria-label={t('common.action.copy')}
      className={cn(
        'inline-flex items-center justify-center gap-2',
        TOUCH_TARGET,
        'px-4 py-2 font-pixel text-pixel-base',
        'bg-pixel-accent-2 text-[#191a26] border-2 border-[#191a26]',
        PRESS_FEEDBACK,
        className,
      )}
    >
      {copied ? (
        <Check size={16} strokeWidth={2} aria-hidden="true" />
      ) : (
        <Copy size={16} strokeWidth={2} aria-hidden="true" />
      )}
      <span aria-hidden="true">{copied ? t('common.action.copied') : t('common.action.copy')}</span>
      {/* Failure announcement only; success is conveyed by the visual check. */}
      <span aria-live="polite" className="sr-only">
        {failed ? t('common.action.copyFailed') : ''}
      </span>
    </button>
  );
}

/** LED red solid chip for inline error feedback (AA in both themes). */
export function ErrorBanner({
  message,
  className,
}: {
  message: ReactNode;
  className?: string;
}) {
  return (
    <div
      role="alert"
      className={cn(
        'mb-4 p-3 font-pixel text-pixel-sm bg-pixel-led-red text-[#f4f4fa] border-2 border-[#191a26]',
        className,
      )}
    >
      {message}
    </div>
  );
}

/** Page title: PS2P 12px mobile / 16px desktop (16px grid). */
export function PageTitle({
  children,
  className,
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <h2
      className={cn(
        'mb-6 font-display text-pixel-base sm:text-pixel-lg text-pixel-fg',
        className,
      )}
    >
      {children}
    </h2>
  );
}

/** Title row with right-aligned action slot; single column below 768px. */
export function PageTitleRow({
  title,
  actions,
  className,
}: {
  title: ReactNode;
  actions?: ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cn(
        'mb-6 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between',
        className,
      )}
    >
      <h2 className="font-display text-pixel-base sm:text-pixel-lg text-pixel-fg">{title}</h2>
      {actions ? <div className="flex flex-wrap gap-2">{actions}</div> : null}
    </div>
  );
}

/** Pixel panel with optional raised header strip separated by a 2px line. */
export function PixelPanel({
  title,
  actions,
  children,
  className,
  bodyClassName,
}: {
  title?: ReactNode;
  actions?: ReactNode;
  children: ReactNode;
  className?: string;
  bodyClassName?: string;
}) {
  return (
    <div className={cn('bg-pixel-surface border-2 border-pixel-line', className)}>
      {title || actions ? (
        <div className="flex flex-col gap-3 border-b-2 border-pixel-line bg-pixel-raised px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
          {title ? (
            <h3 className="font-pixel text-pixel-sm uppercase tracking-pixel text-pixel-muted">
              {title}
            </h3>
          ) : (
            <span />
          )}
          {actions}
        </div>
      ) : null}
      <div className={bodyClassName}>{children}</div>
    </div>
  );
}

/** Filter pill; active state is an accent solid block (5.36:1 both themes). */
export function FilterPill({
  active,
  className,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { active: boolean }) {
  return (
    <button
      className={cn(
        'min-h-[44px] px-4 py-1 font-pixel text-pixel-sm border-2',
        PRESS_FEEDBACK,
        active
          ? 'bg-pixel-accent text-[#191a26] border-[#191a26]'
          : 'bg-pixel-surface text-pixel-fg border-pixel-line hover:bg-pixel-raised',
        className,
      )}
      {...props}
    />
  );
}

/** Yes/No status chip on the LED palette (real state only, never decor). */
export function YesNoChip({ value }: { value: boolean }) {
  const t = useT();
  return (
    <span
      className={cn(
        'inline-flex items-center px-2 py-0.5 font-pixel text-sm leading-none',
        value ? PIXEL_CHIP.ok : PIXEL_CHIP.neutral,
      )}
    >
      {value ? t('connections.chip.yes') : t('connections.chip.no')}
    </span>
  );
}

/** Neutral label chip for enum values (protocol, channel type, mode...). */
export function NeutralChip({ children }: { children: ReactNode }) {
  return (
    <span
      className={cn(
        'inline-flex items-center px-2 py-0.5 font-pixel text-sm leading-none',
        PIXEL_CHIP.neutral,
      )}
    >
      {children}
    </span>
  );
}

/** Full-width form control: VT323 18px on recessed pixel-bg surface. */
export const PIXEL_INPUT =
  'w-full px-3 py-2 font-mono text-lg text-pixel-fg bg-pixel-bg border-2 border-pixel-line focus:border-pixel-accent-2 disabled:opacity-50 disabled:cursor-not-allowed';

/** Compact in-table select (dense data column context). */
export const PIXEL_SELECT_COMPACT =
  'px-2 py-1 font-mono text-base text-pixel-fg bg-pixel-bg border-2 border-pixel-line focus:border-pixel-accent-2 disabled:opacity-50 disabled:cursor-not-allowed';

/** Form field label in the PS2P label style (matches StatCard labels). */
export function PixelField({
  label,
  htmlFor,
  children,
}: {
  label: string;
  htmlFor?: string;
  children: ReactNode;
}) {
  return (
    <div>
      <label
        htmlFor={htmlFor}
        className="mb-1 block font-pixel text-pixel-sm uppercase tracking-pixel text-pixel-muted"
      >
        {label}
      </label>
      {children}
    </div>
  );
}

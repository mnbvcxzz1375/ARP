/**
 * Local pixel UI kit for the admin feature pages.
 *
 * The shared design-system components (DataTable / StatCard / StatusBadge /
 * ErrorState / ...) already speak the pixel language; this kit covers the
 * page-level chrome that only admin pages need (headers, panels, detail
 * fields, code blocks, table row action buttons, error banners).
 *
 * Rules followed (see DesignSystemDoc):
 * - One accent (#df7126). Status colors are the LED trio and only express
 *   real status (destructive actions reuse the LED-red chip, mirroring
 *   ConfirmDialog's danger variant).
 * - Every "text on theme-variable background" pair is either
 *   pixel-fg/pixel-muted on surface (pre-verified 12.39:1 / 6.84:1) or a
 *   solid semantic chip with a fixed text color (LED chip pattern).
 * - All corners hard; 2px pixel step borders; 4px-grid spacing.
 * - No em-dash / en-dash in any copy.
 */
import type { ButtonHTMLAttributes, ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { AlertTriangle, ArrowLeft } from 'lucide-react';
import { cn } from '../../lib/utils';
import { PIXEL_CHIP } from '../../lib/tokens';

/** Page title bar: Press Start 2P on a 2px pixel rule. */
export function PageHeader({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="mb-6 border-b-2 border-pixel-line pb-3">
      <h2 className="font-display text-pixel-lg leading-tight text-pixel-fg md:text-pixel-2xl">
        {title}
      </h2>
      {children}
    </div>
  );
}

/** Back navigation chip: accent solid block on hover (5.36:1 both themes). */
export function BackLink({ to, children }: { to: string; children: ReactNode }) {
  return (
    <Link
      to={to}
      className="mb-4 inline-flex min-h-[44px] items-center gap-2 border-2 border-pixel-line bg-pixel-raised px-3 py-1 font-pixel text-pixel-base text-pixel-fg hover:bg-pixel-accent hover:text-[#191a26]"
    >
      <ArrowLeft className="h-4 w-4" strokeWidth={2} aria-hidden="true" />
      {children}
    </Link>
  );
}

/**
 * Pixel panel: hard-edged surface with a hard pixel-step shadow. Optional
 * section title in Pixelify Sans uppercase (never inside dense data).
 */
export function Panel({
  title,
  icon,
  children,
  className,
}: {
  title?: string;
  icon?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section
      className={cn(
        'border-2 border-pixel-line bg-pixel-surface p-4 shadow-pixel-sm md:p-6',
        className,
      )}
    >
      {title && (
        <h3 className="mb-4 flex items-center gap-2 font-pixel text-pixel-base uppercase tracking-pixel text-pixel-muted">
          {icon}
          {title}
        </h3>
      )}
      {children}
    </section>
  );
}

/** Key/value field for detail pages. */
export function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div>
      <dt className="font-pixel text-pixel-sm uppercase tracking-pixel text-pixel-muted">
        {label}
      </dt>
      <dd className="mt-1 text-base text-pixel-fg">{children}</dd>
    </div>
  );
}

/** Monospace code block on the raw page background (both themes pass AA). */
export function CodeBlock({ content }: { content: string | null | undefined }) {
  if (!content) return <span className="text-base text-pixel-muted">-</span>;
  return (
    <pre className="mt-1 max-h-48 overflow-auto whitespace-pre-wrap break-all border-2 border-pixel-line bg-pixel-bg p-3 font-mono text-base text-pixel-fg">
      {content}
    </pre>
  );
}

/**
 * Error content block: solid LED-red chip with fixed light text
 * (5.89:1 in both themes), consistent with ErrorState / StepUpDialog.
 */
export function ErrorBlock({ content }: { content: string | null | undefined }) {
  return (
    <pre className="mt-1 max-h-48 overflow-auto whitespace-pre-wrap break-all border-2 border-[#191a26] bg-pixel-led-red p-3 font-mono text-base text-[#f4f4fa]">
      {content}
    </pre>
  );
}

/** Neutral tag chip (capabilities etc.) - not a status, so no LED fill. */
export function TagChip({ children }: { children: ReactNode }) {
  return (
    <span className="inline-flex items-center border-2 border-pixel-line bg-pixel-raised px-2 py-1 font-pixel text-pixel-base text-pixel-fg">
      {children}
    </span>
  );
}

type PixelActionVariant = 'accent' | 'danger' | 'neutral';

const ACTION_VARIANTS: Record<PixelActionVariant, string> = {
  // Primary action: accent solid block + #191a26 text (5.36:1 both themes).
  accent: 'bg-pixel-accent text-[#191a26] border-[#191a26]',
  // Destructive action: LED-red chip + fixed light text (5.89:1 both themes).
  danger: 'bg-pixel-led-red text-[#f4f4fa] border-[#191a26]',
  // Secondary action: fg on surface (pre-verified AA).
  neutral: 'bg-pixel-surface text-pixel-fg border-pixel-line hover:bg-pixel-raised',
};

/**
 * Compact pixel button for table rows. Kept compact (no 44px min-height) so
 * the 36px table row grid of the PC cockpit density is preserved; mobile
 * navigation targets use TOUCH_TARGET via the shell / Pagination instead.
 */
export function PixelActionButton({
  variant = 'neutral',
  className,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: PixelActionVariant }) {
  return (
    <button
      {...props}
      className={cn(
        'inline-flex items-center justify-center border-2 px-2 py-1 font-pixel text-pixel-base disabled:opacity-50',
        ACTION_VARIANTS[variant],
        className,
      )}
    />
  );
}

/** Table-row detail link in the same chip language as the action buttons. */
export function DetailLink({ to, children }: { to: string; children: ReactNode }) {
  return (
    <Link
      to={to}
      className="inline-flex items-center border-2 border-pixel-line bg-pixel-raised px-2 py-1 font-pixel text-pixel-base text-pixel-fg hover:bg-pixel-accent hover:text-[#191a26]"
    >
      {children}
    </Link>
  );
}

/** Mutation error banner (contract: data-testid="action-error"). */
export function ActionErrorBanner({ message }: { message: string }) {
  return (
    <div
      data-testid="action-error"
      className="mb-4 flex items-start gap-2 border-2 border-[#191a26] bg-pixel-led-red p-3 font-pixel text-pixel-base text-[#f4f4fa]"
    >
      <AlertTriangle className="h-4 w-4 shrink-0" strokeWidth={2} aria-hidden="true" />
      <span>{message}</span>
    </div>
  );
}

/** Worker health readout: solid LED chip (real status only). */
export function WorkerHealthChip({
  label,
  status,
}: {
  label?: string;
  status: string | null | undefined;
}) {
  const ok = status === 'ok';
  return (
    <span
      className={cn(
        'inline-flex items-center gap-2 border-2 border-[#191a26] px-3 py-1 font-pixel text-pixel-base',
        ok ? PIXEL_CHIP.ok : PIXEL_CHIP.bad,
      )}
    >
      {label ? `${label}: ` : ''}
      {status ?? 'unknown'}
    </span>
  );
}

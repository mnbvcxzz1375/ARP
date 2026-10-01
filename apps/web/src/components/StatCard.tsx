import { cn } from '../lib/utils';

interface StatCardProps {
  label: string;
  value: string | number;
  variant?: 'default' | 'danger';
  className?: string;
}

export default function StatCard({ label, value, variant = 'default', className }: StatCardProps) {
  return (
    <div
      className={cn(
        'relative border-2 p-4 bg-pixel-surface',
        variant === 'danger' ? 'border-pixel-led-red' : 'border-pixel-line',
        className,
      )}
    >
      {/* Semantic LED strip: 4px grid step, real status meaning only. */}
      {variant === 'danger' && (
        <div
          className="absolute inset-x-0 top-0 h-1 bg-pixel-led-red"
          aria-hidden="true"
        />
      )}
      <p className="font-pixel text-pixel-sm uppercase tracking-pixel text-pixel-muted">
        {label}
      </p>
      <p
        className="mt-2 font-display text-pixel-2xl leading-tight text-pixel-fg"
        data-testid="stat-card-value"
      >
        {value}
      </p>
    </div>
  );
}

import { cn } from '../lib/utils';

interface StatCardProps {
  label: string;
  value: string | number;
  variant?: 'default' | 'danger';
  className?: string;
}

export default function StatCard({ label, value, variant = 'default', className }: StatCardProps) {
  return (
    <div className={cn(
      'rounded-lg border p-4',
      variant === 'danger' ? 'border-red-200 bg-red-50' : 'border-gray-200 bg-white',
      className,
    )}>
      <p className="text-xs font-medium text-gray-500 uppercase tracking-wide">{label}</p>
      <p className={cn(
        'mt-1 text-2xl font-bold',
        variant === 'danger' ? 'text-red-700' : 'text-gray-900',
      )}>{value}</p>
    </div>
  );
}

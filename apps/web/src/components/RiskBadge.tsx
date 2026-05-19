import { cn } from '../lib/utils';

const RISK_MAP: Record<string, string> = {
  low: 'bg-green-100 text-green-800',
  medium: 'bg-yellow-100 text-yellow-800',
  high: 'bg-red-100 text-red-800',
  critical: 'bg-red-200 text-red-900',
};

export default function RiskBadge({ level }: { level: string }) {
  const cls = RISK_MAP[level.toLowerCase()] ?? 'bg-gray-100 text-gray-600';
  return (
    <span className={cn('inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium capitalize', cls)}>
      {level}
    </span>
  );
}

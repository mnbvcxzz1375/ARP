import { cn } from '../lib/utils';

const STATUS_MAP: Record<string, { label: string; cls: string }> = {
  created: { label: 'Created', cls: 'bg-blue-100 text-blue-800' },
  delivered: { label: 'Delivered', cls: 'bg-indigo-100 text-indigo-800' },
  accepted: { label: 'Accepted', cls: 'bg-green-100 text-green-800' },
  running: { label: 'Running', cls: 'bg-yellow-100 text-yellow-800' },
  completed: { label: 'Completed', cls: 'bg-green-100 text-green-800' },
  failed: { label: 'Failed', cls: 'bg-red-100 text-red-800' },
  expired: { label: 'Expired', cls: 'bg-gray-100 text-gray-600' },
  cancelled: { label: 'Cancelled', cls: 'bg-gray-100 text-gray-600' },
  pending: { label: 'Pending', cls: 'bg-yellow-100 text-yellow-800' },
  rejected: { label: 'Rejected', cls: 'bg-red-100 text-red-800' },
  online: { label: 'Online', cls: 'bg-green-100 text-green-800' },
  offline: { label: 'Offline', cls: 'bg-gray-100 text-gray-600' },
};

export default function StatusBadge({ status }: { status: string }) {
  const info = STATUS_MAP[status.toLowerCase()] ?? { label: status, cls: 'bg-gray-100 text-gray-600' };
  return (
    <span className={cn('inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium', info.cls)}>
      {info.label}
    </span>
  );
}

import { cn } from '../lib/utils';

const ROLE_MAP: Record<string, string> = {
  user: 'bg-blue-100 text-blue-800',
  admin: 'bg-purple-100 text-purple-800',
  super_admin: 'bg-red-100 text-red-800',
};

export default function RoleBadge({ role }: { role: string }) {
  const cls = ROLE_MAP[role] ?? 'bg-gray-100 text-gray-600';
  return (
    <span className={cn('inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium', cls)}>
      {role.replace(/_/g, ' ')}
    </span>
  );
}

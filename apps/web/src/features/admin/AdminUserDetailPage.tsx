import { useParams, Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { ArrowLeft } from 'lucide-react';
import api from '../../api/client';
import RoleBadge from '../../components/RoleBadge';
import LoadingState from '../../components/LoadingState';
import ErrorState from '../../components/ErrorState';

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <dt className="text-xs font-medium text-gray-500 uppercase">{label}</dt>
      <dd className="mt-1 text-sm text-gray-900">{children}</dd>
    </div>
  );
}

export default function AdminUserDetailPage() {
  const { userId } = useParams<{ userId: string }>();

  const { data, isLoading, isError } = useQuery({
    queryKey: ['admin/user-detail', userId],
    queryFn: () => api.get(`/v1/dashboard/admin/users/${userId}`).then((r) => r.data),
    enabled: !!userId,
  });

  if (isLoading) return <LoadingState />;
  if (isError) return <ErrorState message="Failed to load user detail" />;

  const user = data;

  return (
    <div>
      <Link
        to="/admin/users"
        className="inline-flex items-center gap-1 text-sm text-blue-600 hover:underline mb-4"
      >
        <ArrowLeft className="h-4 w-4" />
        Back to Users
      </Link>
      <h2 className="text-xl font-semibold mb-6">{user.username}</h2>

      <div className="bg-white rounded-lg border p-6">
        <h3 className="text-sm font-semibold text-gray-700 mb-4">User Details</h3>
        <dl className="grid grid-cols-2 gap-4">
          <Field label="Username">{user.username}</Field>
          <Field label="Role">
            <RoleBadge role={user.role} />
          </Field>
          <Field label="Disabled">{user.is_disabled ? 'Yes' : 'No'}</Field>
          <Field label="Created">{new Date(user.created_at).toLocaleString()}</Field>
          <Field label="Agents">{user.agents_count}</Field>
          <Field label="Active API Keys">{user.active_api_keys_count}</Field>
          <Field label="Tasks (24h)">{user.tasks_24h}</Field>
          <Field label="Failed Tasks (24h)">{user.failed_tasks_24h}</Field>
          <Field label="Active Sessions">{user.active_sessions_count}</Field>
          <Field label="Recent Audit Events">{user.recent_audit_count}</Field>
        </dl>
      </div>
    </div>
  );
}

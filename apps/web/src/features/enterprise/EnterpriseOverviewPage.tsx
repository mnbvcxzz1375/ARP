import { useQuery } from '@tanstack/react-query';
import api from '../../api/client';
import StatCard from '../../components/StatCard';
import LoadingState from '../../components/LoadingState';
import ErrorState from '../../components/ErrorState';

export default function EnterpriseOverviewPage() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ['admin/overview'],
    queryFn: () => api.get('/v1/dashboard/admin/overview').then((r) => r.data),
    refetchInterval: 30000,
  });

  if (isLoading) return <LoadingState />;
  if (isError) return <ErrorState message="Failed to load enterprise overview" />;

  const stats = [
    { label: 'Total Users', value: data?.total_users ?? 0 },
    { label: 'Active Users', value: data?.active_users ?? 0 },
    { label: 'Disabled Users', value: data?.disabled_users ?? 0, variant: 'danger' as const },
    { label: 'Total Agents', value: data?.total_agents ?? 0 },
    { label: 'Online Agents', value: data?.online_agents ?? 0 },
    { label: 'WS Connections', value: data?.active_ws_connections ?? 0 },
    { label: 'Tasks (1h)', value: data?.tasks_1h ?? 0 },
    { label: 'Tasks (24h)', value: data?.tasks_24h ?? 0 },
    { label: 'Tasks (7d)', value: data?.tasks_7d ?? 0 },
    { label: 'Failed Tasks', value: data?.failed_tasks ?? 0, variant: 'danger' as const },
    { label: 'Expired Tasks', value: data?.expired_tasks ?? 0 },
    { label: 'Pending Approvals', value: data?.pending_approvals ?? 0 },
    { label: 'Pending Messages', value: data?.pending_messages ?? 0 },
  ];

  return (
    <div>
      <h2 className="text-xl font-semibold mb-6">Enterprise Overview</h2>
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-4">
        {stats.map((s) => <StatCard key={s.label} {...s} />)}
      </div>
      <div className="mt-6 flex gap-4">
        <div className={`px-3 py-1 rounded text-sm font-medium ${
          data?.retry_worker_health === 'ok' ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'
        }`}>
          Retry Worker: {data?.retry_worker_health ?? 'unknown'}
        </div>
        <div className={`px-3 py-1 rounded text-sm font-medium ${
          data?.timeout_worker_health === 'ok' ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'
        }`}>
          Timeout Worker: {data?.timeout_worker_health ?? 'unknown'}
        </div>
      </div>
    </div>
  );
}

import { useQuery } from '@tanstack/react-query';
import api from '../../api/client';
import StatCard from '../../components/StatCard';
import DataTable from '../../components/DataTable';
import LoadingState from '../../components/LoadingState';
import ErrorState from '../../components/ErrorState';

export default function OverviewPage() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ['dashboard/overview'],
    queryFn: () => api.get('/v1/dashboard/overview').then((r) => r.data),
    refetchInterval: 15000,
  });

  if (isLoading) return <LoadingState />;
  if (isError) return <ErrorState message="Failed to load overview" />;

  const stats = [
    { label: 'Online Agents', value: data?.online_agents ?? 0 },
    { label: 'Tasks Today', value: data?.tasks_today ?? 0 },
    { label: 'Failed Tasks', value: data?.failed_tasks ?? 0, variant: 'danger' as const },
    { label: 'Pending Approvals', value: data?.pending_approvals ?? 0 },
    { label: 'Pending Messages', value: data?.pending_messages ?? 0 },
  ];

  return (
    <div>
      <h2 className="text-xl font-semibold mb-6">Overview</h2>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4 mb-8">
        {stats.map((s) => <StatCard key={s.label} {...s} />)}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-white rounded-lg border p-4">
          <h3 className="text-sm font-medium text-gray-700 mb-3">Recent Tasks</h3>
          <DataTable
            columns={[
              { key: 'task_id', label: 'ID', render: (r: any) => r.task_id?.slice(0, 8) },
              { key: 'status', label: 'Status' },
              { key: 'created_at', label: 'Created' },
            ]}
            data={data?.recent_tasks ?? []}
          />
        </div>
        <div className="bg-white rounded-lg border p-4">
          <h3 className="text-sm font-medium text-gray-700 mb-3">Recent Approvals</h3>
          <DataTable
            columns={[
              { key: 'approval_id', label: 'ID', render: (r: any) => r.approval_id?.slice(0, 8) },
              { key: 'status', label: 'Status' },
              { key: 'risk_level', label: 'Risk' },
            ]}
            data={data?.recent_approvals ?? []}
          />
        </div>
      </div>
    </div>
  );
}

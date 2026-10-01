import { useQuery } from '@tanstack/react-query';
import api from '../../api/client';
import { useT } from '../../i18n';
import StatCard from '../../components/StatCard';
import LoadingState from '../../components/LoadingState';
import ErrorState from '../../components/ErrorState';
import { PageHeader, WorkerHealthChip } from './PixelKit';

export default function AdminOverviewPage() {
  const t = useT();
  const { data, isLoading, isError } = useQuery({
    queryKey: ['admin/overview'],
    queryFn: () => api.get('/v1/dashboard/admin/overview').then((r) => r.data),
    refetchInterval: 30000,
  });

  if (isLoading) return <LoadingState />;
  if (isError) return <ErrorState message={t('admin.error.loadOverview')} />;

  const stats = [
    { label: t('admin.stat.totalUsers'), value: data?.total_users ?? 0 },
    { label: t('admin.stat.activeUsers'), value: data?.active_users ?? 0 },
    { label: t('admin.stat.disabledUsers'), value: data?.disabled_users ?? 0, variant: 'danger' as const },
    { label: t('admin.stat.totalAgents'), value: data?.total_agents ?? 0 },
    { label: t('admin.stat.onlineAgents'), value: data?.online_agents ?? 0 },
    { label: t('admin.stat.wsConnections'), value: data?.active_ws_connections ?? 0 },
    { label: t('admin.stat.tasks1h'), value: data?.tasks_1h ?? 0 },
    { label: t('admin.stat.tasks24h'), value: data?.tasks_24h ?? 0 },
    { label: t('admin.stat.tasks7d'), value: data?.tasks_7d ?? 0 },
    { label: t('admin.stat.failedTasks'), value: data?.failed_tasks ?? 0, variant: 'danger' as const },
    { label: t('admin.stat.expiredTasks'), value: data?.expired_tasks ?? 0 },
    { label: t('admin.stat.pendingApprovals'), value: data?.pending_approvals ?? 0 },
    { label: t('admin.stat.pendingMessages'), value: data?.pending_messages ?? 0 },
  ];

  return (
    <div>
      <PageHeader title={t('admin.title.overview')} />

      {/* KPI grid: single column under 768px, cockpit density on PC. */}
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-4 xl:grid-cols-5">
        {stats.map((s) => <StatCard key={s.label} {...s} />)}
      </div>

      <div className="mt-6 flex flex-wrap gap-3">
        <WorkerHealthChip label={t('admin.worker.retry')} status={data?.retry_worker_health} />
        <WorkerHealthChip label={t('admin.worker.timeout')} status={data?.timeout_worker_health} />
      </div>
    </div>
  );
}

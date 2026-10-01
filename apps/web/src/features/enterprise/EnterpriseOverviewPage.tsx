import { useQuery } from '@tanstack/react-query';
import api from '../../api/client';
import { useT } from '../../i18n';
import StatCard from '../../components/StatCard';
import LoadingState from '../../components/LoadingState';
import ErrorState from '../../components/ErrorState';
import { PageTitle } from '../connections/pixel-ui';
import { PIXEL_CHIP } from '../../lib/tokens';
import { cn } from '../../lib/utils';

export default function EnterpriseOverviewPage() {
  const t = useT();
  const { data, isLoading, isError } = useQuery({
    queryKey: ['admin/overview'],
    queryFn: () => api.get('/v1/dashboard/admin/overview').then((r) => r.data),
    refetchInterval: 30000,
  });

  if (isLoading) return <LoadingState />;
  if (isError) return <ErrorState message={t('enterprise.overview.error.load')} />;

  const stats = [
    { label: t('enterprise.overview.stat.totalUsers'), value: data?.total_users ?? 0 },
    { label: t('enterprise.overview.stat.activeUsers'), value: data?.active_users ?? 0 },
    { label: t('enterprise.overview.stat.disabledUsers'), value: data?.disabled_users ?? 0, variant: 'danger' as const },
    { label: t('enterprise.overview.stat.totalAgents'), value: data?.total_agents ?? 0 },
    { label: t('enterprise.overview.stat.onlineAgents'), value: data?.online_agents ?? 0 },
    { label: t('enterprise.overview.stat.wsConnections'), value: data?.active_ws_connections ?? 0 },
    { label: t('enterprise.overview.stat.tasks1h'), value: data?.tasks_1h ?? 0 },
    { label: t('enterprise.overview.stat.tasks24h'), value: data?.tasks_24h ?? 0 },
    { label: t('enterprise.overview.stat.tasks7d'), value: data?.tasks_7d ?? 0 },
    { label: t('enterprise.overview.stat.failedTasks'), value: data?.failed_tasks ?? 0, variant: 'danger' as const },
    { label: t('enterprise.overview.stat.expiredTasks'), value: data?.expired_tasks ?? 0 },
    { label: t('enterprise.overview.stat.pendingApprovals'), value: data?.pending_approvals ?? 0 },
    { label: t('enterprise.overview.stat.pendingMessages'), value: data?.pending_messages ?? 0 },
  ];

  // Worker health is a real state, so it uses the LED palette as a
  // solid chip with fixed contrast text (both themes AA).
  const renderWorkerChip = (label: string, health: string | undefined) => {
    const healthy = health === 'ok';
    return (
      <div
        className={cn(
          'inline-flex items-center px-3 py-1 font-pixel text-sm border-2 border-[#191a26]',
          healthy ? PIXEL_CHIP.ok : PIXEL_CHIP.bad,
        )}
      >
        {label}: {health ?? 'unknown'}
      </div>
    );
  };

  return (
    <div>
      <PageTitle>{t('enterprise.overview.title')}</PageTitle>
      <div className="grid grid-cols-1 gap-4 md:grid-cols-3 lg:grid-cols-5">
        {stats.map((s) => (
          <StatCard key={s.label} {...s} />
        ))}
      </div>
      <div className="mt-6 flex flex-col gap-4 sm:flex-row sm:flex-wrap">
        {renderWorkerChip(t('enterprise.overview.worker.retry'), data?.retry_worker_health)}
        {renderWorkerChip(t('enterprise.overview.worker.timeout'), data?.timeout_worker_health)}
      </div>
    </div>
  );
}

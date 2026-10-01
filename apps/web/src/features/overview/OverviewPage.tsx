import { useQuery } from '@tanstack/react-query';
import api from '../../api/client';
import StatCard from '../../components/StatCard';
import DataTable from '../../components/DataTable';
import LoadingState from '../../components/LoadingState';
import ErrorState from '../../components/ErrorState';
import { useT } from '../../i18n';

export default function OverviewPage() {
  const t = useT();
  const { data, isLoading, isError } = useQuery({
    queryKey: ['dashboard/overview'],
    queryFn: () => api.get('/v1/dashboard/overview').then((r) => r.data),
    refetchInterval: 15000,
  });

  if (isLoading) return <LoadingState />;
  if (isError) return <ErrorState message={t('overview.error.load')} />;

  const stats = [
    { label: t('overview.stat.onlineAgents'), value: data?.online_agents ?? 0 },
    { label: t('overview.stat.tasksToday'), value: data?.tasks_today ?? 0 },
    { label: t('overview.stat.failedTasks'), value: data?.failed_tasks ?? 0, variant: 'danger' as const },
    { label: t('overview.stat.pendingApprovals'), value: data?.pending_approvals ?? 0 },
    { label: t('overview.stat.pendingMessages'), value: data?.pending_messages ?? 0 },
  ];

  return (
    <div>
      <h2 className="font-display text-pixel-xl text-pixel-fg mb-6">{t('overview.title')}</h2>
      {/* KPI grid: single column under 768px (mobile rule), stepped pixel panels. */}
      <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-5 gap-4 mb-8">
        {stats.map((s) => <StatCard key={s.label} {...s} />)}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Pixel panel: surface fill + hard 4px line shadow. The inner DataTable
            keeps its own 2px border, so the section itself stays borderless and
            avoids a double frame. */}
        <section className="bg-pixel-surface shadow-pixel-sm">
          <h3 className="px-4 pt-4 pb-3 font-display text-pixel-base uppercase tracking-pixel text-pixel-muted">
            {t('overview.section.recentTasks')}
          </h3>
          <DataTable
            columns={[
              { key: 'task_id', label: t('overview.table.id'), render: (r: any) => <span className="font-mono">{r.task_id?.slice(0, 8)}</span> },
              { key: 'status', label: t('overview.table.status') },
              { key: 'created_at', label: t('overview.table.created'), render: (r: any) => <span className="font-mono">{r.created_at}</span> },
            ]}
            data={data?.recent_tasks ?? []}
          />
        </section>
        <section className="bg-pixel-surface shadow-pixel-sm">
          <h3 className="px-4 pt-4 pb-3 font-display text-pixel-base uppercase tracking-pixel text-pixel-muted">
            {t('overview.section.recentApprovals')}
          </h3>
          <DataTable
            columns={[
              { key: 'approval_id', label: t('overview.table.id'), render: (r: any) => <span className="font-mono">{r.approval_id?.slice(0, 8)}</span> },
              { key: 'status', label: t('overview.table.status') },
              { key: 'risk_level', label: t('overview.table.risk') },
            ]}
            data={data?.recent_approvals ?? []}
          />
        </section>
      </div>
    </div>
  );
}

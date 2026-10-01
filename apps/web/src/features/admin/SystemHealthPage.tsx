import { useQuery } from '@tanstack/react-query';
import { Shield, CheckCircle, XCircle, Server, Box } from 'lucide-react';
import api from '../../api/client';
import { useT } from '../../i18n';
import LoadingState from '../../components/LoadingState';
import ErrorState from '../../components/ErrorState';
import { PageHeader, Panel, WorkerHealthChip } from './PixelKit';

function HealthTile({ status, label }: { status: string; label: string }) {
  const ok = status === 'ok';
  // LED frame carries the real status; the tile body stays a plain pixel
  // panel so label/status text keeps its pre-verified contrast.
  return (
    <div
      className={`flex items-center gap-3 border-2 bg-pixel-surface p-3 ${
        ok ? 'border-pixel-led-green' : 'border-pixel-led-red'
      }`}
    >
      <span
        className={`inline-flex h-10 w-10 shrink-0 items-center justify-center border-2 border-[#191a26] ${
          ok ? 'bg-pixel-led-green' : 'bg-pixel-led-red'
        }`}
        aria-hidden="true"
      >
        {ok ? (
          <CheckCircle className="h-6 w-6 text-[#191a26]" strokeWidth={2} />
        ) : (
          <XCircle className="h-6 w-6 text-[#f4f4fa]" strokeWidth={2} />
        )}
      </span>
      <div className="min-w-0">
        <p className="font-pixel text-pixel-base uppercase tracking-pixel text-pixel-fg">
          {label}
        </p>
        <p className="font-mono text-base text-pixel-muted">{status}</p>
      </div>
    </div>
  );
}

export default function SystemHealthPage() {
  const t = useT();
  const { data, isLoading, isError } = useQuery({
    queryKey: ['admin/system'],
    queryFn: () => api.get('/v1/dashboard/admin/system-health').then((r) => r.data),
    refetchInterval: 10000,
  });

  if (isLoading) return <LoadingState />;
  if (isError) return <ErrorState message={t('admin.error.loadSystemHealth')} />;

  return (
    <div>
      <PageHeader title={t('admin.title.systemHealth')} />

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-4">
        <HealthTile status={data?.api_health || 'down'} label={t('admin.health.tile.api')} />
        <HealthTile status={data?.db_health || 'down'} label={t('admin.health.tile.postgres')} />
        <HealthTile status={data?.redis_health || 'down'} label={t('admin.health.tile.redis')} />
        <HealthTile status={data?.https_wss_staging || 'not_configured'} label={t('admin.health.tile.httpsWss')} />
      </div>

      <div className="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-2">
        <Panel title={t('admin.health.panel.systemInfo')} icon={<Server className="h-4 w-4" strokeWidth={2} />}>
          <dl className="space-y-2">
            <div className="flex justify-between gap-4">
              <dt className="text-base text-pixel-muted">{t('admin.health.field.appVersion')}</dt>
              <dd className="font-mono text-base text-pixel-fg">{data?.app_version || 'unknown'}</dd>
            </div>
            <div className="flex justify-between gap-4">
              <dt className="text-base text-pixel-muted">{t('admin.health.field.migration')}</dt>
              <dd className="font-mono text-base text-pixel-fg">{data?.migration_revision || 'unknown'}</dd>
            </div>
            <div className="flex justify-between gap-4">
              <dt className="text-base text-pixel-muted">{t('admin.health.field.pendingQueue')}</dt>
              <dd className="font-mono text-base text-pixel-fg">{data?.pending_queue_length ?? 0}</dd>
            </div>
          </dl>
        </Panel>

        <Panel title={t('admin.health.panel.workers')} icon={<Box className="h-4 w-4" strokeWidth={2} />}>
          <dl className="space-y-3">
            <div className="flex items-center justify-between gap-4">
              <dt className="text-base text-pixel-muted">{t('admin.worker.retry')}</dt>
              <dd>
                <WorkerHealthChip label="" status={data?.retry_worker_health} />
              </dd>
            </div>
            <div className="flex items-center justify-between gap-4">
              <dt className="text-base text-pixel-muted">{t('admin.worker.timeout')}</dt>
              <dd>
                <WorkerHealthChip label="" status={data?.timeout_worker_health} />
              </dd>
            </div>
          </dl>
        </Panel>
      </div>

      <p className="mt-6 flex items-center gap-2 text-base text-pixel-muted">
        <Shield className="h-4 w-4" strokeWidth={2} /> {t('admin.health.note.noSecrets')}
      </p>
    </div>
  );
}

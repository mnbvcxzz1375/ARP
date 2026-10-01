import { useParams, Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { ArrowLeft } from 'lucide-react';
import api from '../../api/client';
import StatusBadge from '../../components/StatusBadge';
import RiskBadge from '../../components/RiskBadge';
import DataTable from '../../components/DataTable';
import LoadingState from '../../components/LoadingState';
import ErrorState from '../../components/ErrorState';
import EmptyState from '../../components/EmptyState';
import { PIXEL_CHIP, TOUCH_TARGET } from '../../lib/tokens';
import { useFormat, useT } from '../../i18n';

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  // Field labels are body font (VT323), not the display face; values are
  // mono data text at 18px per the pixel type rules.
  return (
    <div>
      <dt className="font-mono text-sm uppercase tracking-pixel text-pixel-muted">{label}</dt>
      <dd className="mt-1 font-mono text-lg text-pixel-fg">{children}</dd>
    </div>
  );
}

function CodeBlock({ content }: { content: string | null | undefined }) {
  if (!content) return <span className="font-mono text-lg text-pixel-muted">-</span>;
  // Terminal well: bg base + 2px pixel step, fg text (12.39:1 both themes).
  return (
    <pre className="mt-1 whitespace-pre-wrap break-all bg-pixel-bg border-2 border-pixel-line p-3 font-mono text-base text-pixel-fg max-h-48 overflow-auto">
      {content}
    </pre>
  );
}

export default function TaskDetailPage() {
  const t = useT();
  const { formatDateTime } = useFormat();
  const { taskId } = useParams<{ taskId: string }>();

  const taskQuery = useQuery({
    queryKey: ['task-detail', taskId],
    queryFn: () => api.get(`/v1/dashboard/tasks/${taskId}`).then((r) => r.data),
    enabled: !!taskId,
  });

  const messagesQuery = useQuery({
    queryKey: ['task-messages', taskId],
    queryFn: () => api.get(`/v1/dashboard/tasks/${taskId}/messages`).then((r) => r.data),
    enabled: !!taskId,
  });

  const progressQuery = useQuery({
    queryKey: ['task-progress', taskId],
    queryFn: () => api.get(`/v1/dashboard/tasks/${taskId}/progress`).then((r) => r.data),
    enabled: !!taskId,
  });

  const deliveryEventsQuery = useQuery({
    queryKey: ['task-delivery-events', taskId],
    queryFn: () => api.get(`/v1/tasks/${taskId}/delivery-events`).then((r) => r.data),
    enabled: !!taskId,
  });

  const routeDecisionsQuery = useQuery({
    queryKey: ['task-route-decisions', taskId],
    queryFn: () => api.get(`/v1/tasks/${taskId}/route-decisions`).then((r) => r.data),
    enabled: !!taskId,
  });

  if (taskQuery.isLoading) return <LoadingState />;
  if (taskQuery.isError) return <ErrorState message={t('tasks.error.loadDetail')} />;

  const task = taskQuery.data;

  return (
    <div>
      <Link
        to="/app/tasks"
        className={`inline-flex items-center gap-2 px-3 mb-4 border-2 border-pixel-line bg-pixel-surface text-pixel-fg font-pixel text-pixel-base hover:bg-pixel-raised ${TOUCH_TARGET}`}
      >
        <ArrowLeft className="h-4 w-4" />
        {t('tasks.action.backToList')}
      </Link>
      <h2 className="font-display text-pixel-xl text-pixel-fg mb-6">
        {t('tasks.page.detailTitle', { taskId: task.task_id?.slice(0, 8) ?? '' })}
      </h2>

      <div className="space-y-6">
        <section className="border-2 border-pixel-line bg-pixel-surface p-4 md:p-6 shadow-pixel-sm">
          <h3 className="font-display text-pixel-base uppercase tracking-pixel text-pixel-muted mb-4">{t('tasks.section.status')}</h3>
          <dl className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <Field label={t('tasks.table.status')}>
              <StatusBadge status={task.status} />
            </Field>
            <Field label={t('tasks.field.deliveryStatus')}>{task.delivery_status}</Field>
            <Field label={t('tasks.field.retryCount')}>{task.retry_count}</Field>
            <Field label={t('tasks.field.created')}>{formatDateTime(task.created_at)}</Field>
            <Field label={t('tasks.field.updated')}>{formatDateTime(task.updated_at)}</Field>
          </dl>
        </section>

        {(task.payload_preview || task.result_preview || task.error_message) && (
          <section className="border-2 border-pixel-line bg-pixel-surface p-4 md:p-6 shadow-pixel-sm">
            <h3 className="font-display text-pixel-base uppercase tracking-pixel text-pixel-muted mb-4">{t('tasks.section.content')}</h3>
            <div className="space-y-4">
              {task.payload_preview && (
                <div>
                  <dt className="font-mono text-sm uppercase tracking-pixel text-pixel-muted">{t('tasks.field.payload')}</dt>
                  <CodeBlock content={task.payload_preview} />
                </div>
              )}
              {task.result_preview && (
                <div>
                  <dt className="font-mono text-sm uppercase tracking-pixel text-pixel-muted mt-3">{t('tasks.field.result')}</dt>
                  <CodeBlock content={task.result_preview} />
                </div>
              )}
              {task.error_message && (
                <div>
                  {/* LED red chip label + solid red well: 5.89:1 both themes. */}
                  <dt className="mt-3">
                    <span className={`inline-flex items-center px-2 py-0.5 font-pixel text-pixel-sm uppercase ${PIXEL_CHIP.bad}`}>
                      {t('tasks.field.error')}
                    </span>
                  </dt>
                  <pre className="mt-1 whitespace-pre-wrap break-all bg-pixel-led-red border-2 border-[#191a26] p-3 font-mono text-base text-[#f4f4fa] max-h-48 overflow-auto">
                    {task.error_message}
                  </pre>
                </div>
              )}
            </div>
          </section>
        )}

        <section className="border-2 border-pixel-line bg-pixel-surface p-4 md:p-6 shadow-pixel-sm">
          <h3 className="font-display text-pixel-base uppercase tracking-pixel text-pixel-muted mb-4">{t('tasks.section.messages')}</h3>
          {messagesQuery.isLoading ? (
            <LoadingState className="p-4" />
          ) : messagesQuery.isError ? (
            <ErrorState message={t('tasks.error.loadMessages')} />
          ) : (
            <DataTable
              columns={[
                { key: 'message_id', label: t('tasks.table.messageId'), render: (r: any) => <span className="font-mono">{r.message_id?.slice(0, 8)}</span> },
                { key: 'type', label: t('tasks.table.type') },
                { key: 'delivery_status', label: t('tasks.table.delivery'), render: (r: any) => <span className="font-mono">{r.delivery_status}</span> },
                { key: 'created_at', label: t('tasks.table.created'), render: (r: any) => <span className="font-mono">{formatDateTime(r.created_at)}</span> },
              ]}
              data={messagesQuery.data?.messages ?? []}
            />
          )}
        </section>

        <section className="border-2 border-pixel-line bg-pixel-surface p-4 md:p-6 shadow-pixel-sm">
          <h3 className="font-display text-pixel-base uppercase tracking-pixel text-pixel-muted mb-4">{t('tasks.section.progress')}</h3>
          {progressQuery.isLoading ? (
            <LoadingState className="p-4" />
          ) : progressQuery.isError ? (
            <ErrorState message={t('tasks.error.loadProgress')} />
          ) : (
            <DataTable
              columns={[
                { key: 'seq', label: t('tasks.table.seq'), render: (r: any) => <span className="font-mono">{r.seq}</span> },
                { key: 'status', label: t('tasks.table.status'), render: (r: any) => <StatusBadge status={r.status} /> },
                { key: 'progress_pct', label: t('tasks.table.percent'), render: (r: any) => <span className="font-mono">{r.progress_pct != null ? `${r.progress_pct}%` : '-'}</span> },
                { key: 'message', label: t('tasks.table.message') },
                { key: 'created_at', label: t('tasks.table.created'), render: (r: any) => <span className="font-mono">{formatDateTime(r.created_at)}</span> },
              ]}
              data={progressQuery.data?.progress ?? []}
            />
          )}
        </section>

        <section className="border-2 border-pixel-line bg-pixel-surface p-4 md:p-6 shadow-pixel-sm">
          <h3 className="font-display text-pixel-base uppercase tracking-pixel text-pixel-muted mb-4">{t('tasks.section.deliveryEvents')}</h3>
          {deliveryEventsQuery.isLoading ? (
            <LoadingState className="p-4" />
          ) : deliveryEventsQuery.isError ? (
            <ErrorState message={t('tasks.error.loadDeliveryEvents')} />
          ) : (deliveryEventsQuery.data?.delivery_events ?? []).length === 0 ? (
            <EmptyState message={t('tasks.empty.noDeliveryEvents')} />
          ) : (
            <DataTable
              columns={[
                {
                  key: 'event_type',
                  label: t('tasks.table.event'),
                  render: (r: any) => <StatusBadge status={r.event_type ?? 'unknown'} />,
                },
                { key: 'route_type', label: t('tasks.table.routeType'), render: (r: any) => r.route_type || '-' },
                {
                  key: 'relay_node_id',
                  label: t('tasks.table.relayNode'),
                  render: (r: any) => <span className="font-mono">{r.relay_node_id?.slice(0, 8) ?? '-'}</span>,
                },
                {
                  key: 'latency_ms',
                  label: t('tasks.table.latency'),
                  render: (r: any) => <span className="font-mono">{r.latency_ms != null ? `${r.latency_ms}` : '-'}</span>,
                },
                {
                  key: 'queue_wait_ms',
                  label: t('tasks.table.queueWait'),
                  render: (r: any) => <span className="font-mono">{r.queue_wait_ms != null ? `${r.queue_wait_ms}` : '-'}</span>,
                },
                {
                  key: 'error_code',
                  label: t('tasks.table.errorCode'),
                  render: (r: any) => r.error_code ? (
                    <span className={`inline-flex items-center px-2 py-0.5 font-mono text-sm ${PIXEL_CHIP.bad}`}>
                      {r.error_code}
                    </span>
                  ) : '-',
                },
                {
                  key: 'created_at',
                  label: t('tasks.table.created'),
                  render: (r: any) => <span className="font-mono">{r.created_at ? formatDateTime(r.created_at) : '-'}</span>,
                },
              ]}
              data={deliveryEventsQuery.data?.delivery_events ?? []}
            />
          )}
        </section>

        <section className="border-2 border-pixel-line bg-pixel-surface p-4 md:p-6 shadow-pixel-sm">
          <h3 className="font-display text-pixel-base uppercase tracking-pixel text-pixel-muted mb-4">{t('tasks.section.routeDecisions')}</h3>
          {routeDecisionsQuery.isLoading ? (
            <LoadingState className="p-4" />
          ) : routeDecisionsQuery.isError ? (
            <ErrorState message={t('tasks.error.loadRouteDecisions')} />
          ) : (routeDecisionsQuery.data?.decisions ?? []).length === 0 ? (
            <EmptyState message={t('tasks.empty.noRouteDecisions')} />
          ) : (
            <DataTable
              columns={[
                { key: 'selected_route_type', label: t('tasks.table.routeType') },
                {
                  key: 'risk_level',
                  label: t('tasks.table.risk'),
                  render: (r: any) => <RiskBadge level={r.risk_level ?? 'low'} />,
                },
                { key: 'fallback_reason', label: t('tasks.table.fallbackReason'), render: (r: any) => r.fallback_reason || '-' },
                {
                  key: 'decision_time_ms',
                  label: t('tasks.table.decisionTime'),
                  render: (r: any) => <span className="font-mono">{r.decision_time_ms != null ? `${r.decision_time_ms}` : '-'}</span>,
                },
                {
                  key: 'shadow_mode',
                  label: t('tasks.table.shadow'),
                  render: (r: any) => (
                    <span className={`inline-flex items-center px-2 py-0.5 text-sm font-pixel ${
                      r.shadow_mode ? PIXEL_CHIP.warn : PIXEL_CHIP.neutral
                    }`}>
                      {r.shadow_mode ? t('tasks.fieldValue.yes') : t('tasks.fieldValue.no')}
                    </span>
                  ),
                },
                {
                  key: 'created_at',
                  label: t('tasks.table.created'),
                  render: (r: any) => <span className="font-mono">{r.created_at ? formatDateTime(r.created_at) : '-'}</span>,
                },
              ]}
              data={routeDecisionsQuery.data?.decisions ?? []}
            />
          )}
        </section>
      </div>
    </div>
  );
}

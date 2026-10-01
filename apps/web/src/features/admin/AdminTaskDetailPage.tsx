import { useParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import api from '../../api/client';
import { useT, useFormat } from '../../i18n';
import StatusBadge from '../../components/StatusBadge';
import LoadingState from '../../components/LoadingState';
import ErrorState from '../../components/ErrorState';
import { PageHeader, Panel, Field, BackLink, CodeBlock, ErrorBlock } from './PixelKit';

export default function AdminTaskDetailPage() {
  const { taskId } = useParams<{ taskId: string }>();
  const t = useT();
  const { formatDateTime } = useFormat();

  const { data, isLoading, isError } = useQuery({
    queryKey: ['admin/task-detail', taskId],
    queryFn: () => api.get(`/v1/dashboard/admin/tasks/${taskId}`).then((r) => r.data),
    enabled: !!taskId,
  });

  if (isLoading) return <LoadingState />;
  if (isError) return <ErrorState message={t('admin.error.loadTaskDetail')} />;

  const task = data;

  return (
    <div>
      <BackLink to="/admin/tasks">{t('admin.back.tasks')}</BackLink>
      <PageHeader title={t('admin.taskDetail.title', { id: task.task_id?.slice(0, 8) })} />

      <div className="space-y-6">
        <Panel title={t('admin.taskDetail.panel.details')}>
          <dl className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <Field label={t('admin.table.owner')}>{task.owner_username}</Field>
            <Field label={t('admin.table.status')}>
              <StatusBadge status={task.status} />
            </Field>
            <Field label={t('admin.taskDetail.field.deliveryStatus')}>{task.delivery_status}</Field>
            <Field label={t('admin.taskDetail.field.retryCount')}>{task.retry_count}</Field>
            <Field label={t('admin.table.created')}>{formatDateTime(task.created_at)}</Field>
            <Field label={t('admin.agentDetail.field.updated')}>{formatDateTime(task.updated_at)}</Field>
          </dl>
        </Panel>

        {(task.payload_preview || task.result_preview || task.error_message) && (
          <Panel title={t('admin.taskDetail.panel.content')}>
            <div className="space-y-4">
              {task.payload_preview && (
                <div>
                  <dt className="font-pixel text-pixel-sm uppercase tracking-pixel text-pixel-muted">{t('admin.taskDetail.field.payload')}</dt>
                  <CodeBlock content={task.payload_preview} />
                </div>
              )}
              {task.result_preview && (
                <div className="mt-4">
                  <dt className="font-pixel text-pixel-sm uppercase tracking-pixel text-pixel-muted">{t('admin.taskDetail.field.result')}</dt>
                  <CodeBlock content={task.result_preview} />
                </div>
              )}
              {task.error_message && (
                <div className="mt-4">
                  <dt className="font-pixel text-pixel-sm uppercase tracking-pixel text-pixel-muted">{t('admin.taskDetail.field.error')}</dt>
                  <ErrorBlock content={task.error_message} />
                </div>
              )}
            </div>
          </Panel>
        )}
      </div>
    </div>
  );
}

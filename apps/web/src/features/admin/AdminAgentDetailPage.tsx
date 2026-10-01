import { useParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import api from '../../api/client';
import { useT, useFormat } from '../../i18n';
import StatusBadge from '../../components/StatusBadge';
import LoadingState from '../../components/LoadingState';
import ErrorState from '../../components/ErrorState';
import { PageHeader, Panel, Field, BackLink, TagChip } from './PixelKit';

export default function AdminAgentDetailPage() {
  const { agentId } = useParams<{ agentId: string }>();
  const t = useT();
  const { formatDateTime } = useFormat();

  const { data, isLoading, isError } = useQuery({
    queryKey: ['admin/agent-detail', agentId],
    queryFn: () => api.get(`/v1/dashboard/admin/agents/${agentId}`).then((r) => r.data),
    enabled: !!agentId,
  });

  if (isLoading) return <LoadingState />;
  if (isError) return <ErrorState message={t('admin.error.loadAgentDetail')} />;

  const agent = data;

  return (
    <div>
      <BackLink to="/admin/agents">{t('admin.back.agents')}</BackLink>
      <PageHeader title={agent.name || agent.agent_number} />

      <div className="space-y-6">
        <Panel title={t('admin.agentDetail.panel.coreIdentity')}>
          <dl className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <Field label={t('admin.table.owner')}>{agent.owner_username}</Field>
            <Field label={t('admin.agentDetail.field.agentNumber')}>{agent.agent_number}</Field>
            <Field label={t('admin.agentDetail.field.name')}>{agent.name}</Field>
            <Field label={t('admin.agentDetail.field.runtime')}>{agent.runtime}</Field>
            <Field label={t('admin.table.status')}>
              <StatusBadge status={agent.status} />
            </Field>
            <Field label={t('admin.agentDetail.field.inboundPolicy')}>{agent.inbound_policy}</Field>
            <Field label={t('admin.agentDetail.field.discoverable')}>{agent.discoverable ? t('admin.value.yes') : t('admin.value.no')}</Field>
            <Field label={t('admin.table.created')}>{formatDateTime(agent.created_at)}</Field>
            <Field label={t('admin.agentDetail.field.updated')}>{formatDateTime(agent.updated_at)}</Field>
            <Field label={t('admin.agents.table.tasks24h')}>{agent.tasks_24h}</Field>
            <Field label={t('admin.agentDetail.field.failedTasks24h')}>{agent.failed_tasks_24h}</Field>
          </dl>
        </Panel>

        <Panel title={t('admin.agentDetail.panel.capabilities')}>
          {agent.capabilities && agent.capabilities.length > 0 ? (
            <div className="flex flex-wrap gap-2">
              {agent.capabilities.map((c: string) => (
                <TagChip key={c}>{c}</TagChip>
              ))}
            </div>
          ) : (
            <p className="text-base text-pixel-muted">{t('admin.agentDetail.text.none')}</p>
          )}
        </Panel>

        <Panel title={t('admin.agentDetail.panel.tokenMetadata')}>
          <dl className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <Field label={t('admin.agentDetail.field.tokenPrefix')}>
              {agent.token_metadata?.prefix ?? '-'}
            </Field>
            <Field label={t('admin.agentDetail.field.tokenCreated')}>
              {agent.token_metadata?.created_at
                ? formatDateTime(agent.token_metadata.created_at)
                : '-'}
            </Field>
            <Field label={t('admin.agentDetail.field.tokenRotated')}>
              {agent.token_metadata?.rotated_at
                ? formatDateTime(agent.token_metadata.rotated_at)
                : t('admin.value.never')}
            </Field>
          </dl>
        </Panel>
      </div>
    </div>
  );
}

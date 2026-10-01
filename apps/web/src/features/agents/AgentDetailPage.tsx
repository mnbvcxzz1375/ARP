import { useParams, Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { ArrowLeft } from 'lucide-react';
import api from '../../api/client';
import StatusBadge from '../../components/StatusBadge';
import LoadingState from '../../components/LoadingState';
import ErrorState from '../../components/ErrorState';
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

export default function AgentDetailPage() {
  const t = useT();
  const { formatDateTime } = useFormat();
  const { agentId } = useParams<{ agentId: string }>();

  const { data, isLoading, isError } = useQuery({
    queryKey: ['agent-detail', agentId],
    queryFn: () => api.get(`/v1/dashboard/agents/${agentId}`).then((r) => r.data),
    enabled: !!agentId,
  });

  if (isLoading) return <LoadingState />;
  if (isError) return <ErrorState message={t('agents.error.loadDetail')} />;

  const agent = data;

  return (
    <div>
      <Link
        to="/app/agents"
        className={`inline-flex items-center gap-2 px-3 mb-4 border-2 border-pixel-line bg-pixel-surface text-pixel-fg font-pixel text-pixel-base hover:bg-pixel-raised ${TOUCH_TARGET}`}
      >
        <ArrowLeft className="h-4 w-4" />
        {t('agents.action.backToList')}
      </Link>
      <h2 className="font-display text-pixel-xl text-pixel-fg mb-6">{agent.name || agent.agent_number}</h2>

      <div className="space-y-6">
        <section className="border-2 border-pixel-line bg-pixel-surface p-4 md:p-6 shadow-pixel-sm">
          <h3 className="font-display text-pixel-base uppercase tracking-pixel text-pixel-muted mb-4">{t('agents.section.coreIdentity')}</h3>
          <dl className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <Field label={t('agents.field.agentNumber')}>{agent.agent_number}</Field>
            <Field label={t('agents.field.name')}>{agent.name}</Field>
            <Field label={t('agents.field.runtime')}>{agent.runtime}</Field>
            <Field label={t('agents.field.status')}>
              <StatusBadge status={agent.status} />
            </Field>
            <Field label={t('agents.field.inboundPolicy')}>{agent.inbound_policy}</Field>
            <Field label={t('agents.field.discoverable')}>{agent.discoverable ? t('agents.fieldValue.yes') : t('agents.fieldValue.no')}</Field>
            <Field label={t('agents.field.created')}>{formatDateTime(agent.created_at)}</Field>
            <Field label={t('agents.field.updated')}>{formatDateTime(agent.updated_at)}</Field>
          </dl>
        </section>

        <section className="border-2 border-pixel-line bg-pixel-surface p-4 md:p-6 shadow-pixel-sm">
          <h3 className="font-display text-pixel-base uppercase tracking-pixel text-pixel-muted mb-4">{t('agents.section.capabilities')}</h3>
          {agent.capabilities && agent.capabilities.length > 0 ? (
            <div className="flex flex-wrap gap-2">
              {agent.capabilities.map((c: string) => (
                // Info chip (accent-2 solid, dark text): 9.32:1 dark /
                // 2.56:1 light (measured; see pixel-ui.tsx header).
                <span
                  key={c}
                  className={`inline-flex items-center px-2 py-0.5 text-sm font-pixel ${PIXEL_CHIP.info}`}
                >
                  {c}
                </span>
              ))}
            </div>
          ) : (
            <p className="text-base text-pixel-muted">{t('agents.empty.noCapabilities')}</p>
          )}
        </section>

        <section className="border-2 border-pixel-line bg-pixel-surface p-4 md:p-6 shadow-pixel-sm">
          <h3 className="font-display text-pixel-base uppercase tracking-pixel text-pixel-muted mb-4">{t('agents.section.tokenMetadata')}</h3>
          <dl className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <Field label={t('agents.field.tokenPrefix')}>
              {agent.token_metadata?.prefix ?? '-'}
            </Field>
            <Field label={t('agents.field.tokenCreated')}>
              {agent.token_metadata?.created_at
                ? formatDateTime(agent.token_metadata.created_at)
                : '-'}
            </Field>
            <Field label={t('agents.field.tokenRotated')}>
              {agent.token_metadata?.rotated_at
                ? formatDateTime(agent.token_metadata.rotated_at)
                : t('agents.fieldValue.never')}
            </Field>
          </dl>
        </section>
      </div>
    </div>
  );
}

import { useT } from '../../i18n';
import { PIXEL_CHIP } from '../../lib/tokens';

export interface SummaryStripData {
  online_agents?: number | null;
  tasks_today?: number | null;
  failed_tasks?: number | null;
  pending_approvals?: number | null;
  pending_messages?: number | null;
}
export interface SummaryStripProps {
  data?: SummaryStripData | null;
  isError?: boolean;
}
function Count({ label, value }: { label: string; value: number }) {
  return (
    <span className="archipelago-summary__count">
      <span className="archipelago-summary__value">{value}</span>
      <span className="archipelago-summary__label">{label}</span>
    </span>
  );
}
export default function SummaryStrip({ data, isError = false }: SummaryStripProps) {
  const t = useT();
  return (
    <div className="archipelago-summary" role="group" aria-label={t('overview.strip.title')}>
      <div className="archipelago-summary__metrics">
        {isError ? <span>{t('overview.strip.error')}</span> : (
          <>
            <Count label={t('overview.stat.onlineAgents')} value={data?.online_agents ?? 0} />
            <Count label={t('overview.stat.tasksToday')} value={data?.tasks_today ?? 0} />
            <span className="archipelago-summary__count">
              <span className={'archipelago-summary__error ' + PIXEL_CHIP.bad}>{data?.failed_tasks ?? 0}</span>
              <span className="archipelago-summary__label">{t('overview.stat.failedTasks')}</span>
            </span>
            <Count label={t('overview.stat.pendingApprovals')} value={data?.pending_approvals ?? 0} />
            <Count label={t('overview.stat.pendingMessages')} value={data?.pending_messages ?? 0} />
          </>
        )}
      </div>
      <span className="archipelago-summary__lag">{t('overview.strip.lag')}</span>
    </div>
  );
}

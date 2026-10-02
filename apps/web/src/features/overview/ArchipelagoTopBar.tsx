import { Link } from 'react-router-dom';
import { ArrowUpRight, BookOpen, List, Map, UserRound } from 'lucide-react';
import { useT } from '../../i18n';
import AgentAvatar from '../../components/pixel/AgentAvatar';

export type OverviewViewMode = 'map' | 'list';
export interface ArchipelagoTopBarProps {
  viewMode: OverviewViewMode;
  onViewModeChange: (mode: OverviewViewMode) => void;
}

export default function ArchipelagoTopBar({ viewMode, onViewModeChange }: ArchipelagoTopBarProps) {
  const t = useT();
  return (
    <header className="archipelago-topbar">
      <div className="archipelago-brand">
        <AgentAvatar seed="agentnet-brand" size={28} name="AgentNet" />
        <span className="archipelago-brand__name">AgentNet</span>
        <span className="archipelago-brand__divider" aria-hidden="true" />
        <span className="archipelago-brand__sub">{t('overview.brand.sub')}</span>
      </div>
      <div className="archipelago-topbar__actions">
        <div className="archipelago-view-toggle" role="group" aria-label={t('overview.viewMode.label')}>
          {(['map', 'list'] as const).map((mode) => {
            const Icon = mode === 'map' ? Map : List;
            return (
              <button
                key={mode}
                type="button"
                aria-pressed={viewMode === mode}
                onClick={() => onViewModeChange(mode)}
              >
                <Icon size={17} aria-hidden="true" />
                {t('overview.viewMode.' + mode)}
              </button>
            );
          })}
        </div>
        <Link
          to="/docs/quickstart"
          className="archipelago-guide"
          title={t('overview.gap.createTask')}
        >
          <BookOpen size={17} aria-hidden="true" />
          <span>{t('overview.action.taskGuide')}</span>
          <ArrowUpRight size={16} aria-hidden="true" />
        </Link>
        <Link to="/app/settings" className="archipelago-account" aria-label={t('overview.action.account')}>
          <UserRound size={18} aria-hidden="true" />
        </Link>
      </div>
    </header>
  );
}

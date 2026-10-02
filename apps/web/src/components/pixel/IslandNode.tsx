import { useT } from '../../i18n';
import { TOUCH_TARGET } from '../../lib/tokens';
import AgentAvatar from './AgentAvatar';
import { activeCount, type TaskCounters } from '../../lib/traffic';

/** Raster terrain and HTML identity share the same bottom-centre anchor.
 * ConnectionLayer uses these metrics to keep routes attached to the sprite. */
export const ISLAND_SPRITE_WIDTH = 232;
export const ISLAND_SPRITE_HEIGHT = 176;
export const ISLAND_NODE_CENTER_OFFSET = ISLAND_SPRITE_HEIGHT / 2;

export interface IslandNodeAgent {
  id: string;
  number?: string | null;
  name?: string | null;
  status?: string | null;
}
export interface IslandNodeSlot { x: number; y: number; }
export interface IslandNodeProps {
  workload?: TaskCounters;
  agent: IslandNodeAgent;
  slot: IslandNodeSlot;
  selected?: boolean;
  index: number;
  total: number;
  onSelect?: (agentId: string) => void;
  tabIndex?: number;
  className?: string;
}
export default function IslandNode({
  agent, slot, selected = false, index, total, onSelect, tabIndex, className, workload,
}: IslandNodeProps) {
  const t = useT();
  const online = (agent.status ?? '').trim().toLowerCase() === 'online';
  const name = agent.name?.trim() || agent.number?.trim() || agent.id;
  const statusText = t(online ? 'common.statusLabel.online' : 'common.statusLabel.offline');
  const label = t('overview.island.label', {
    name, number: agent.number || agent.id, status: statusText, index, total,
  });
  const terrain = index % 2 === 0 ? 'observatory-island' : 'workshop-island';

  return (
    <button
      type="button"
      className={['island-node absolute flex flex-col items-center', TOUCH_TARGET,
        selected ? 'island-node--selected' : '', className].filter(Boolean).join(' ')}
      style={{ left: slot.x + 'px', top: slot.y + 'px', transform: 'translate(-50%, -100%)' }}
      aria-pressed={selected}
      aria-current={selected ? 'step' : undefined}
      aria-label={workload ? label+' · '+t('overview.traffic.count',{active:activeCount(workload),failed:workload.failed_24h}) : label}
      tabIndex={tabIndex}
      onClick={onSelect ? () => onSelect(agent.id) : undefined}
    >
      <span className="island-node__nameplate w-full max-w-full truncate text-center font-pixel text-pixel-fg">{name}</span>
      <span className="sr-only">{agent.number || agent.id}</span>
      <span className="island-node__presence inline-flex items-center gap-[4px] leading-none">
        <span aria-hidden="true" className={'block h-[10px] w-[10px] border-2 border-pixel-bg ' + (online ? 'bg-pixel-led-green' : 'bg-pixel-line')} />
        <span className="font-pixel text-pixel-sm text-pixel-muted">{statusText}</span>
      </span>
      {workload && <span className="island-node__workload">{t('overview.traffic.count',{active:activeCount(workload),failed:workload.failed_24h})}</span>}
      <span className="island-node__figure">
        <img
          className="island-node__terrain"
          src={'/art/archipelago/' + terrain + '.png'}
          alt="" aria-hidden="true" draggable={false}
          width={ISLAND_SPRITE_WIDTH} height={ISLAND_SPRITE_HEIGHT}
        />
        <AgentAvatar seed={agent.number?.trim() || agent.id} size={64} name={name} className="island-node__avatar" />
      </span>
    </button>
  );
}

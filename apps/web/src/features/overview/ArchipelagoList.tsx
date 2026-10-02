import { Link } from 'react-router-dom';
import { useT } from '../../i18n';
import { shortUserId } from '../../lib/utils';
import StatusBadge from '../../components/StatusBadge';
import AgentAvatar from '../../components/pixel/AgentAvatar';
import { TOUCH_TARGET } from '../../lib/tokens';
import { activeCount, type TaskCounters } from '../../lib/traffic';
import type {
  ArchipelagoAgent,
  ArchipelagoPendingConnection,
} from './AgentDetailPanel';

/**
 * ArchipelagoList - the list mode of the overview (the map's sibling).
 *
 * Data: the SAME dashboard/agents query cache as the map (the page passes
 * its visible/own-agent set through) — full paging belongs to the page,
 * this surface renders whatever slice it is given, so the list and the
 * map can never disagree about who exists.
 *
 * Rows (keyboard traversable: real buttons + links in DOM order):
 * - a select button carrying the deterministic avatar, name, agent
 *   number and a status chip (text label, never color-only). Selection
 *   is exposed via aria-pressed plus the accent outline so it does not
 *   rely on color; the stage's roving-tabindex arrow navigation stays a
 *   map-mode concern;
 * - an independent /app/agents/:agentId link for the full agent page.
 *
 * Pending connection requests render below the agent rows as requester
 * number → target agent name. The target name needs the `to_agent_id`
 * field of the connections contract; before that revision lands the row
 * states `list.pending.targetUnknown` instead of guessing an endpoint.
 * In production requesters usually belong to other users (the agents
 * query is owner-scoped), which is exactly why these requests are
 * listed here rather than drawn — the note says so plainly.
 *
 * No query of its own: pure presentation of page-provided props, which
 * also keeps the unit tests synchronous.
 */
export interface ArchipelagoListProps {
  workloadByAgent?: Readonly<Record<string, TaskCounters>>;
  /** Visible agents (same cache as the map stage). */
  agents: ArchipelagoAgent[];
  /** Pending requests scoped to the user's agents. */
  pendingRequests?: ArchipelagoPendingConnection[];
  /** Currently selected agent id (shared with the map selection). */
  selectedId?: string | null;
  /** Select an agent: opens the detail panel / drawer. */
  onSelect?: (agentId: string) => void;
  compact?: boolean;
}

export default function ArchipelagoList({
  agents,
  pendingRequests = [],
  selectedId = null,
  onSelect,
  compact = false,
  workloadByAgent,
}: ArchipelagoListProps) {
  const t = useT();

  // agent_id → agent join for the pending target names; a target beyond
  // the visible slice degrades to its short id, never a placeholder name.
  const byId = new Map<string, ArchipelagoAgent>();
  for (const a of agents) byId.set(a.agent_id, a);

  return (
    <div className="archipelago-list flex min-h-0 flex-1 flex-col bg-pixel-surface">
      <div className="flex h-12 shrink-0 items-center border-b-2 border-pixel-line px-4">
        <h2 className="font-display text-pixel-base uppercase tracking-pixel text-pixel-muted">
          {t('overview.list.title')}
        </h2>
      </div>

      {agents.length === 0 ? (
        <p className="flex min-h-0 flex-1 items-center justify-center p-8 text-center text-base text-pixel-muted">
          {t('overview.list.empty')}
        </p>
      ) : (
        <ul className="min-h-0 flex-1 overflow-y-auto">
          {agents.map((agent) => {
            const selected = agent.agent_id === selectedId;
            return (
              <li
                key={agent.agent_id}
                className="border-b-2 border-pixel-line last:border-b-0"
              >
                <div className="flex items-center gap-3 p-2">
                  {/* Select button: full row reach, 44px touch target,
                      state via aria-pressed + the stepped accent outline
                      (border-l-4 with the pinned nav-active pattern). */}
                  <button
                    type="button"
                    aria-pressed={selected}
                    onClick={() => onSelect?.(agent.agent_id)}
                    className={
                      'flex min-w-0 flex-1 items-center gap-3 border-l-4 px-3 py-2 ' +
                      TOUCH_TARGET +
                      (selected
                        ? ' border-l-[#191a26] bg-pixel-accent text-[#191a26]'
                        : ' border-l-transparent text-pixel-fg hover:bg-pixel-raised')
                    }
                  >
                    <AgentAvatar
                      seed={agent.agent_number ?? agent.agent_id}
                      size={28}
                      name={agent.name}
                    />
                    <span className="min-w-0 flex-1">
                      <span className="block truncate font-display text-pixel-base">
                        {agent.name}
                      </span>
                      <span className="block break-all font-mono text-pixel-sm opacity-80">
                        {agent.agent_number}
                      </span>
                      {workloadByAgent?.[agent.agent_id] && <span className="block font-pixel text-xs opacity-80">
                        {t('overview.traffic.count',{active:activeCount(workloadByAgent[agent.agent_id]),failed:workloadByAgent[agent.agent_id].failed_24h})}
                      </span>}
                    </span>
                    <StatusBadge status={agent.status} />
                  </button>
                  <Link
                    to={`/app/agents/${agent.agent_id}`}
                    aria-label={`${t('overview.detail.action.viewAgent')}: ${agent.name}`}
                    className="inline-flex shrink-0 items-center justify-center border-2 border-pixel-line bg-pixel-surface px-3 py-1 font-pixel text-pixel-sm text-pixel-fg hover:bg-pixel-raised active:translate-y-[2px]"
                  >
                    {t('overview.list.action.view')}
                  </Link>
                </div>
              </li>
            );
          })}
        </ul>
      )}

      {/* Pending connection requests: requester number → target name.
          `to_agent_id` arrives with the contract revision; until then
          the gap is stated, no endpoint is assumed. */}
      <details className="archipelago-pending border-t-2 border-pixel-line p-4" open={!compact}>
        <summary>
          <span className="font-pixel text-pixel-sm text-pixel-muted">{t('overview.list.pending.title')}</span>
          <span className="font-mono text-pixel-sm text-pixel-muted">{pendingRequests.length}</span>
        </summary>
        {pendingRequests.length === 0 ? (
          <p className="text-pixel-sm text-pixel-muted">{t('overview.detail.pending.empty')}</p>
        ) : (
          <>
            <ul className="flex flex-col gap-2">
              {pendingRequests.map((p) => {
                const target =
                  p.to_agent_id != null
                    ? byId.get(p.to_agent_id)?.name ?? shortUserId(p.to_agent_id)
                    : null;
                return (
                  <li
                    key={p.connection_id}
                    className="border-2 border-pixel-line bg-pixel-raised p-2 text-pixel-sm text-pixel-fg"
                  >
                    <span className="break-all font-mono">{p.agent_number}</span>
                    <span className="text-pixel-muted"> → </span>
                    {target ? (
                      <span>{target}</span>
                    ) : (
                      <span className="text-pixel-muted">
                        {t('overview.list.pending.targetUnknown')}
                      </span>
                    )}
                  </li>
                );
              })}
            </ul>
            <p className="mt-2 text-pixel-sm text-pixel-muted">{t('overview.list.pending.note')}</p>
          </>
        )}
      </details>
    </div>
  );
}

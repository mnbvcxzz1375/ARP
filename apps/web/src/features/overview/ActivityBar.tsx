import { Link } from 'react-router-dom';
import { useT, useFormat } from '../../i18n';

/**
 * ActivityBar - the 128px bottom activity bar of the overview.
 *
 * Data source: overview.recent_agent_status_changes — the NARROW audit
 * slice: AuditLog rows whose actor is one of the user's own agents and
 * whose resource_type is 'agent'
 * (apps/api/app/services/dashboard_service.py:245-249). That means
 * actions performed BY the user's own agents (create / update /
 * rotate_token / firewall …), NOT user-initiated audits (actor is the
 * user id) and NOT presence flips. Online/offline state comes from the
 * agents query's Redis presence instead; this bar never renders it.
 *
 * Consequences stated in the UI:
 * - the list can legitimately be empty (an account whose agents never
 *   self-act), and the empty copy explains the narrow scope instead of
 *   pretending nothing ever happened;
 * - at most the newest 3 rows are shown here (the API returns 10; the
 *   "view all" entry goes to /app/agents, the existing agent surface
 *   with the full audit trail behind it).
 *
 * The bar is a plain HTML text layer (no stage scaling, no animation):
 * short localized timestamps (numeric month/day + 2-digit time) never
 * stack vertically into tall columns, and action/resource ids render in
 * the mono face.
 */
export interface ActivityEntry {
  action: string;
  resource_id: string;
  created_at: string;
}

export interface ActivityBarProps {
  /** recent_agent_status_changes rows (already capped at 3 by the
   *  archipelago data hook); undefined = feed not resolved yet. */
  activity?: ActivityEntry[];
  agents?: ReadonlyArray<{ agent_id: string; name: string }>;
}

/** Short, locale-aware timestamp: "3/1, 14:05" style. */
function useShortTime() {
  const { formatDateTime } = useFormat();
  return (iso: string) =>
    formatDateTime(iso, {
      month: 'numeric',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
}

export default function ActivityBar({ activity, agents = [] }: ActivityBarProps) {
  const t = useT();
  const shortTime = useShortTime();
  const latest = (activity ?? []).slice(0, 3);

  return (
    <div
      role="region"
      aria-label={t('overview.activity.title')}
      className="flex min-h-32 flex-col border-t-2 border-pixel-line bg-pixel-surface"
    >
      <div className="flex h-12 shrink-0 items-center justify-between gap-4 border-b-2 border-pixel-line px-4">
        <h2 className="font-display text-pixel-sm uppercase tracking-pixel text-pixel-muted">
          {t('overview.activity.title')}
        </h2>
        <Link
          to="/app/agents"
          className="font-pixel text-pixel-sm text-pixel-fg underline-offset-2 hover:underline"
        >
          {t('overview.activity.viewAll')}
        </Link>
      </div>
      {latest.length === 0 ? (
        // Empty copy: the narrow scope is the reason, not a loading
        // glitch. Honest about "often empty".
        <p className="flex min-h-0 flex-1 items-center px-4 py-3 text-pixel-sm text-pixel-muted">
          {t('overview.activity.empty')}
        </p>
      ) : (
        // min-h-0 + overflow: the page grid row is a fixed 128px; three
        // rows + the header can exceed it, so the list scrolls instead
        // of pushing the stage or overflowing the shell column.
        <ul className="min-h-0 flex-1 overflow-y-auto">
          {latest.map((entry) => (
            <li
              key={`${entry.action}-${entry.resource_id}-${entry.created_at}`}
              className="flex flex-wrap items-baseline gap-x-3 gap-y-1 border-b-2 border-pixel-line px-4 py-2 last:border-b-0"
            >
              <time className="font-mono text-pixel-sm text-pixel-muted">
                {shortTime(entry.created_at)}
              </time>
              <span className="font-pixel text-pixel-sm text-pixel-fg">{entry.action}</span>
              <span className="font-mono text-pixel-sm text-pixel-muted" title={entry.resource_id}>
                {agents.find((agent) => agent.agent_id === entry.resource_id)?.name ?? entry.resource_id}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

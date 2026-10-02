import { Link } from 'react-router-dom';
import { useT, useFormat } from '../../i18n';
import StatusBadge from '../../components/StatusBadge';
import AgentAvatar from '../../components/pixel/AgentAvatar';
import { type TaskCounters } from '../../lib/traffic';

/**
 * AgentDetailPanel - the right 320px detail column of the overview.
 *
 * Scope: the selected island's agent. Shows the AgentListItem fields the
 * dashboard/agents endpoint actually returns (name / agent_number /
 * runtime / status / inbound_policy / discoverable / capabilities /
 * created_at) — `last_seen_at` is deliberately NOT rendered: the
 * production router hardcodes it to None
 * (apps/api/app/routers/dashboard_user.py:100), only the demo layer fills
 * it, so showing it here would be fake data.
 *
 * Related tasks: the page pre-filters the tasks feed's FIRST PAGE
 * (offset=0, limit=50, no cache) to rows involving this agent (newest 5)
 * and pre-joins the endpoint names (agent_id join, demo name fallback).
 * The rows arrive as DetailTaskRow; each carries a DELIVERY_STATUS chip
 * (via StatusBadge, which maps the delivery statuses onto the same
 * PIXEL_CHIP classes as tokens.ts DELIVERY_STATUS, with i18n labels)
 * plus the joined From/To names. Progress is a stated GAP: the tasks
 * list API does not return progress (only the detail sub-resource
 * /progress does), so no percentage is faked.
 *
 * Pending requests: the page pre-filters the requests whose
 * `to_agent_id` matches this agent; the panel renders requester number
 * → this agent's name. A pre-revision connections payload (no
 * `to_agent_id` exposed) yields an empty list here, so the empty copy
 * states BOTH possibilities instead of claiming "there are none" —
 * never fabricate a target (see OverviewPage's pendingForAgent).
 *
 * The panel is pure presentation of props — no queries of its own, so
 * the page (and the unit tests) feeds it exactly the shaped data.
 */

/** Dashboard agent row (GET /v1/dashboard/agents, AgentListItem). */
export interface ArchipelagoAgent {
  agent_id: string;
  agent_number: string;
  name: string;
  runtime: string;
  status: string;
  inbound_policy: string;
  discoverable: boolean;
  capabilities: string[];
  created_at: string;
}

/**
 * Task row pre-joined by the page: names already resolved from the
 * agent_id join (demo: name fallback). Mirrors OverviewPage's
 * DetailTaskRow shape — kept as a local structural interface so the
 * panel does not import the page module (the page imports the panel).
 */
export interface DetailTaskRow {
  task_id: string;
  status: string;
  delivery_status?: string | null;
  created_at: string;
  sender_name?: string | null;
  target_name?: string | null;
}

/** Pending connection row (GET /v1/dashboard/connections, pending_requests).
 *  `to_agent_id` lands with the contract revision; absent = GAP. */
export interface ArchipelagoPendingConnection {
  connection_id: string;
  /** Requester agent number (e.g. AN-XXXX-...). */
  agent_number: string;
  /** Requester agent id (UUID, production contract). The demo layer may
   *  hold a name there; join by agent_id and fall back gracefully. */
  requester_agent: string;
  /** Revision field — target agent id. Missing before the revision. */
  to_agent_id?: string | null;
  /** Backend hardcodes 'unknown' — not displayed. */
  requested_policy?: string | null;
  created_at: string;
}

export interface AgentDetailPanelProps {
  workload?: TaskCounters;
  /** Selected agent; null renders the "nothing selected" prompt. */
  agent: ArchipelagoAgent | null;
  /** Newest ≤5 task rows involving this agent, names pre-joined. */
  tasks?: DetailTaskRow[];
  /** Pending requests pre-filtered to this agent's to_agent_id. */
  pendingRequests?: ArchipelagoPendingConnection[];
  /** DetailDrawer reuses the panel body but renders its own title bar
   *  (with the close button), so the inner header can be suppressed. */
  showHeader?: boolean;
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex min-w-0 flex-col gap-1 border-b-2 border-pixel-line py-2">
      <dt className="text-pixel-sm text-pixel-muted">{label}</dt>
      <dd className="break-words text-base text-pixel-fg">{children}</dd>
    </div>
  );
}

function endpointLabel(value?: string | null): string {
  if (!value) return '—';
  return /^[0-9a-f]{8}-[0-9a-f-]{27}$/i.test(value)
    ? value.slice(0, 8) + '…' + value.slice(-4)
    : value;
}

export default function AgentDetailPanel({
  agent,
  tasks = [],
  pendingRequests = [],
  showHeader = true,
  workload,
}: AgentDetailPanelProps) {
  const t = useT();
  const { formatDateTime } = useFormat();

  if (!agent) {
    return (
      <div
        className="flex h-full min-h-0 flex-col bg-pixel-surface"
        aria-label={t('overview.detail.title')}
      >
        {showHeader ? <PanelHeader title={t('overview.detail.title')} /> : null}
        <div className="flex min-h-0 flex-1 items-center justify-center p-6">
          <p className="text-center text-base text-pixel-muted">
            {t('overview.detail.noneSelected')}
          </p>
        </div>
      </div>
    );
  }

  // Related tasks arrive pre-filtered and pre-joined from the page (the
  // join lives there because the demo payload stores names, production
  // UUIDs); the panel only caps the row count defensively.
  const related = tasks.slice(0, 5);

  return (
    <div
      className="flex h-full min-h-0 flex-col bg-pixel-surface"
      aria-label={t('overview.detail.title')}
    >
      {showHeader ? <PanelHeader title={t('overview.detail.title')} /> : null}

      <div className="min-h-0 flex-1 overflow-y-auto">
        {/* Identity: avatar (deterministic, from agent_number), name,
            number, status chip. The status is a chip with a text label —
            never color-only. */}
        <div className="archipelago-detail-identity">
          <AgentAvatar seed={agent.agent_number ?? agent.agent_id} size={64} name={agent.name} />
          <div className="flex min-w-0 flex-col gap-1">
            <h3 className="break-words font-display text-pixel-base text-pixel-fg">
              {agent.name}
            </h3>
            <span className="break-all font-mono text-pixel-sm text-pixel-muted">
              {agent.agent_number}
            </span>
            <StatusBadge status={agent.status} />
          </div>
          <Link
            to={`/app/agents/${agent.agent_id}`}
            className="archipelago-detail-open font-pixel text-pixel-sm text-pixel-fg"
          >
            {t('overview.detail.action.viewAgent')}
          </Link>
        </div>

        {/* Core fields (last_seen_at intentionally absent: production
            hardcodes None — see file header). */}
        {workload && <div className="archipelago-agent-workload">
          <p>{t('overview.traffic.breakdown',{running:workload.running,queued:workload.queued,awaiting:workload.awaiting_approval,failed:workload.failed_24h})}</p>
          <Link to={'/app/tasks?view=attention&agent_id='+agent.agent_id}>{t('overview.traffic.allTasks')}</Link>
        </div>}
        <dl className="archipelago-detail-fields">
          <Field label={t('overview.detail.field.runtime')}>{agent.runtime}</Field>
          <Field label={t('overview.detail.field.policy')}>{agent.inbound_policy}</Field>
          <Field label={t('overview.detail.field.discoverable')}>
            {agent.discoverable ? t('overview.detail.value.yes') : t('overview.detail.value.no')}
          </Field>
          <Field label={t('overview.detail.field.created')}>
            {formatDateTime(agent.created_at)}
          </Field>
          <Field label={t('overview.detail.field.capabilities')}>
            {agent.capabilities.length > 0 ? (
              <ul className="flex flex-wrap gap-2">
                {agent.capabilities.map((cap) => (
                  <li
                    key={cap}
                    className="border-2 border-pixel-line bg-pixel-raised px-2 py-0.5 font-mono text-pixel-sm text-pixel-fg"
                  >
                    {cap}
                  </li>
                ))}
              </ul>
            ) : (
              <span className="text-pixel-muted">{t('overview.detail.capabilities.empty')}</span>
            )}
          </Field>
        </dl>

        {/* Related tasks: chip + text + per-task detail link. Sender and
            target names come through the agent_id join. */}
        <section className="border-t-2 border-pixel-line p-4">
          <h4 className="mb-2 font-display text-pixel-sm uppercase tracking-pixel text-pixel-muted">
            {t('overview.detail.section.tasks')}
          </h4>
          {related.length === 0 ? (
            <p className="text-pixel-sm text-pixel-muted">{t('overview.detail.task.empty')}</p>
          ) : (
            <ul className="flex flex-col gap-3">
              {related.map((task) => (
                <li key={task.task_id} className="border-2 border-pixel-line bg-pixel-raised p-2">
                  <div className="flex flex-wrap items-center gap-2">
                    <StatusBadge status={task.status} />
                    {task.delivery_status && task.delivery_status!==task.status && <StatusBadge status={task.delivery_status} />}
                    <Link
                      to={`/app/tasks/${task.task_id}`}
                      className="font-pixel text-pixel-sm text-pixel-fg underline-offset-2 hover:underline"
                    >
                      {t('overview.detail.action.viewTask')}
                    </Link>
                  </div>
                  <div className="mt-2 flex flex-col gap-1 text-pixel-sm text-pixel-fg">
                    <span title={task.sender_name ?? undefined}>
                      <span className="text-pixel-muted">{t('overview.detail.task.from')}: </span>
                      {endpointLabel(task.sender_name)}
                    </span>
                    <span title={task.target_name ?? undefined}>
                      <span className="text-pixel-muted">{t('overview.detail.task.to')}: </span>
                      {endpointLabel(task.target_name)}
                    </span>
                  </div>
                </li>
              ))}
            </ul>
          )}
          {/* Scope + gap notes: the check covers only the latest page, and
              progress is deliberately absent (list API has no progress
              field — no faked percentage anywhere). */}
          <p className="mt-3 text-pixel-sm text-pixel-muted">{t('overview.detail.task.scopeNote')}</p>
          <p className="mt-1 text-pixel-sm text-pixel-muted">{t('overview.gap.progress')}</p>
        </section>

        {/* Pending connection requests: requester number → this agent.
            The list is pre-filtered by the page on to_agent_id; an empty
            list may also mean the pre-revision payload hides the target,
            so the empty copy states both — never a fabricated target. */}
        <section className="border-t-2 border-pixel-line p-4">
          <h4 className="mb-2 font-display text-pixel-sm uppercase tracking-pixel text-pixel-muted">
            {t('overview.detail.section.pending')}
          </h4>
          {pendingRequests.length === 0 ? (
            <p className="text-pixel-sm text-pixel-muted">{t('overview.detail.pending.empty')}</p>
          ) : (
            <ul className="flex flex-col gap-2">
              {pendingRequests.map((p) => (
                <li
                  key={p.connection_id}
                  className="border-2 border-pixel-line bg-pixel-raised p-2 text-pixel-sm text-pixel-fg"
                >
                  <span className="break-all font-mono">{p.agent_number}</span>
                  <span className="text-pixel-muted"> → {agent.name}</span>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>
    </div>
  );
}

/** Shared panel heading; DetailDrawer reuses the same title styling by
 *  importing the panel (the drawer renders the panel as its body). */
export function PanelHeader({ title }: { title: string }) {
  return (
    <div className="flex h-12 shrink-0 items-center border-b-2 border-pixel-line px-4">
      <h2 className="font-display text-pixel-base uppercase tracking-pixel text-pixel-fg">
        {title}
      </h2>
    </div>
  );
}

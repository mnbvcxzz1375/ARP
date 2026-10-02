import { useT } from '../../i18n';
import { activeCount, routeKey } from '../../lib/traffic';
import type {
  ArchipelagoMapAgent,
  ArchipelagoMapEdge,
  StagePoint,
} from './ArchipelagoStage';

/**
 * ConnectionLayer - the map's connection lines between islands.
 *
 * Two edge kinds (shapes from useArchipelagoData, joined by agent_id):
 *
 * - `task`    edges: task sender_agent -> target_agent pairs (a REAL task
 *             relationship - 'overview.map.edgeNote' states this is NOT a
 *             live network topology).
 * - `pending` edges: connection requester_agent -> to_agent_id (a REAL
 *             connection request). The hook only emits one when the target
 *             is exposed AND both endpoints are map-visible; a pre-revision
 *             payload (no target) is filtered out here too - it is never
 *             half-drawn, never faked toward the lighthouse or the stage
 *             edge. Production-wise a pending requester usually belongs to
 *             another user, so such edges almost always vanish before this
 *             layer and surface in list/detail instead (the permission
 *             semantics, not a defect).
 *
 * Drawing rules (mapSpec):
 * - an edge is drawn ONLY when BOTH endpoints resolve to a slotted visible
 *   agent (the `points` map is exactly the slotted set);
 * - the two kinds differ by LINE STYLE (solid vs dashed pixel segments) AND
 *   a text label (overview.map.legend.*), never by color alone;
 * - each line carries a hover tooltip (overview.map.tooltip.*) with the
 *   joined endpoint names; the requester's display name joins from its
 *   agent id, `requesterNumber` is only the label fallback.
 *
 * Accessibility: the whole layer is aria-hidden / role=presentation - the
 * semantics travel in the endpoint node labels and the hover tooltips.
 * aria-current is a step-node concept (JourneyMap) and is never used here.
 *
 * Art: 2px strokes on the JourneyMap palette (fg for task routes, accent for
 * connection requests - decorative lines; the kind is carried by the dashed
 * pattern + label, not the hue). SVG coordinates are the same 960x720
 * design space as the stage; the HTML labels sit at the edge midpoints so
 * all business text stays HTML (never baked into sprites).
 */

export interface ConnectionLayerProps {
  focusId?: string | null;
  edges: readonly ArchipelagoMapEdge[];
  /** Slotted visible agents' node centers (agent id -> point). An edge is
   *  drawable exactly when both endpoints are keys in this map. */
  points: ReadonlyMap<string, StagePoint>;
  /** Visible roster for display-name resolution (join by agent_id). */
  roster?: readonly ArchipelagoMapAgent[];
}

/**
 * Filter + dedupe the drawable edges: both endpoints present in the slotted
 * `points` map, and a target present (`to == null` = the pre-revision
 * contract - no line, no assumed endpoint). Deduplicated per
 * (kind, from, to) because many tasks / requests between the same pair
 * would otherwise stack identical lines. Order-preserving (stable) so the
 * stage's packet run and the list mode can rely on it.
 *
 * The data hook already applies the same guarantee; this is the component's
 * own contract guard (a stricter consumer must not produce a half line).
 */
export function filterDrawableEdges(
  edges: readonly ArchipelagoMapEdge[],
  points: ReadonlyMap<string, StagePoint>,
): ArchipelagoMapEdge[] {
  const seen = new Set<string>();
  const drawable: ArchipelagoMapEdge[] = [];
  for (const edge of edges) {
    if (!edge) continue;
    if (edge.to == null) continue; // no target -> never drawn
    if (!points.has(edge.from) || !points.has(edge.to)) continue; // half-visible
    const key = `${edge.kind}:${edge.from}:${edge.to}`;
    if (seen.has(key)) continue;
    seen.add(key);
    drawable.push(edge);
  }
  return drawable;
}

export default function ConnectionLayer({ edges, points, roster, focusId }: ConnectionLayerProps) {
  const t = useT();
  const drawable = filterDrawableEdges(edges, points);

  const nameOf = (agentId: string, fallbackNumber?: string): string => {
    const rosterName = roster?.find((agent) => agent.agent_id === agentId)?.name?.trim();
    if (rosterName) return rosterName;
    if (fallbackNumber) return fallbackNumber;
    return agentId;
  };

  return (
    <>
    <div className="archipelago-connections" aria-hidden="true" role="presentation">
      <svg viewBox="0 0 960 720" width={960} height={720} shapeRendering="crispEdges" className="block">
        {drawable.map((edge) => {
          const from = points.get(edge.from)!;
          const to = points.get(edge.to!)!;
          const pending = edge.kind === 'pending';
          const stroke = pending ? 'var(--pixel-accent-2)' : 'var(--pixel-accent)';
          const baseTooltip = t(
            pending ? 'overview.map.tooltip.pendingEdge' : 'overview.map.tooltip.taskEdge',
            {
              from: nameOf(edge.from, edge.requesterNumber),
              to: nameOf(edge.to!),
            },
          );
          const tooltip = edge.workload ? baseTooltip+' · '+t('overview.traffic.breakdown', {
            running:edge.workload.running,queued:edge.workload.queued,
            awaiting:edge.workload.awaiting_approval,failed:edge.workload.failed_24h,
          }) : baseTooltip;
          return (
            <g key={`${edge.kind}:${edge.from}:${edge.to}`} data-route={routeKey(edge)}
              data-focused={!focusId || edge.from===focusId || edge.to===focusId}>
              {/* Visible 2px line: solid (task route) or dashed pixel
                  segments (connection request). */}
              <line
                x1={from.x}
                y1={from.y}
                x2={to.x}
                y2={to.y}
                stroke={stroke}
                strokeWidth={2}
                strokeDasharray={pending ? '6 4' : undefined}
              />
              {/* Wider transparent hit stroke carries the hover tooltip; it
                  is invisible to screen readers (the layer is hidden). */}
              <line
                className="archipelago-connections__hit"
                x1={from.x}
                y1={from.y}
                x2={to.x}
                y2={to.y}
                stroke="transparent"
                strokeWidth={12}
              >
                <title>{tooltip}</title>
              </line>
            </g>
          );
        })}
      </svg>
      {drawable.map((edge) => {
        const from = points.get(edge.from)!;
        const to = points.get(edge.to!)!;
        const pending = edge.kind === 'pending';
        return (
          <span
            key={`label-${edge.kind}:${edge.from}:${edge.to}`}
            className={
              'archipelago-connections__label font-pixel text-pixel-sm uppercase tracking-pixel ' +
              (pending ? 'text-pixel-accent' : 'text-pixel-fg')
            }
            style={{
              left: Math.round((from.x + to.x) / 2),
              top: Math.round((from.y + to.y) / 2),
            }}
          >
            {pending ? t('overview.map.legend.pendingEdge') : t('overview.map.legend.taskEdge')}
          </span>
        );
      })}
    </div>
    <div className="archipelago-route-counts" role="list" aria-label={t('overview.traffic.routeCounts')}>
      {focusId && drawable.filter(e=>e.workload && (e.from===focusId || e.to===focusId)).slice(0,3).map(e=>{
        const from=points.get(e.from)!; const to=points.get(e.to!)!;
        const dx=to.x-from.x,dy=to.y-from.y,len=Math.hypot(dx,dy)||1;
        return <span role="listitem" aria-label={nameOf(e.from)+' → '+nameOf(e.to!)+': '+t('overview.traffic.breakdown',{running:e.workload!.running,queued:e.workload!.queued,awaiting:e.workload!.awaiting_approval,failed:e.workload!.failed_24h})} key={'count-'+routeKey(e)} className="archipelago-route-badge" title={t('overview.traffic.breakdown',{running:e.workload!.running,queued:e.workload!.queued,awaiting:e.workload!.awaiting_approval,failed:e.workload!.failed_24h})}
          style={{left:from.x+dx*.33+dy/len*20,top:from.y+dy*.33-dx/len*20}}>
          {t('overview.traffic.count',{active:activeCount(e.workload!),failed:e.workload!.failed_24h})}
        </span>;
      })}
    </div>
    </>
  );
}

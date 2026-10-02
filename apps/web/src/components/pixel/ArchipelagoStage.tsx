import { useEffect, useLayoutEffect, useRef, useState } from 'react';
import type { KeyboardEvent as ReactKeyboardEvent } from 'react';
import { useT } from '../../i18n';
import ConnectionLayer, { filterDrawableEdges } from './ConnectionLayer';
import IslandNode, { ISLAND_NODE_CENTER_OFFSET } from './IslandNode';
import MessagePacket from './MessagePacket';
import RelayLighthouse from './RelayLighthouse';
import { activeCount, routeKey, type TaskCounters } from '../../lib/traffic';
import '../../features/overview/archipelago.css';

/**
 * ArchipelagoStage - the overview map canvas / zoom stage.
 *
 * The stage is a fixed 960x720 design space (origin top-left, integer
 * coordinates) absolutely positioned inside an `overflow:hidden` viewport.
 * A ResizeObserver computes `scale = min(cw/960, ch/720)` and centers the
 * stage with a transform, so nodes, connection lines AND click hit areas
 * scale together - the viewport can never push past the shell's
 * `minmax(0, 1fr)` column (the 375px horizontal-overflow guard). The top
 * bar / summary strip / activity bar are HTML layers outside this component
 * and never participate in the scale.
 *
 * Layout (pure layout coordinates - the API carries no positions, and the
 * slots are bound to NO hardcoded identity):
 * - 6 island slots S1..S6 (mapSpec percentages -> integer px below); a slot
 *   is the island sprite's bottom-center anchor. The IslandNode component
 *   (sibling deliverable) self-positions from that anchor with
 *   translate(-50%, -100%); it exports ISLAND_NODE_CENTER_OFFSET so the
 *   edge endpoint ("the node center point above the anchor") is the same
 *   geometry on both sides of the boundary.
 * - the relay lighthouse (pure scene component, sibling deliverable) is
 *   centered at (50%, 48%) = (480, 346) and is never an edge endpoint.
 *
 * z-order (mapSpec: lines under the buildings, labels/actions above):
 * connection lines (z 0) < lighthouse < islands (DOM order) < packets (z 20).
 *
 * Data contract (structural subset of useArchipelagoData's exports, which
 * mirror the backend AgentListItem / the tasks+connections joins): the hook
 * already de-dupes, stably sorts (agent_number dictionary order) and
 * capacity-truncates `visibleAgents`, and only emits edges whose BOTH
 * endpoints sit inside that visible set (a pending requester usually belongs
 * to another user, so such edges land in list/detail, not here). This stage
 * still runs its own drawable-edge guard: the component stays correct when
 * consumed with a less strict edge source.
 *
 * Motion contract (tightened RelayScene `is-live` contract): the host (the
 * overview page) raises `isLive` ONLY on a real change inside the tasks
 * first page (offset=0, limit=50: a new task_id or a delivery-status
 * change) - never on the 15s poll tick and never on the initial load - and
 * clears it again on the packet animationend, which bubbles up through this
 * stage to the host wrapper. Packets run along TASK edges only; a
 * connection request is not a message delivery.
 *
 * Keyboard: the islands are buttons (IslandNode) and arrow keys move the
 * selection to the geometrically nearest slot; the stage owns the roving
 * tabindex (only the selected island - or the first one when nothing is
 * selected - stays in the tab order) and refocuses the newly selected
 * island's button after an arrow move.
 */

/** Stage design space (mapSpec: 960x720, origin top-left). */
export const STAGE_WIDTH = 960;
export const STAGE_HEIGHT = 720;

/** Six island slots: sprite bottom-center anchors (S1..S6). */
export const STAGE_SLOTS: readonly StagePoint[] = [
  { x: 250, y: 282 },
  { x: 705, y: 292 },
  { x: 148, y: 492 },
  { x: 800, y: 508 },
  { x: 330, y: 692 },
  { x: 704, y: 690 },
];

/** Relay lighthouse anchor (50%, 48%) = (480, 346). */
export const LIGHTHOUSE_ANCHOR: StagePoint = { x: 480, y: 346 };

/** How many islands the map can show (S1..S6, mapSpec capacity). */
export const MAX_ISLANDS = 6;

/** A point in the 960x720 design space. */
export interface StagePoint {
  x: number;
  y: number;
}

/**
 * Agent row consumed by the map. Structural subset of useArchipelagoData's
 * `ArchipelagoAgent` (the AgentListItem payload), so the hook's output
 * assigns to it without a cross-layer import.
 */
export interface ArchipelagoMapAgent {
  agent_id: string;
  agent_number?: string | null;
  name?: string | null;
  /** 'online' | 'offline' - dashboard/agents Redis presence. */
  status?: string | null;
}

export type ArchipelagoMapEdgeKind = 'task' | 'pending';

/**
 * One map edge (same shape as useArchipelagoData's `ArchipelagoEdge`).
 * - task:    from = sender agent id, to = target agent id.
 * - pending: from = requester agent id, to = to_agent_id (+ the
 *            requester's agent_number as a display label).
 *
 * `to` stays `string | null` here on purpose: the hook never emits a
 * pre-revision edge anymore, but the layer keeps the "no target -> no line"
 * branch (design option b) so a direct consumer cannot half-draw one.
 */
export interface ArchipelagoMapEdge {
  kind: ArchipelagoMapEdgeKind;
  from: string;
  to: string | null;
  /** Task edges only: the task the relation comes from. */
  taskId?: string;
  /** Pending edges only: the requester's agent_number (label, not a key). */
  requesterNumber?: string;
  /** Pending edges only: identifies the request in list/detail. */
  connectionId?: string;
  workload?: TaskCounters;
  revision?: string;
}

/**
 * Edge endpoint = the node CENTER: the slot anchor lifted by
 * ISLAND_NODE_CENTER_OFFSET (IslandNode's own sprite metric, so the line
 * geometry can never drift from the painted figure).
 */
export function nodeCenterAt(slot: StagePoint): StagePoint {
  return { x: slot.x, y: slot.y - ISLAND_NODE_CENTER_OFFSET };
}

const ARROW_KEYS: Record<string, 'up' | 'down' | 'left' | 'right'> = {
  ArrowUp: 'up',
  ArrowDown: 'down',
  ArrowLeft: 'left',
  ArrowRight: 'right',
};

export interface ArchipelagoStageProps {
  /** Map-visible agents (de-duped, sorted, capacity-truncated by the hook). */
  visibleAgents: readonly ArchipelagoMapAgent[];
  /** Task + pending edges (joined by agent_id). */
  edges?: readonly ArchipelagoMapEdge[];
  selectedId?: string | null;
  onSelect?: (agentId: string) => void;
  /**
   * Raised by the host ONLY on a real first-page tasks change (new
   * task_id or delivery-status change); cleared on the packet
   * animationend that bubbles through this stage to the host wrapper.
   */
  isLive?: boolean;
  /** Stops ambient sea movement when the host's motion preference requires it. */
  reducedMotion?: boolean;
  focusId?: string | null;
  animatedRoutes?: readonly string[];
  workloadByAgent?: Readonly<Record<string, TaskCounters>>;
  /**
   * Optional in-stage "open list mode" entry on the no-connections hint.
   * The overview page currently wires list-mode switching from its own
   * overflow strip, so the entry renders here only when a callback is
   * passed.
   */
  onViewList?: () => void;
  className?: string;
}

export default function ArchipelagoStage({
  visibleAgents,
  edges = [],
  selectedId,
  onSelect,
  isLive = false,
  reducedMotion = false,
  focusId = null, animatedRoutes, workloadByAgent = {},
  onViewList,
  className,
}: ArchipelagoStageProps) {
  const t = useT();
  const viewportRef = useRef<HTMLDivElement>(null);
  const [scale, setScale] = useState(1);
  /** Set by an arrow-key move so the effect below can refocus the island
   *  button that just became selected (the button markup is IslandNode's,
   *  so the focus target is looked up, not referenced). */
  const arrowMove = useRef(false);

  useLayoutEffect(() => {
    const el = viewportRef.current;
    if (!el || typeof ResizeObserver === 'undefined') return;
    const compute = () => {
      const cw = el.clientWidth;
      const ch = el.clientHeight;
      if (cw > 0 && ch > 0) setScale(Math.min(cw / STAGE_WIDTH, ch / STAGE_HEIGHT));
    };
    compute();
    const observer = new ResizeObserver(compute);
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  // Slot assignment mirrors ConnectionLayer: first MAX_ISLANDS agents in
  // the (already stable) input order.
  const slotted = visibleAgents.slice(0, MAX_ISLANDS);
  const points = new Map<string, StagePoint>();
  slotted.forEach((agent, index) => {
    points.set(agent.agent_id, nodeCenterAt(STAGE_SLOTS[index]));
  });

  const drawable = filterDrawableEdges(edges, points);
  const runPackets = drawable.filter((edge) => edge.kind === 'task' && (!edge.workload || activeCount(edge.workload)>0));
  const related = new Set([focusId]);
  drawable.filter(e=>e.from===focusId || e.to===focusId).forEach(e=>{related.add(e.from);related.add(e.to);});

  // Roving tabindex: the selected island (or the first one when nothing is
  // selected) is the tab entry point; the rest are arrow-key reachable.
  const selectionInMap = slotted.some((agent) => agent.agent_id === selectedId);
  const tabIndexFor = (agentId: string, index: number): number =>
    agentId === selectedId || (!selectionInMap && index === 0) ? 0 : -1;

  // Refocus after an arrow move once the re-render marks the new selection.
  useEffect(() => {
    if (!arrowMove.current) return;
    arrowMove.current = false;
    const selected = viewportRef.current?.querySelector(
      'button[aria-pressed="true"]',
    ) as HTMLButtonElement | null;
    selected?.focus();
  }, [selectedId]);

  const onKeyDown = (event: ReactKeyboardEvent<HTMLDivElement>) => {
    const direction = ARROW_KEYS[event.key];
    if (!direction || slotted.length === 0) return;

    // Origin: the selected slot, or the lighthouse anchor when the
    // selection sits outside the slotted set / nothing is selected.
    const currentIndex =
      selectedId != null ? slotted.findIndex((a) => a.agent_id === selectedId) : -1;
    const origin =
      currentIndex >= 0 ? nodeCenterAt(STAGE_SLOTS[currentIndex]) : LIGHTHOUSE_ANCHOR;

    let best: number | null = null;
    let bestDistance = Number.POSITIVE_INFINITY;
    for (let i = 0; i < slotted.length; i += 1) {
      if (i === currentIndex) continue;
      const candidate = nodeCenterAt(STAGE_SLOTS[i]);
      const dx = candidate.x - origin.x;
      const dy = candidate.y - origin.y;
      if (direction === 'left' && dx >= 0) continue;
      if (direction === 'right' && dx <= 0) continue;
      if (direction === 'up' && dy >= 0) continue;
      if (direction === 'down' && dy <= 0) continue;
      // Geometric nearest neighbor, axis-weighted: the pressed axis carries
      // its plain squared delta, the perpendicular axis is doubled, so a
      // slot that merely leans into the direction (pure Euclidean nearest)
      // loses to one that actually lies in that direction.
      const primary = direction === 'left' || direction === 'right' ? dx : dy;
      const secondary = direction === 'left' || direction === 'right' ? dy : dx;
      const distance = primary * primary + 2 * secondary * secondary;
      if (distance < bestDistance) {
        bestDistance = distance;
        best = i;
      }
    }
    if (best === null) return;
    event.preventDefault();
    onSelect?.(slotted[best].agent_id);
    arrowMove.current = true;
  };

  const viewportClass = [
    'archipelago-stage__viewport',
    className,
  ]
    .filter(Boolean)
    .join(' ');

  return (
    <div
      ref={viewportRef}
      role="region"
      aria-label={t('overview.map.label')}
      className={viewportClass}
      data-reduced-motion={reducedMotion}
      onKeyDown={onKeyDown}
    >
      <div className="archipelago-map-caption" aria-hidden="true">
        <span>AGENTNET / {t('overview.brand.sub')}</span>
        <span>{String(slotted.length).padStart(2, '0')} NODES</span>
      </div>
      <p className="archipelago-map-note">{t('overview.map.edgeNote')}</p>
      {/*
        The scaled design space. Everything inside (lines, lighthouse,
        islands, packets) scales with the transform - including the islands'
        click hit areas. The unscaled HTML notice below stays outside this
        transform so it never scales down with the canvas.
      */}
      <div
        className="archipelago-stage"
        style={{
          width: STAGE_WIDTH,
          height: STAGE_HEIGHT,
          left: '50%',
          top: '50%',
          transform: `translate(-50%, -50%) scale(${scale})`,
        }}
      >
        <ConnectionLayer edges={edges} points={points} roster={visibleAgents} focusId={focusId} />

        {/* Relay lighthouse: self-positioning pure scene component. */}
        <RelayLighthouse position={LIGHTHOUSE_ANCHOR} />

        {slotted.map((agent, index) => (
          <IslandNode
            key={agent.agent_id}
            agent={{
              id: agent.agent_id,
              number: agent.agent_number ?? null,
              name: agent.name ?? null,
              status: agent.status ?? null,
            }}
            slot={STAGE_SLOTS[index]}
            selected={agent.agent_id === selectedId}
            index={index + 1}
            total={slotted.length}
            onSelect={onSelect}
            workload={workloadByAgent[agent.agent_id]}
            className={focusId && !related.has(agent.agent_id) ? 'island-node--muted' : undefined}
            tabIndex={tabIndexFor(agent.agent_id, index)}
          />
        ))}

        {/*
          Message packets: one per drawable TASK edge, resting at the target
          node. They never ride a pending edge (a connection request is not
          a message delivery); an edge whose endpoints are not both visible
          has no packet either - the stage draws no half routes.
        */}
        {runPackets.filter(edge=>!focusId || edge.from===focusId || edge.to===focusId).map((edge) => {
          const from = points.get(edge.from);
          const to = edge.to == null ? undefined : points.get(edge.to);
          if (!from || !to) return null;
          return (
            <MessagePacket
              key={`packet-${edge.taskId ?? edge.connectionId ?? `${edge.kind}:${edge.from}:${edge.to}`}`}
              from={from}
              to={to}
              active={animatedRoutes ? animatedRoutes.includes(routeKey(edge)) : isLive}
            />
          );
        })}
      </div>

      {/*
        Stage-level no-connections state (mapSpec): with islands in view but
        no drawable route, the map states the fact and (when the host wires
        the callback) offers the list entry. The capacity overflow entry is
        owned by the page, not this stage.
      */}
      {slotted.length > 0 && drawable.length === 0 && (
        <div
          role="status"
          className="pointer-events-none absolute bottom-3 left-3 right-3 flex flex-col items-start gap-1 border-2 border-pixel-line bg-pixel-surface px-3 py-2 sm:right-auto"
        >
          <span className="font-mono text-xs text-pixel-muted">{t('overview.map.noEdges')}</span>
          <span className="font-mono text-xs text-pixel-muted">{t('overview.map.edgeNote')}</span>
          {onViewList && (
            <button
              type="button"
              onClick={onViewList}
              // pointer-events-auto re-enables hit testing on this button:
              // the hint container is pointer-events-none (it must not steal
              // map clicks) and `pointer-events` is INHERITED, so without
              // this the button would be unreachable by mouse/touch (the
              // hover brightness would not fire either); keyboard Enter
              // works regardless.
              className="pointer-events-auto min-h-[44px] self-start px-2 font-mono text-xs text-pixel-accent-2 underline decoration-2 underline-offset-2 hover:brightness-110"
            >
              {t('overview.map.openList')}
            </button>
          )}
        </div>
      )}
    </div>
  );
}

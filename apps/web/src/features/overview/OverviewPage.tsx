import { useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import { useQuery } from '@tanstack/react-query';
import api from '../../api/client';
import LoadingState from '../../components/LoadingState';
import ErrorState from '../../components/ErrorState';
import EmptyState from '../../components/EmptyState';
import { useT } from '../../i18n';
import { usePreferences } from '../../hooks/usePreferences';
import {
  MAP_CAPACITY,
  useArchipelagoData,
  type ArchipelagoAgent,
  type ArchipelagoStatusChange,
} from './useArchipelagoData';
import ArchipelagoTopBar from './ArchipelagoTopBar';
import SummaryStrip from './SummaryStrip';
import ArchipelagoList from './ArchipelagoList';
import AgentDetailPanel from './AgentDetailPanel';
import ActivityBar from './ActivityBar';
import ArchipelagoStage from '../../components/pixel/ArchipelagoStage';
import DetailDrawer from './DetailDrawer';
import { changedRoutes, type TaskTraffic, type TaskTrafficRoute } from '../../lib/traffic';

/** Personal archipelago: paged stable Agent groups, server traffic totals,
 * selected-Agent priority task samples, and focus-aware bounded packet signals.
 * The sidebar, theme, independent sea motion and keyboard semantics remain shared.
 * All feeds degrade independently; sample rows never substitute aggregate totals.
 */

/** Overview payload (GET /v1/dashboard/overview). The five counters feed
 *  the summary strip; recent_agent_status_changes feeds the activity bar. */
interface OverviewResponse {
  online_agents: number;
  tasks_today: number;
  failed_tasks: number;
  pending_approvals: number;
  pending_messages: number;
  recent_agent_status_changes?: ArchipelagoStatusChange[] | null;
}

export type ViewMode = 'map' | 'list';

/** Breakpoint of the right-hand panel: below it the detail panel drawers. */
const DESKTOP_PANEL_QUERY = '(min-width: 1280px) and (min-height: 700px)';
/** Breakpoint where the compact list is the default and map zoom stops. */
const COMPACT_QUERY = '(max-width: 767px), (max-height: 849px)';

function useMediaQuery(query: string): boolean {
  const [matches, setMatches] = useState(() => {
    if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') return false;
    return window.matchMedia(query).matches;
  });
  useEffect(() => {
    if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') return;
    const mql = window.matchMedia(query);
    setMatches(mql.matches);
    const onChange = (event: MediaQueryListEvent) => setMatches(event.matches);
    if (typeof mql.addEventListener === 'function') {
      mql.addEventListener('change', onChange);
      return () => mql.removeEventListener('change', onChange);
    }
    if (typeof mql.addListener === 'function') {
      mql.addListener(onChange);
      return () => mql.removeListener(onChange);
    }
    return undefined;
  }, [query]);
  return matches;
}

/**
 * Reduced-motion double gate, same rule as StationMaster: the OS media
 * query OR the stored backend preference forces the static terminal
 * rendering. The page does not arm the packet animation under either
 * signal (the motion CSS is the second, independent gate).
 */
function useReducedMotion(): boolean {
  const mediaReduced = useMediaQuery('(prefers-reduced-motion: reduce)');
  const { data: preferences } = usePreferences();
  return mediaReduced || preferences?.reducedMotion === true;
}

/**
 * Task row pre-joined for the detail panel / drawer (AgentDetailPanel's
 * DetailTaskRow contract): names already resolved from the agent_id join.
 */
export interface DetailTaskRow {
  task_id: string;
  status: string;
  delivery_status: string;
  created_at: string;
  sender_name: string;
  target_name: string;
}

export default function OverviewPage() {
  const t = useT();

  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [focusId, setFocusId] = useState<string | null>(null);
  const [groupPage, setGroupPage] = useState(1);
  // ── three independently-degrading feeds ──────────────────────────────
  const overviewQuery = useQuery({
    queryKey: ['dashboard/overview'],
    queryFn: () => api.get<OverviewResponse>('/v1/dashboard/overview').then((r) => r.data),
    refetchInterval: 15000,
  });

  const agentsQuery = useQuery({
    queryKey: ['dashboard/agents', { page: groupPage, page_size: MAP_CAPACITY, order:'oldest' }],
    queryFn: () =>
      api
        .get<{ agents: ArchipelagoAgent[]; total: number }>('/v1/dashboard/agents', {
          params: { page: groupPage, page_size: MAP_CAPACITY, order:'oldest' },
        })
        .then((r) => r.data),
    refetchInterval: 15000,
  });

  const connectionsQuery = useQuery({
    queryKey: ['dashboard/connections'],
    queryFn: () =>
      api
        .get<{
          agents: unknown[];
          pending_requests: Array<{
            connection_id: string;
            agent_number: string;
            requester_agent: string;
            to_agent_id?: string | null;
            requested_policy?: string | null;
            created_at: string;
          }>;
        }>('/v1/dashboard/connections')
        .then((r) => r.data),
    refetchInterval: 15000,
  });

  const trafficIds = (agentsQuery.data?.agents ?? []).map(a=>a.agent_id).sort().join(',');
  const trafficQuery = useQuery({
    queryKey: ['dashboard/task-traffic', trafficIds],
    queryFn: () => api.get<TaskTraffic>('/v1/dashboard/task-traffic', {params:{agent_ids:trafficIds}}).then(r=>r.data),
    enabled: !!trafficIds,
    refetchInterval: 15000,
  });
  const archi = useArchipelagoData({
    traffic: trafficQuery.data, aggregateOnly:true, preserveOrder:true,
    taskView:'attention', selectedAgentId:selectedId,
    agents: agentsQuery.data?.agents,
    pendingRequests: connectionsQuery.data?.pending_requests,
    recentChanges: overviewQuery.data?.recent_agent_status_changes,
  });

  // ── selection + view mode ────────────────────────────────────────────
  const [viewMode, setViewMode] = useState<ViewMode>('map');

  const isDesktopPanel = useMediaQuery(DESKTOP_PANEL_QUERY);
  const isCompact = useMediaQuery(COMPACT_QUERY);

  // <768px defaults to the compact list and never squeezes the whole map
  // down to an unreadable scale (spec rule). A manual pick is kept while
  // the viewport stays compact.
  useEffect(() => {
    if (isCompact) setViewMode('list');
  }, [isCompact]);

  const selectedAgent = useMemo(
    () => archi.sortedAgents.find((a) => a.agent_id === selectedId) ?? null,
    [archi.sortedAgents, selectedId],
  );

  // Wide layouts open a useful inspector immediately. Compact layouts
  // wait for an explicit selection so they do not open a drawer on load.
  const firstAgentId = archi.visibleAgents[0]?.agent_id;
  useEffect(() => {
    if (isDesktopPanel && firstAgentId && !selectedAgent) setSelectedId(firstAgentId);
  }, [isDesktopPanel, firstAgentId, selectedAgent]);

  // Only changed aggregate routes animate; entering another group is a
  // fresh initial snapshot. Decorative packets are capped at three.
  const reducedMotion = useReducedMotion();
  const prevTraffic = useRef<{scope:string;routes:TaskTrafficRoute[]} | null>(null);
  const [animatedRoutes, setAnimatedRoutes] = useState<string[]>([]);
  useEffect(() => {
    if (!trafficQuery.data) return;
    const previous = prevTraffic.current;
    const current = trafficQuery.data.routes;
    prevTraffic.current = {scope:trafficIds,routes:current};
    if (reducedMotion || previous?.scope !== trafficIds) { setAnimatedRoutes([]); return; }
    const changed = changedRoutes(previous.routes, current, focusId);
    if (changed.length) setAnimatedRoutes(changed);
  }, [trafficQuery.data, trafficIds, reducedMotion, focusId]);
  const workloadByAgent = useMemo(()=>Object.fromEntries(
    (trafficQuery.data?.agents ?? []).map(a=>[a.agent_id,a])),[trafficQuery.data]);
  const groupCount = Math.max(1, Math.ceil((agentsQuery.data?.total ?? 0)/MAP_CAPACITY));
  useEffect(()=>{ if (agentsQuery.data && groupPage>groupCount) setGroupPage(groupCount); },[agentsQuery.data,groupPage,groupCount]);
  const changeGroup = (page:number) => {setGroupPage(page);setSelectedId(null);setFocusId(null);setAnimatedRoutes([]);};

  // ── task joins for the detail panel (data binding lives in the page) ──
  // The panel receives pre-joined rows (DetailTaskRow): the agent_id join
  // resolves both endpoints' display names. An endpoint outside the
  // caller's own agents (a task counterpart owned by another user) falls
  // back to its raw value - an id, never an invented identity.
  const byId = useMemo(
    () => new Map(archi.sortedAgents.map((a) => [a.agent_id, a])),
    [archi.sortedAgents],
  );

  const displayName = (value: string | null | undefined): string => {
    if (!value) return '';
    return byId.get(value)?.name ?? value;
  };

  /** Newest ≤5 first-page tasks involving the selected agent. */
  const relatedTasks = useMemo<DetailTaskRow[]>(() => {
    if (!selectedId) return [];
    const rows: DetailTaskRow[] = [];
    for (const task of archi.firstPageTasks ?? []) {
      // Edge endpoints are agent_ids (the demo adapter translates its
      // fixture names at the response boundary); a non-matching endpoint
      // is simply "the other side belongs to another user".
      if (task.sender_agent !== selectedId && task.target_agent !== selectedId) continue;
      rows.push({
        task_id: task.task_id,
        status: task.status,
        delivery_status: task.delivery_status,
        created_at: task.created_at,
        sender_name: displayName(task.sender_agent),
        target_name: displayName(task.target_agent),
      });
      if (rows.length >= 5) break;
    }
    return rows;
  }, [archi.firstPageTasks, byId, selectedId]);

  /** Pending requests pre-filtered to the selected agent's to_agent_id. */
  const pendingForAgent = useMemo(
    () =>
      (connectionsQuery.data?.pending_requests ?? []).filter(
        (request) => request.to_agent_id === selectedId,
      ),
    [connectionsQuery.data?.pending_requests, selectedId],
  );

  const totalAgents = agentsQuery.data?.total ?? archi.sortedAgents.length;

  const handleSelect = (agentId: string) => { setSelectedId(agentId); setFocusId(agentId); };

  // ── the map/list cell: five explicit states (load / error / empty / ──
  // offline-node / no-connection are covered by the stage itself; this
  // cell owns load, error, empty and the overflow entry).
  let content: ReactNode;
  if (agentsQuery.isLoading) {
    content = <LoadingState />;
  } else if (agentsQuery.isError) {
    content = <ErrorState message={t('overview.error.load')} />;
  } else if (archi.sortedAgents.length === 0) {
    content = (
      <EmptyState
        scene="agents"
        action={{ to: '/docs/quickstart', label: t('agents.empty.action.quickstart') }}
      />
    );
  } else if (viewMode === 'list') {
    content = (
      <ArchipelagoList
        agents={archi.sortedAgents}
        workloadByAgent={workloadByAgent}
        compact={isCompact}
        pendingRequests={connectionsQuery.data?.pending_requests ?? []}
        selectedId={selectedId}
        onSelect={handleSelect}
      />
    );
  } else {
    content = (
      <>
        <ArchipelagoStage
          visibleAgents={archi.visibleAgents}
          edges={archi.edges}
          selectedId={selectedId}
          onSelect={handleSelect}
          animatedRoutes={animatedRoutes}
          focusId={focusId}
          workloadByAgent={workloadByAgent}
          reducedMotion={reducedMotion}
          onViewList={() => setViewMode('list')}
        />
      </>
    );
  }

  const showDrawer = !isDesktopPanel && selectedAgent !== null;

  return (
    <div className="archipelago-page">
      {/* Top bar (64px, page-level): brand, map/list toggle, create-task
          gap link, account entry. */}
      <div className="archipelago-header-cell">
        <ArchipelagoTopBar viewMode={viewMode} onViewModeChange={setViewMode} />
      </div>

      {/* Summary strip (64px, col1 row2): one inline text line of the five
          overview counters with the standing lag note. Degrades to a gap
          notice when the overview feed is unavailable. */}
      <div className="archipelago-summary-cell">
        <SummaryStrip data={overviewQuery.data} isError={overviewQuery.isError} />
      </div>

      {/* Map / list area (col1 row3): overflow:hidden stage, the map never
          breaks out of the shell's minmax(0,1fr) column. */}
      <div
        className="archipelago-map-cell"
        onAnimationEnd={() => setAnimatedRoutes([])}
      >
        <div className="archipelago-group-nav">
          <span>{t('overview.map.group',{page:groupPage,pages:groupCount,total:totalAgents})}</span>
          {groupCount>1 && <div>
            <button type="button" disabled={groupPage<=1} onClick={()=>changeGroup(groupPage-1)}>{t('overview.map.previousGroup')}</button>
            <button type="button" disabled={groupPage>=groupCount} onClick={()=>changeGroup(groupPage+1)}>{t('overview.map.nextGroup')}</button>
          </div>}
        </div>
        {viewMode==='map' && <div className="archipelago-focus-bar"><span>{focusId ? t('overview.traffic.focus',{name:selectedAgent?.name ?? ''}) : t('overview.traffic.focusHint')}</span><button type="button" disabled={!focusId} onClick={()=>setFocusId(null)}>{t('overview.traffic.showAll')}</button></div>}
        {content}
        {trafficQuery.isError ? <div className="archipelago-traffic-note">{t('overview.traffic.unavailable')}</div> :
          <details className="archipelago-traffic-note" open={!isCompact}><summary>{t('overview.traffic.scopeTitle')}</summary>{t('overview.traffic.scope')}</details>}
        {/* Per-feed degradation notices (403 / network): the map keeps
            rendering, the affected relation strip says so. */}
        <div className="flex flex-col gap-1 text-xs text-pixel-muted">
          {archi.isTasksError && <span>{t('overview.gap.tasks')}</span>}
          {connectionsQuery.isError && <span>{t('overview.gap.connections')}</span>}
        </div>
      </div>

      {/* Detail panel (col2, rows 2-3; below 1024 it drawers). The panel
          handles the "nothing selected" prompt itself (agent === null). */}
      <aside className="archipelago-inspector">
        <AgentDetailPanel
          agent={selectedAgent}
          workload={selectedId ? workloadByAgent[selectedId] : undefined}
          tasks={relatedTasks}
          pendingRequests={pendingForAgent}
        />
      </aside>

      {/* Activity bar (128px, spans both columns): the narrow agent-audit
          feed, not a general audit log and not an online/offline stream. */}
      <div className="archipelago-activity-cell">
        <ActivityBar activity={archi.recentActivity} agents={archi.sortedAgents} />
      </div>

      {/* <1024 detail drawer: fixed, Escape-closed, focus returns to the
          triggering node. Renders the panel body with the drawer's own
          title bar (the inner panel header is suppressed). */}
      {showDrawer && (
        <DetailDrawer
          open
          onClose={() => setSelectedId(null)}
          title={selectedAgent?.name ?? t('overview.detail.title')}
        >
          <AgentDetailPanel
            agent={selectedAgent}
            workload={selectedId ? workloadByAgent[selectedId] : undefined}
            tasks={relatedTasks}
            pendingRequests={pendingForAgent}
            showHeader={false}
          />
        </DetailDrawer>
      )}
    </div>
  );
}

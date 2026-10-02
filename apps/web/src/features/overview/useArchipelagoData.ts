import { useMemo, useRef } from 'react';
import { stableAgentOrder, type TaskTraffic, type TaskCounters } from '../../lib/traffic';
import { useQuery } from '@tanstack/react-query';
import api from '../../api/client';

/** Data binding for authoritative per-pair workload aggregates.
 * Production uses server traffic totals; priority task rows are a bounded
 * selected-Agent detail sample. Legacy direct consumers can still opt into
 * task-derived relations, while aggregateOnly disables that fallback.
 * No relationship is drawn when either endpoint is outside the map group.
 */

/** Map slot capacity: S1..S6. Beyond it, the stage shows an overflow entry. */
export const MAP_CAPACITY = 6;

/** Tasks feed page size (endpoint cap is 200; 50 is the packet scope). */
export const TASKS_PAGE_LIMIT = 50;

/**
 * Agent row as returned by GET /v1/dashboard/agents (the AgentListItem
 * payload; `last_seen_at` is hardcoded None in production and is not part
 * of the archipelago surfaces).
 */
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
  updated_at: string;
}

/** Task row as returned by GET /v1/dashboard/tasks. */
export interface ArchipelagoTask {
  task_id: string;
  status: string;
  /** Production: agent_id (UUID). Demo: agent name (name-join fallback). */
  sender_agent: string;
  target_agent: string;
  created_at: string;
  updated_at: string;
  delivery_status: string;
}

/**
 * Pending connection request as returned by GET /v1/dashboard/connections.
 * `agent_number` is the REQUESTER's number; `requester_agent` is the
 * requester's agent_id (UUID); `to_agent_id` is the target agent id,
 * exposed by the contract revision (absent on the pre-revision payload).
 */
export interface ArchipelagoPendingRequest {
  connection_id: string;
  agent_number: string;
  requester_agent: string;
  to_agent_id?: string | null;
  requested_policy?: string | null;
  created_at: string;
}

/** Narrow audit row from dashboard/overview.recent_agent_status_changes. */
export interface ArchipelagoStatusChange {
  action: string;
  resource_id: string;
  created_at: string;
}

export type ArchipelagoEdgeKind = 'task' | 'pending';

/**
 * One drawn relation. `from` / `to` are agent ids guaranteed to resolve
 * inside `visibleAgents`; the connection layer must never look up an
 * endpoint itself - if a future field changes, the edge simply drops.
 */
export interface ArchipelagoEdge {
  kind: ArchipelagoEdgeKind;
  from: string;
  to: string;
  /** Task edges only: the task the relation comes from. */
  taskId?: string;
  /** Pending edges only: the requester's agent_number (label, not a key). */
  requesterNumber?: string;
  /** Pending edges only: identifies the request in list/detail. */
  connectionId?: string;
  workload?: TaskCounters;
  revision?: string;
}

export interface ArchipelagoActivity {
  action: string;
  resource_id: string;
  created_at: string;
}

export interface UseArchipelagoDataArgs {
  traffic?: TaskTraffic;
  aggregateOnly?: boolean;
  preserveOrder?: boolean;
  taskView?: 'attention';
  selectedAgentId?: string | null;
  /** Agents from GET /v1/dashboard/agents (undefined while loading). */
  agents?: ReadonlyArray<ArchipelagoAgent> | null;
  /** Pending requests from GET /v1/dashboard/connections. */
  pendingRequests?: ReadonlyArray<ArchipelagoPendingRequest> | null;
  /** recent_agent_status_changes from GET /v1/dashboard/overview; null /
   *  malformed rows are skipped by the normalization below. */
  recentChanges?: ReadonlyArray<ArchipelagoStatusChange | null> | null;
}

export interface UseArchipelagoDataResult {
  /** De-duplicated, sorted, map-capacity-truncated agent list (S1..S6). */
  visibleAgents: ArchipelagoAgent[];
  /** Same derivation without the capacity cut (list mode / counts). */
  sortedAgents: ArchipelagoAgent[];
  /** edges with both endpoints inside `visibleAgents`. */
  edges: ArchipelagoEdge[];
  /** Narrow audit feed, newest first, capped at 3. */
  recentActivity: ArchipelagoActivity[];
  /** Raw current tasks page (message-packet change detection). */
  firstPageTasks: ArchipelagoTask[] | undefined;
  /** True while the first tasks page has not resolved yet. */
  isTasksLoading: boolean;
  /** True when the tasks feed failed (403 / network) - degrade, do not crash. */
  isTasksError: boolean;
}

/**
 * Stable lexicographic ordering (dictionary order on code units, so the
 * result does not wiggle between locales) with an agent_id tiebreak, so
 * the map's slot assignment is reproducible render-to-render.
 */
function compareAgents(a: ArchipelagoAgent, b: ArchipelagoAgent): number {
  if (a.agent_number < b.agent_number) return -1;
  if (a.agent_number > b.agent_number) return 1;
  if (a.agent_id < b.agent_id) return -1;
  if (a.agent_id > b.agent_id) return 1;
  return 0;
}

export function useArchipelagoData({
  agents,
  pendingRequests,
  recentChanges,
  traffic, aggregateOnly = false, preserveOrder = false, taskView, selectedAgentId,
}: UseArchipelagoDataArgs): UseArchipelagoDataResult {
  // The tasks feed must be the FIRST page at a fixed window: the packet
  // semantics is "something changed inside the latest 50", not full
  // traffic. Same key shape as every other dashboard feed so
  // invalidQueries callers hit it uniformly.
  const tasksQuery = useQuery({
    queryKey: ['dashboard/tasks', { offset: 0, limit: TASKS_PAGE_LIMIT, ...(taskView ? {view:taskView,agent_id:selectedAgentId ?? undefined} : {}) }],
    queryFn: () =>
      api
        .get<{ tasks: ArchipelagoTask[]; total: number; offset: number; limit: number }>(
          '/v1/dashboard/tasks',
          { params: { offset: 0, limit: TASKS_PAGE_LIMIT, ...(taskView ? {view:taskView,agent_id:selectedAgentId ?? undefined} : {}) } },
        )
        .then((r) => r.data),
    refetchInterval: 15000,
  });

  const orderRef = useRef<string[]>([]);
  const sortedAgents = useMemo<ArchipelagoAgent[]>(() => {
    const seen = new Set<string>();
    const out: ArchipelagoAgent[] = [];
    for (const agent of agents ?? []) {
      if (!agent || !agent.agent_id || seen.has(agent.agent_id)) continue;
      seen.add(agent.agent_id);
      out.push(agent);
    }
    if (preserveOrder) {
      orderRef.current = stableAgentOrder(orderRef.current, out.map(a=>a.agent_id));
      const index=new Map(orderRef.current.map((id,i)=>[id,i]));
      out.sort((a,b)=>index.get(a.agent_id)!-index.get(b.agent_id)!);
    } else out.sort(compareAgents);
    return out;
  }, [agents, preserveOrder]);

  const visibleAgents = useMemo(
    () => sortedAgents.slice(0, MAP_CAPACITY),
    [sortedAgents],
  );

  const edges = useMemo<ArchipelagoEdge[]>(() => {
    // One join rule for every feed: agent_id equality. A value that is not
    // one of the caller's own agents (the production norm for a pending
    // requester, or a task counterpart owned by another user) simply does
    // not resolve - never half-drawn, never guessed.
    const known = new Set<string>(sortedAgents.map((a) => a.agent_id));
    const resolve = (value: string | null | undefined): string | undefined => {
      if (!value) return undefined;
      return known.has(value) ? value : undefined;
    };

    // Only edges whose BOTH endpoints sit in the map-visible (capacity
    // cut) set are emitted. A requester outside the caller's own agents
    // (the production norm for pending requests) therefore never produces
    // an edge here - the request belongs to list/detail.
    const visibleIds = new Set(visibleAgents.map((a) => a.agent_id));
    const isDrawable = (id: string | undefined): id is string =>
      typeof id === 'string' && visibleIds.has(id);

    const out: ArchipelagoEdge[] = [];

    if (traffic) {
      for (const route of traffic.routes) {
        if (isDrawable(route.from) && isDrawable(route.to) && route.from !== route.to)
          out.push({kind:'task',from:route.from,to:route.to,workload:route,revision:route.revision});
      }
    }

    for (const task of !traffic && !aggregateOnly ? tasksQuery.data?.tasks ?? [] : []) {
      const from = resolve(task.sender_agent);
      const to = resolve(task.target_agent);
      if (!isDrawable(from) || !isDrawable(to)) continue;
      // A self-task (sender === target) is a loop, not a relation: drop it
      // rather than draw a zero-length stub.
      if (from === to) continue;
      out.push({ kind: 'task', from, to, taskId: task.task_id });
    }

    for (const request of pendingRequests ?? []) {
      if (!request || !request.requester_agent) continue;
      // Contract fallback (pre-revision payload): NO to_agent_id means no
      // known target. Never invent one - skip the edge entirely and let
      // the list/detail surfaces present the request with what exists
      // (requester number + a "target not exposed" gap notice).
      if (!request.to_agent_id) continue;
      const from = resolve(request.requester_agent);
      const to = resolve(request.to_agent_id);
      if (!isDrawable(from) || !isDrawable(to)) continue;
      if (from === to) continue;
      out.push({
        kind: 'pending',
        from,
        to,
        requesterNumber: request.agent_number,
        connectionId: request.connection_id,
      });
    }

    return out;
  }, [tasksQuery.data?.tasks, pendingRequests, visibleAgents, sortedAgents, traffic, aggregateOnly]);

  const recentActivity = useMemo<ArchipelagoActivity[]>(() => {
    const rows: ArchipelagoStatusChange[] = [];
    for (const change of recentChanges ?? []) {
      if (!change || typeof change.action !== 'string') continue;
      rows.push({
        action: change.action,
        resource_id: change.resource_id ?? '',
        created_at: change.created_at ?? '',
      });
    }
    // Newest first (the overview payload is already newest-first; the sort
    // keeps the contract explicit for list rendering).
    rows.sort((a, b) => (a.created_at < b.created_at ? 1 : a.created_at > b.created_at ? -1 : 0));
    return rows.slice(0, 3);
  }, [recentChanges]);

  return {
    visibleAgents,
    sortedAgents,
    edges,
    recentActivity,
    firstPageTasks: tasksQuery.data?.tasks,
    isTasksLoading: tasksQuery.isLoading,
    isTasksError: tasksQuery.isError,
  };
}

export default useArchipelagoData;

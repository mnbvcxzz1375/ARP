export interface TaskCounters {
  running: number;
  queued: number;
  awaiting_approval: number;
  failed_24h: number;
}
export interface TaskTrafficRoute extends TaskCounters {
  from: string;
  to: string;
  revision: string;
}
export interface TaskTraffic {
  agents: Array<TaskCounters & { agent_id: string }>;
  routes: TaskTrafficRoute[];
  failure_window_hours: number;
  generated_at: string;
}
export const routeKey = (r: {from: string; to?: string | null}) => r.from + ':' + r.to;
export const activeCount = (r: TaskCounters) => r.running + r.queued + r.awaiting_approval;
export function changedRoutes(previous: readonly TaskTrafficRoute[] | null,
  current: readonly TaskTrafficRoute[], focusId?: string | null): string[] {
  if (previous === null) return [];
  const before = new Map(previous.map(r => [routeKey(r), JSON.stringify(r)]));
  return current.filter(r => activeCount(r) > 0 &&
    (!focusId || r.from === focusId || r.to === focusId) &&
    before.get(routeKey(r)) !== JSON.stringify(r)).slice(0, 3).map(routeKey);
}
export function stableAgentOrder(previous: readonly string[], current: readonly string[]): string[] {
  const present = new Set(current);
  const kept = previous.filter(id => present.has(id));
  const known = new Set(kept);
  return [...kept, ...current.filter(id => !known.has(id))];
}

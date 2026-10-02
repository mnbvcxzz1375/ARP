import { describe, it, expect, beforeEach } from 'vitest';
import { demoApi } from '../demoAdapter';
import { getDemoStore, resetDemoStore, resetDemoSession } from '../demoStore';
import { personaById } from '../personas';

/**
 * Pins the archipelago-related demo contract changes:
 * - pending_requests carry `to_agent_id` (target agent id) and a
 *   `requester_agent` UUID (agent_id口径, not a name - the demo used to
 *   store the requester's NAME, which broke the hook's agent_id join);
 * - the typical pending requester is an agent owned by ANOTHER user
 *   (demo_manager), mirroring production visibility: dashboard/agents only
 *   returns the caller's own agents, so such a request renders in
 *   list/detail, never as a map edge;
 * - one self-connect pending row exercises the rare drawable path and is
 *   annotated as rare in the fixture;
 * - overview's recent_agent_status_changes mirrors the production narrow
 *   audit filter (agent actors + resource_type 'agent' only), so the
 *   activity bar never shows user-initiated audits as status changes;
 * - /connections scopes pending requests to the caller's own agents as
 *   targets, like the backend's to_agent_id IN ds.user.agents.
 */

interface PendingRow {
  connection_id: string;
  agent_number: string;
  requester_agent: string;
  to_agent_id: string;
  requested_policy: string;
  created_at: string;
}

it('aggregates old active traffic beyond the latest task page and keeps external routes private', async () => {
  const persona = personaById('personal');
  await demoApi.post('/v1/dashboard/auth/login', { username: persona.username, api_key: persona.apiKey });
  const agents = (await demoApi.get('/v1/dashboard/agents')).data as { agents: {agent_id:string; name:string}[] };
  const [a,b] = agents.agents;
  const store = getDemoStore();
  const base = store.world.tasks[0];
  store.world.tasks.push(...Array.from({length:65}, (_,i)=>({...base, task_id:'old-'+i,
    sender_agent:a.name, target_agent:b.name, status:'running', created_at:'2020-01-01T00:00:00Z'})));
  const result = (await demoApi.get('/v1/dashboard/task-traffic', {params:{agent_ids:a.agent_id+','+b.agent_id}})).data as
    {routes:{from:string;to:string;running:number}[]};
  expect(result.routes.find(r=>r.from===a.agent_id && r.to===b.agent_id)?.running).toBeGreaterThanOrEqual(65);
  const filtered = (await demoApi.get('/v1/dashboard/tasks', {params:{view:'active',agent_id:b.agent_id, search:'old-',limit:20}})).data as {total:number;tasks:{status:string}[]};
  expect(filtered.total).toBe(65);
  expect(filtered.tasks).toHaveLength(20);
  expect(filtered.tasks.every(t=>t.status==='running')).toBe(true);
});

interface ConnectionsResponse {
  agents: { agent_id: string; pending_requests: number }[];
  pending_requests: PendingRow[];
}

interface OverviewResponse {
  online_agents: number;
  pending_messages: number;
  recent_agent_status_changes: { action: string; resource_id: string; created_at: string }[];
}

function login(persona: 'super_admin' | 'org_manager' | 'personal') {
  const p = personaById(persona);
  return demoApi.post('/v1/dashboard/auth/login', { username: p.username, api_key: p.apiKey });
}

async function get(url: string, params?: Record<string, unknown>) {
  const r = await demoApi.get(url, params ? { params } : undefined);
  return r.data;
}

/** The two fixture pending connection ids (see fixtures.ts). */
const SELF_CONNECT = 'c1000001-0000-4000-8000-000000000001';
const EXTERNAL = 'c1000001-0000-4000-8000-000000000002';

beforeEach(() => {
  resetDemoStore();
  resetDemoSession();
});

describe('demo connections contract (archipelago)', () => {
  it('exposes to_agent_id and UUID requester_agent on every pending row', async () => {
    await login('personal');
    const data = (await get('/v1/dashboard/connections')) as ConnectionsResponse;
    expect(data.pending_requests).toHaveLength(2);
    for (const row of data.pending_requests) {
      expect(row.to_agent_id).toBeTruthy();
      // agent_id口径: UUID-shaped requester ids, never display names.
      expect(row.requester_agent).toMatch(/^[0-9a-f]{8}-[0-9a-f]{4}-/);
    }
  });

  it('scopes pending requests to the caller\'s own agents as targets', async () => {
    await login('personal');
    const data = (await get('/v1/dashboard/connections')) as ConnectionsResponse;
    const ownIds = new Set(data.agents.map((a) => a.agent_id));
    for (const row of data.pending_requests) {
      expect(ownIds.has(row.to_agent_id)).toBe(true);
    }
    // The pending counts per agent row agree with the pending list.
    const counted = data.agents
      .filter((a) => a.pending_requests > 0)
      .map((a) => a.agent_id)
      .sort();
    const listed = data.pending_requests.map((r) => r.to_agent_id).sort();
    expect(counted).toEqual(listed);
  });

  it('keeps the typical requester external and the self-connect row rare', async () => {
    await login('personal');
    const agents = ((await get('/v1/dashboard/agents', { params: { page: 1, page_size: 50 } })) as {
      agents: { agent_id: string; name: string }[];
    }).agents;
    const ownIds = new Set(agents.map((a) => a.agent_id));
    const data = (await get('/v1/dashboard/connections')) as ConnectionsResponse;

    const self = data.pending_requests.find((r) => r.connection_id === SELF_CONNECT)!;
    expect(self).toBeTruthy();
    // Rare drawable path: both endpoints are the caller's own agents.
    expect(ownIds.has(self.requester_agent)).toBe(true);
    expect(ownIds.has(self.to_agent_id)).toBe(true);

    const external = data.pending_requests.find((r) => r.connection_id === EXTERNAL)!;
    expect(external).toBeTruthy();
    // The production norm: the requester belongs to another user, so the
    // map must not draw this edge - list/detail presents it instead.
    expect(ownIds.has(external.requester_agent)).toBe(false);
    expect(ownIds.has(external.to_agent_id)).toBe(true);
    // agent_number is the requester's number (requester side, not target).
    const requester = agents.find((a) => a.agent_id === external.requester_agent);
    expect(requester).toBeUndefined();
  });

  it('mirrors the narrow audit filter in recent_agent_status_changes', async () => {
    await login('personal');
    const agents = ((await get('/v1/dashboard/agents', { params: { page: 1, page_size: 50 } })) as {
      agents: { agent_id: string }[];
    }).agents;
    const ownIds = new Set(agents.map((a) => a.agent_id));
    const overview = (await get('/v1/dashboard/overview')) as OverviewResponse;
    expect(overview.recent_agent_status_changes.length).toBeGreaterThan(0);
    for (const change of overview.recent_agent_status_changes) {
      // Agent-actor audits only (ws.connected / ws.disconnected); no
      // user/admin rows leak into the "agent status" feed.
      expect(ownIds.has(change.resource_id)).toBe(true);
      expect(['ws.connected', 'ws.disconnected']).toContain(change.action);
    }
    // pending_messages counts requests targeting the caller's agents.
    expect(overview.pending_messages).toBe(2);
  });

  it('keeps every pending row visible to super_admin (all agents visible)', async () => {
    await login('super_admin');
    const data = (await get('/v1/dashboard/connections')) as ConnectionsResponse;
    expect(data.pending_requests).toHaveLength(2);
  });

  it('returns task endpoints as agent_id UUIDs (unified join口径)', async () => {
    await login('personal');
    const agents = ((await get('/v1/dashboard/agents', { params: { page: 1, page_size: 50 } })) as {
      agents: { agent_id: string }[];
    }).agents;
    const ownIds = new Set(agents.map((a) => a.agent_id));
    const tasks = (await get('/v1/dashboard/tasks', { params: { offset: 0, limit: 50 } })) as {
      tasks: { task_id: string; sender_agent: string; target_agent: string }[];
    };
    expect(tasks.tasks.length).toBeGreaterThan(0);
    // Every endpoint is either one of the caller's own agent ids (the
    // visible side) or a value the join cannot resolve (the counterpart
    // belongs to another user) - never a bare display name, which used to
    // break the archipelago hook's agent_id join in demo mode.
    for (const task of tasks.tasks) {
      expect(task.sender_agent).toMatch(/^[0-9a-f]{8}-[0-9a-f]{4}-/);
      expect(task.target_agent).toMatch(/^[0-9a-f]{8}-[0-9a-f]{4}-/);
    }
    const visible = tasks.tasks.filter(
      (t) => ownIds.has(t.sender_agent) || ownIds.has(t.target_agent),
    );
    expect(visible.length).toBeGreaterThan(0);
  });
});


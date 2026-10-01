import { describe, it, expect, beforeEach } from 'vitest';
import { demoApi } from '../demoAdapter';
import { createDemoWorld } from '../fixtures';
import { getDemoStore, resetDemoStore, resetDemoSession } from '../demoStore';
import { personaById } from '../personas';

/**
 * Demo mode regression coverage: pins the fixture world + adapter so a
 * shape change in a response silently breaks the offline demo.
 *
 * The endpoints listed here are exactly the ones the console pages call
 * (see the queryFns in the feature pages); assertions check the fields
 * each page reads, not the full backend response model.
 */

function login(persona: 'super_admin' | 'org_manager' | 'personal') {
  const p = personaById(persona);
  return demoApi.post('/v1/dashboard/auth/login', { username: p.username, api_key: p.apiKey });
}

async function get(url: string, params?: Record<string, unknown>) {
  const r = await demoApi.get(url, params ? { params } : undefined);
  return r.data;
}

async function fail(url: string) {
  await expect(demoApi.get(url)).rejects.toMatchObject({
    response: { data: { detail: expect.any(String) } },
  });
}

beforeEach(() => {
  resetDemoStore();
  resetDemoSession();
});

describe('demo auth', () => {
  it('logs in as the persona matching the username and returns its session', async () => {
    await login('super_admin');
    const me = (await get('/v1/dashboard/auth/me')) as { role: string; permissions: string[]; step_up_until: string | null };
    expect(me.role).toBe('super_admin');
    expect(me.permissions).toContain('super_admin:write');
    expect(me.step_up_until).toBeTruthy();
  });

  it('defaults unknown usernames to the personal persona', async () => {
    await demoApi.post('/v1/dashboard/auth/login', { username: 'someone-else', api_key: 'x' });
    const me = (await get('/v1/dashboard/auth/me')) as { username: string; role: string };
    expect(me.username).toBe('demo_user');
    expect(me.role).toBe('user');
  });

  it('rejects reads before login', async () => {
    await fail('/v1/dashboard/overview');
  });

  it('logout clears the session', async () => {
    await login('personal');
    await demoApi.post('/v1/dashboard/auth/logout');
    await fail('/v1/dashboard/overview');
  });

  it('step-up and profile patch work', async () => {
    await login('super_admin');
    await demoApi.post('/v1/dashboard/auth/step-up', { api_key: 'x' });
    const r = await demoApi.patch('/v1/dashboard/auth/me/profile', { username: 'renamed' });
    expect((r.data as { username: string }).username).toBe('renamed');
  });
});

describe('demo GET surface (page contracts)', () => {
  beforeEach(async () => {
    await login('super_admin');
  });

  it('dashboard overview: KPIs derived from the fixture world', async () => {
    const o = (await get('/v1/dashboard/overview')) as Record<string, unknown>;
    expect(o.online_agents).toBe(5);
    expect(o.failed_tasks).toBeGreaterThan(0);
    expect(Array.isArray(o.recent_tasks)).toBe(true);
    expect(Array.isArray(o.recent_approvals)).toBe(true);
  });

  it('agents list paginates and filters', async () => {
    const page1 = (await get('/v1/dashboard/agents', { page: 1, page_size: 2 })) as {
      agents: unknown[]; total: number; offset: number; limit: number;
    };
    expect(page1.agents).toHaveLength(2);
    expect(page1.total).toBe(8);
    expect(page1.offset).toBe(1);
    const online = (await get('/v1/dashboard/agents', { page: 1, page_size: 20, status_filter: 'online' })) as {
      agents: { status: string }[];
    };
    expect(online.agents.every((a) => a.status === 'online')).toBe(true);
  });

  it('agent detail carries token_metadata', async () => {
    const agent = getDemoStore().world.agents[0];
    const d = (await get(`/v1/dashboard/agents/${agent.agent_id}`)) as {
      token_metadata: { prefix: string };
    };
    expect(d.token_metadata.prefix).toBe(agent.token_prefix);
  });

  it('tasks list, messages, progress, delivery events, route decisions', async () => {
    const tasks = (await get('/v1/dashboard/tasks', { offset: 0, limit: 20 })) as {
      tasks: { task_id: string }[]; total: number;
    };
    expect(tasks.total).toBeGreaterThan(0);
    const id = tasks.tasks[0].task_id;
    expect((await get(`/v1/dashboard/tasks/${id}`)) as { task_id: string }).toMatchObject({ task_id: id });
    const msgs = (await get(`/v1/dashboard/tasks/${id}/messages`)) as { messages: unknown[] };
    expect(msgs.messages.length).toBeGreaterThan(0);
    const prog = (await get(`/v1/dashboard/tasks/${id}/progress`)) as { progress: unknown[] };
    expect(prog.progress.length).toBeGreaterThan(0);
    const dv = (await get(`/v1/tasks/${id}/delivery-events`)) as { delivery_events: unknown[] };
    expect(dv.delivery_events.length).toBeGreaterThan(0);
    expect((await get(`/v1/tasks/${id}/route-decisions`)) as object).toBeInstanceOf(Object);
  });

  it('approvals, connections, api keys', async () => {
    expect(((await get('/v1/dashboard/approvals')) as { approvals: unknown[] }).approvals.length).toBeGreaterThan(0);
    expect(((await get('/v1/dashboard/connections')) as { agents: unknown[]; pending_requests: unknown[] }).agents.length).toBeGreaterThan(0);
    expect(((await get('/v1/dashboard/api-keys')) as { api_keys: unknown[]; total: number }).total).toBe(1);
  });

  it('admin overview/users/agents/tasks/audit/system-health', async () => {
    expect(((await get('/v1/dashboard/admin/overview')) as { total_users: number }).total_users).toBe(4);
    expect(((await get('/v1/dashboard/admin/users')) as { users: unknown[] }).users.length).toBe(4);
    expect(((await get('/v1/dashboard/admin/agents')) as { agents: unknown[] }).agents.length).toBe(8);
    expect(((await get('/v1/dashboard/admin/tasks')) as { tasks: unknown[] }).tasks.length).toBeGreaterThan(0);
    expect(((await get('/v1/dashboard/admin/audit-logs')) as { audit_logs: unknown[] }).audit_logs.length).toBe(8);
    const h = (await get('/v1/dashboard/admin/system-health')) as { db_health: string; migration_revision: string };
    expect(h.db_health).toBe('healthy');
    expect(h.migration_revision).toBe('0030');
  });

  it('access requests, network scopes/zones', async () => {
    expect(((await get('/v1/dashboard/admin/access-requests')) as { access_requests: unknown[] }).access_requests.length).toBe(2);
    expect(((await get('/v1/dashboard/admin/network/scopes')) as { scopes: unknown[] }).scopes.length).toBe(3);
    const zones = (await get('/v1/dashboard/admin/network/zones', { offset: 0, limit: 20, zone_type: 'central' })) as { zones: { zone_type: string }[] };
    expect(zones.zones.length).toBe(1);
    expect(zones.zones[0].zone_type).toBe('central');
  });

  it('egress gateways, dedicated channels + health checks', async () => {
    expect(((await get('/v1/egress/gateways')) as { gateways: unknown[]; total: number }).total).toBe(3);
    const ch = (await get('/v1/egress/dedicated-channels', { offset: 0, limit: 20 })) as {
      channels: { id: string }[];
    };
    expect(ch.channels.length).toBe(3);
    const checks = (await get(`/v1/egress/dedicated-channels/${ch.channels[0].id}/health-checks`)) as unknown[];
    expect(checks.length).toBeGreaterThan(0);
  });

  it('route policies/decisions/relay nodes filter', async () => {
    expect(((await get('/v1/routes/policies')) as { policies: unknown[] }).policies.length).toBe(3);
    const dec = (await get('/v1/routes/decisions', { offset: 0, limit: 20, task_id: 'nope' })) as { decisions: unknown[] };
    expect(dec.decisions).toHaveLength(0);
    expect(((await get('/v1/routes/relay-nodes')) as { nodes: unknown[] }).nodes.length).toBe(4);
    const degraded = (await get('/v1/routes/relay-nodes', { offset: 0, limit: 20, status: 'degraded' })) as { nodes: { status: string }[] };
    expect(degraded.nodes).toHaveLength(1);
  });

  it('sla targets/violations, circuit breakers, failover events', async () => {
    expect(((await get('/v1/sla/targets')) as { targets: unknown[] }).targets.length).toBe(4);
    const open = (await get('/v1/sla/violations', { resolved: 'false' })) as { violations: { resolved: boolean }[] };
    expect(open.violations.every((v) => !v.resolved)).toBe(true);
    expect(((await get('/v1/continuity/circuit-breakers')) as { circuit_breakers: { is_open: boolean }[] }).circuit_breakers.some((b) => b.is_open)).toBe(true);
    expect(((await get('/v1/continuity/failover-events', { limit: 10 })) as { events: unknown[] }).events.length).toBe(2);
  });

  it('organizations mine + members, personal scope + edge relays', async () => {
    const mine = (await get('/v1/organizations/mine')) as { organizations: { org_id: string }[] };
    expect(mine.organizations).toHaveLength(1);
    const members = (await get(`/v1/organizations/${mine.organizations[0].org_id}/members`)) as { members: { user_id: string }[] };
    expect(members.members.map((m) => m.user_id)).toContain(personaById('org_manager').buildMe().user_id);
    expect(((await get('/v1/personal/scope')) as { default_relay_type: string }).default_relay_type).toBe('central_relay');
    expect(((await get('/v1/personal/edge-relays')) as unknown[]).length).toBe(2);
  });

  it('unknown GET route 404s with a page-readable error', async () => {
    await fail('/v1/does/not/exist');
  });
});

describe('demo write paths', () => {
  beforeEach(async () => {
    await login('super_admin');
  });

  it('egress gateway create -> list -> patch -> delete', async () => {
    const created = await demoApi.post('/v1/egress/gateways', {
      scope_id: getDemoStore().world.scopes[0].scope_id,
      gateway_name: 'Probe GW',
      gateway_type: 'api',
      domain_allowlist: ['probe.example.com'],
      secret_store_ref: 'env:PROBE_KEY',
      cost_tracking: true,
    });
    expect((created as unknown as { status: number }).status).toBe(201);
    const id = (created.data as { id: string }).id;

    const after = (await get('/v1/egress/gateways')) as { gateways: { id: string }[]; total: number };
    expect(after.total).toBe(4);

    const patched = await demoApi.patch(`/v1/egress/gateways/${id}`, { enabled: false });
    expect((patched.data as { enabled: boolean }).enabled).toBe(false);

    await demoApi.delete(`/v1/egress/gateways/${id}`);
    expect(((await get('/v1/egress/gateways')) as { total: number }).total).toBe(3);
  });

  it('approvals accept/reject mutate state', async () => {
    const pending = (await get('/v1/dashboard/approvals')) as { approvals: { approval_id: string; status: string }[] };
    const id = pending.approvals.find((a) => a.status === 'pending')!.approval_id;
    const r = await demoApi.post(`/v1/dashboard/approvals/${id}/accept`);
    expect((r.data as { status: string }).status).toBe('accepted');
  });

  it('api key create + revoke', async () => {
    const r = await demoApi.post('/v1/dashboard/api-keys', { name: 'probe-key' });
    expect((r.data as { api_key: string }).api_key).toMatch(/^ak/);
    const list = (await get('/v1/dashboard/api-keys')) as { api_keys: { api_key_id: string }[]; total: number };
    expect(list.total).toBe(2); // demo_admin starts with one, the probe created the second
    await demoApi.post(`/v1/dashboard/api-keys/${list.api_keys[0].api_key_id}/revoke`);
    expect(((await get('/v1/dashboard/api-keys')) as { api_keys: { revoked_at: string | null }[] }).api_keys[0].revoked_at).toBeTruthy();
  });

  it('access request approval provisions a user', async () => {
    const reqs = (await get('/v1/dashboard/admin/access-requests')) as {
      access_requests: { request_id: string; status: string }[];
    };
    const id = reqs.access_requests.find((r) => r.status === 'pending')!.request_id;
    const r = await demoApi.post(`/v1/dashboard/admin/access-requests/${id}/approve`);
    expect((r.data as { user_id: string }).user_id).toBeTruthy();
    expect(((await get('/v1/dashboard/admin/users')) as { users: unknown[] }).users.length).toBe(5);
  });

  it('network scope create/delete and zone create', async () => {
    const created = await demoApi.post('/v1/dashboard/admin/network/scopes', {
      scope_name: 'Probe Scope',
      scope_type: 'enterprise',
      network_cidr: '10.9.0.0/16',
    });
    const id = (created.data as { scope_id: string }).scope_id;
    expect(((await get('/v1/dashboard/admin/network/scopes')) as { scopes: unknown[] }).scopes.length).toBe(4);
    const zone = await demoApi.post('/v1/dashboard/admin/network/zones', {
      zone_name: 'Probe Zone',
      zone_type: 'regional',
      scope_id: id,
    });
    expect((zone.data as { zone_id: string }).zone_id).toBeTruthy();
    await demoApi.delete(`/v1/dashboard/admin/network/scopes/${id}`);
    expect(((await get('/v1/dashboard/admin/network/scopes')) as { scopes: unknown[] }).scopes.length).toBe(3);
  });

  it('dedicated channel create + health check + delete', async () => {
    const created = await demoApi.post('/v1/egress/dedicated-channels', {
      channel_name: 'probe-vpn',
      channel_type: 'vpn',
      source_agent_id: getDemoStore().world.agents[0].agent_id,
      target_agent_id: getDemoStore().world.agents[1].agent_id,
    });
    const id = (created.data as { id: string }).id;
    const check = await demoApi.post(`/v1/egress/dedicated-channels/${id}/health-check`);
    expect((check.data as { status: string }).status).toBe('healthy');
    await demoApi.delete(`/v1/egress/dedicated-channels/${id}`);
    expect(((await get('/v1/egress/dedicated-channels')) as { channels: unknown[] }).channels.length).toBe(3); // 3 initial + 1 created - 1 deleted
  });

  it('route policy create + patch enabled; relay node create + delete', async () => {
    const created = await demoApi.post('/v1/routes/policies', {
      policy_name: 'Probe Policy',
      priority: 5,
      denied_route_types: ['personal_edge'],
    });
    const id = (created.data as { id: string }).id;
    const patched = await demoApi.patch(`/v1/routes/policies/${id}`, { enabled: false });
    expect((patched.data as { enabled: boolean }).enabled).toBe(false);

    const node = await demoApi.post('/v1/routes/relay-nodes', { node_name: 'probe-relay', node_type: 'central' });
    await demoApi.delete(`/v1/routes/relay-nodes/${(node.data as { id: string }).id}`);
    expect(((await get('/v1/routes/relay-nodes')) as { nodes: unknown[] }).nodes.length).toBe(4);
  });

  it('org member add/patch/delete', async () => {
    const org = getDemoStore().world.organizations[0];
    const newUserId = getDemoStore().world.users[0].user_id;
    const before = ((await get(`/v1/organizations/${org.org_id}/members`)) as { members: unknown[] }).members.length;
    await demoApi.post(`/v1/organizations/${org.org_id}/members`, { user_id: newUserId, role: 'member' });
    await demoApi.patch(`/v1/organizations/${org.org_id}/members/${newUserId}`, { role: 'manager' });
    await demoApi.delete(`/v1/organizations/${org.org_id}/members/${newUserId}`);
    expect(((await get(`/v1/organizations/${org.org_id}/members`)) as { members: unknown[] }).members.length).toBe(before);
  });

  it('personal scope patch flips edge relay', async () => {
    const r = await demoApi.patch('/v1/personal/scope', { enable_edge_relay: false });
    expect((r.data as { enable_edge_relay: boolean }).enable_edge_relay).toBe(false);
  });

  it('unknown mutation 404s', async () => {
    await expect(demoApi.post('/v1/nowhere', {})).rejects.toMatchObject({
      response: { data: { detail: expect.any(String) } },
    });
  });
});

describe('demo persona scoping', () => {
  it('personal persona sees only its own agents', async () => {
    await login('personal');
    const o = (await get('/v1/dashboard/overview')) as { online_agents: number };
    expect(o.online_agents).toBe(2); // demo_user owns 5 agents, 2 online
    const agents = (await get('/v1/dashboard/agents', { page: 1, page_size: 20 })) as { agents: unknown[] };
    expect(agents.agents).toHaveLength(5);
  });

  it('org manager persona sees its org members agents', async () => {
    await login('org_manager');
    // Org-manager visibility is org-wide: Acme's members are demo_manager
    // AND demo_user, so every one of the 8 agents is in scope.
    const agents = (await get('/v1/dashboard/agents', { page: 1, page_size: 20 })) as { agents: unknown[] };
    expect(agents.agents).toHaveLength(8);
  });
});

describe('demo fixtures integrity', () => {
  it('the fixture world satisfies its own invariants', () => {
    const w = createDemoWorld();
    // Every task references agents that exist.
    const names = new Set(w.agents.map((a) => a.name));
    expect(w.tasks.every((t) => names.has(t.sender_agent) && names.has(t.target_agent))).toBe(true);
    // Gateways reference real scopes; decisions reference real tasks.
    const scopeIds = new Set(w.scopes.map((s) => s.scope_id));
    expect(w.gateways.every((g) => scopeIds.has(g.scope_id))).toBe(true);
    const taskIds = new Set(w.tasks.map((t) => t.task_id));
    expect(w.decisions.every((d) => taskIds.has(d.task_id))).toBe(true);
    // SLA violations reference real targets.
    const targetIds = new Set(w.slaTargets.map((t) => t.id));
    expect(w.slaViolations.every((v) => targetIds.has(v.target_id))).toBe(true);
  });
});

/**
 * Demo API adapter: routes every console request to the in-memory fixture
 * world. Drop-in replacement for the axios instance in demo builds: same
 * call signature (`get/post/put/patch/delete` returning `Promise<{data}>`),
 * so pages, react-query, useAuth and the route guards run unmodified.
 *
 * - Successful responses always RESOLVE, so the 401 interceptor and the
 *   CSRF request interceptor (both no-ops here) never fire.
 * - Failures reject with the shape pages already read:
 *   `err.response.data.detail` / `.error.message`, so extractDomainError
 *   surfaces them verbatim.
 * - Mutations mutate the store; pages then invalidate their query keys and
 *   the next GET re-reads the mutated world — the real request cycle.
 */
import { getDemoStore, resetDemoStore, setDemoSession } from './demoStore';
import { personaById, type PersonaId } from './personas';
import type {
  DemoAgent,
  DemoChannel,
  DemoGateway,
  DemoNetworkScope,
  DemoNetworkZone,
  DemoPolicy,
  DemoRelayNode,
} from './fixtures';

interface ReqConfig {
  params?: Record<string, unknown>;
}

type Res = { data: unknown };

/** Demo failure shaped like an axios error so pages' error readers work. */
function rejectDemo(status: number, message: string): Promise<never> {
  const e = { response: { status, data: { detail: message, error: { message, detail: message } } } };
  return Promise.reject(e);
}

function param(params: ReqConfig['params'], key: string): string | undefined {
  const v = params?.[key];
  return v === undefined || v === null || v === '' ? undefined : String(v);
}

function num(params: ReqConfig['params'], key: string, fallback: number): number {
  const v = param(params, key);
  const n = v === undefined ? NaN : parseInt(v, 10);
  return Number.isFinite(n) ? n : fallback;
}

function pageSlice<T>(items: T[], offset: number, limit: number) {
  return { items: items.slice(offset, offset + limit), offset, limit, total: items.length };
}

function match(url: string, pattern: string): RegExpMatchArray | null {
  return url.match(new RegExp('^' + pattern.replace(/\./g, '\\.').replace(/\{[^}]+\}/g, '([^/]+)') + '$'));
}

// ───────────────────────────────────────────────────────────────────
// Store-derived views
// ───────────────────────────────────────────────────────────────────

const NOW = Date.now;
const dayMs = 24 * 60 * 60 * 1000;

/** Agents visible to the current persona (ownership scoping, like prod). */
function visibleAgents(): DemoAgent[] {
  const { world, personaId } = getDemoStore();
  if (personaId === 'super_admin') return world.agents;
  const me = personaById(personaId).buildMe().user_id;
  if (personaId === 'org_manager') {
    const memberIds = world.organizations[0]?.members.map((m) => m.user_id) ?? [];
    return world.agents.filter((a) => memberIds.includes(a.owner_user_id));
  }
  return world.agents.filter((a) => a.owner_user_id === me);
}

function visibleTasks() {
  const { world } = getDemoStore();
  const agentNames = new Set(visibleAgents().map((a) => a.name));
  return world.tasks.filter((t) => agentNames.has(t.sender_agent) || agentNames.has(t.target_agent));
}

// ───────────────────────────────────────────────────────────────────
// GET handlers
// ───────────────────────────────────────────────────────────────────

function handleGet(url: string, params?: ReqConfig['params']): unknown {
  const { world, loggedIn, personaId } = getDemoStore();
  const me = personaById(personaId).buildMe();
  let m: RegExpMatchArray | null;

  // ── auth ────────────────────────────────────────────────────────
  if (url === '/v1/dashboard/auth/me') {
    if (!loggedIn) return rejectDemo(401, 'not authenticated');
    return { ...me, locale: getDemoStore().locale ?? null };
  }
  if (url === '/v1/dashboard/auth/me/preferences') {
    return { locale: getDemoStore().locale ?? null, preferences: {} };
  }

  // ── personal console ─────────────────────────────────────────────
  if (url === '/v1/dashboard/overview') {
    if (!loggedIn) return rejectDemo(401, 'not authenticated');
    const agents = visibleAgents();
    const tasks = visibleTasks();
    const recentTasks = [...tasks]
      .sort((a, b) => NOW() - new Date(b.created_at).getTime() - (NOW() - new Date(a.created_at).getTime()))
      .slice(0, 5);
    const recentApprovals = world.approvals.slice(0, 5);
    return {
      online_agents: agents.filter((a) => a.status === 'online').length,
      tasks_today: tasks.filter((t) => new Date(t.created_at).getTime() > NOW() - dayMs).length,
      failed_tasks: tasks.filter((t) => t.status === 'failed').length,
      pending_approvals: world.approvals.filter((a) => a.status === 'pending').length,
      pending_messages: world.pendingConnections.length,
      recent_tasks: recentTasks.map((t) => ({ task_id: t.task_id, status: t.status, created_at: t.created_at })),
      recent_approvals: recentApprovals.map((a) => ({
        approval_id: a.approval_id,
        status: a.status,
        risk_level: a.risk_level,
        created_at: a.created_at,
      })),
      recent_agent_status_changes: world.auditLogs.slice(0, 4).map((l) => ({
        action: l.action,
        resource_id: l.resource_id ?? '',
        created_at: l.created_at,
      })),
    };
  }

  if (url === '/v1/dashboard/agents') {
    if (!loggedIn) return rejectDemo(401, 'not authenticated');
    const page = num(params, 'page', 1);
    const limit = num(params, 'page_size', 20);
    const statusFilter = param(params, 'status_filter');
    const search = param(params, 'search')?.toLowerCase();
    let agents = visibleAgents();
    if (statusFilter) agents = agents.filter((a) => a.status === statusFilter);
    if (search) agents = agents.filter((a) => a.name.toLowerCase().includes(search) || a.agent_number.toLowerCase().includes(search));
    const offset = (page - 1) * limit;
    const sliced = pageSlice(agents, offset, limit);
    return {
      agents: sliced.items.map((a) => ({
        agent_id: a.agent_id,
        agent_number: a.agent_number,
        name: a.name,
        runtime: a.runtime,
        status: a.status,
        inbound_policy: a.inbound_policy,
        discoverable: a.discoverable,
        capabilities: a.capabilities,
        created_at: a.created_at,
        updated_at: a.updated_at,
        last_seen_at: a.last_seen_at,
      })),
      total: sliced.total,
      offset: page,
      limit: sliced.limit,
    };
  }

  if ((m = match(url, '/v1/dashboard/agents/([0-9a-zA-Z-]+)'))) {
    if (!loggedIn) return rejectDemo(401, 'not authenticated');
    const agent = world.agents.find((a) => a.agent_id === m![1]);
    if (!agent) return rejectDemo(404, 'agent not found');
    return {
      agent_id: agent.agent_id,
      agent_number: agent.agent_number,
      name: agent.name,
      runtime: agent.runtime,
      status: agent.status,
      inbound_policy: agent.inbound_policy,
      discoverable: agent.discoverable,
      capabilities: agent.capabilities,
      created_at: agent.created_at,
      updated_at: agent.updated_at,
      token_metadata: {
        prefix: agent.token_prefix,
        created_at: agent.created_at,
        rotated_at: null,
      },
    };
  }

  if (url === '/v1/dashboard/tasks') {
    if (!loggedIn) return rejectDemo(401, 'not authenticated');
    const offset = num(params, 'offset', 0);
    const limit = num(params, 'limit', 20);
    const statusFilter = param(params, 'status_filter');
    const errorCode = param(params, 'error_code');
    let tasks = visibleTasks();
    if (statusFilter) tasks = tasks.filter((t) => t.status === statusFilter);
    if (errorCode) tasks = tasks.filter((t) => t.error_code === errorCode);
    const sliced = pageSlice(tasks, offset, limit);
    return {
      tasks: sliced.items.map((t) => ({
        task_id: t.task_id,
        status: t.status,
        sender_agent: t.sender_agent,
        target_agent: t.target_agent,
        created_at: t.created_at,
        updated_at: t.updated_at,
        duration_sec: t.duration_sec,
        error_code: t.error_code,
        delivery_status: t.delivery_status,
      })),
      total: sliced.total,
      offset: sliced.offset,
      limit: sliced.limit,
    };
  }

  if ((m = match(url, '/v1/dashboard/tasks/([0-9a-zA-Z-]+)'))) {
    if (!loggedIn) return rejectDemo(401, 'not authenticated');
    const task = world.tasks.find((t) => t.task_id === m![1]);
    if (!task) return rejectDemo(404, 'task not found');
    return {
      task_id: task.task_id,
      status: task.status,
      payload_preview: task.payload_preview,
      result_preview: task.result_preview,
      error_message: task.error_message,
      delivery_status: task.delivery_status,
      retry_count: task.retry_count,
      created_at: task.created_at,
      updated_at: task.updated_at,
    };
  }

  if ((m = match(url, '/v1/dashboard/tasks/([0-9a-zA-Z-]+)/messages'))) {
    const task = world.tasks.find((t) => t.task_id === m![1]);
    if (!task) return rejectDemo(404, 'task not found');
    const offset = num(params, 'offset', 0);
    const limit = num(params, 'limit', 50);
    const sliced = pageSlice(task.messages, offset, limit);
    return { messages: sliced.items, total: sliced.total, offset: sliced.offset, limit: sliced.limit };
  }

  if ((m = match(url, '/v1/dashboard/tasks/([0-9a-zA-Z-]+)/progress'))) {
    const task = world.tasks.find((t) => t.task_id === m![1]);
    if (!task) return rejectDemo(404, 'task not found');
    const offset = num(params, 'offset', 0);
    const limit = num(params, 'limit', 50);
    const sliced = pageSlice(task.progress, offset, limit);
    return { progress: sliced.items, total: sliced.total, offset: sliced.offset, limit: sliced.limit };
  }

  if ((m = match(url, '/v1/tasks/([0-9a-zA-Z-]+)/delivery-events'))) {
    const task = world.tasks.find((t) => t.task_id === m![1]);
    if (!task) return rejectDemo(404, 'task not found');
    return {
      delivery_events: task.messages.map((msg, i) => ({
        event_id: `dv-${task.task_id.slice(-6)}-${i}`,
        event_type: i === 0 ? 'route_selected' : 'delivered',
        route_type: 'central_relay',
        relay_node_id: world.relayNodes[0]?.id ?? null,
        latency_ms: 12 + i * 8,
        queue_wait_ms: i * 3,
        error_code: null,
        created_at: msg.created_at,
      })),
    };
  }

  if ((m = match(url, '/v1/tasks/([0-9a-zA-Z-]+)/route-decisions'))) {
    const decisions = world.decisions.filter((d) => d.task_id === m![1]);
    return { decisions };
  }

  if (url === '/v1/dashboard/approvals') {
    if (!loggedIn) return rejectDemo(401, 'not authenticated');
    const offset = num(params, 'offset', 0);
    const limit = num(params, 'limit', 20);
    const statusFilter = param(params, 'status_filter');
    let approvals = world.approvals;
    if (statusFilter) approvals = approvals.filter((a) => a.status === statusFilter);
    const sliced = pageSlice(approvals, offset, limit);
    return {
      approvals: sliced.items.map((a) => ({
        approval_id: a.approval_id,
        type: a.type,
        status: a.status,
        risk_level: a.risk_level,
        action_kind: a.action_kind,
        action_preview: a.action_preview,
        created_at: a.created_at,
      })),
      total: sliced.total,
      offset: sliced.offset,
      limit: sliced.limit,
    };
  }

  if (url === '/v1/dashboard/connections') {
    if (!loggedIn) return rejectDemo(401, 'not authenticated');
    const agentRows = visibleAgents().map((a) => {
      const stats = world.connectionStats[a.agent_id] ?? { pending: 0, accepted: 0, rejected: 0 };
      return {
        agent_id: a.agent_id,
        agent_number: a.agent_number,
        inbound_policy: a.inbound_policy,
        pending_requests: stats.pending,
        accepted_connections: stats.accepted,
        rejected_connections: stats.rejected,
      };
    });
    return {
      agents: agentRows,
      pending_requests: world.pendingConnections.map((c) => ({
        connection_id: c.connection_id,
        agent_number: c.agent_number,
        requester_agent: c.requester_agent,
        requested_policy: c.requested_policy,
        created_at: c.created_at,
      })),
    };
  }

  if (url === '/v1/dashboard/api-keys') {
    if (!loggedIn) return rejectDemo(401, 'not authenticated');
    const meId = me.user_id;
    const keys = world.apiKeys.filter((k) => k.owner_user_id === meId);
    return {
      api_keys: keys.map((k) => ({
        api_key_id: k.api_key_id,
        key_prefix: k.key_prefix,
        name: k.name,
        created_at: k.created_at,
        expires_at: k.expires_at,
        revoked_at: k.revoked_at,
      })),
      total: keys.length,
    };
  }

  // ── admin console ────────────────────────────────────────────────
  if (url === '/v1/dashboard/admin/overview') {
    const tasks = world.tasks;
    return {
      total_users: world.users.length,
      active_users: world.users.filter((u) => !u.is_disabled).length,
      disabled_users: world.users.filter((u) => u.is_disabled).length,
      total_agents: world.agents.length,
      online_agents: world.agents.filter((a) => a.status === 'online').length,
      active_ws_connections: 7,
      tasks_1h: tasks.filter((t) => new Date(t.created_at).getTime() > NOW() - 60 * 60 * 1000).length,
      tasks_24h: tasks.filter((t) => new Date(t.created_at).getTime() > NOW() - dayMs).length,
      tasks_7d: tasks.length,
      failed_tasks: tasks.filter((t) => t.status === 'failed').length,
      expired_tasks: tasks.filter((t) => t.status === 'expired').length,
      pending_approvals: world.approvals.filter((a) => a.status === 'pending').length,
      pending_messages: world.pendingConnections.length,
      retry_worker_health: 'ok',
      timeout_worker_health: 'ok',
      api_5xx_rate: '0.00',
    };
  }

  if (url === '/v1/dashboard/admin/users') {
    const offset = num(params, 'offset', 0);
    const limit = num(params, 'limit', 20);
    const roleFilter = param(params, 'role_filter');
    const search = param(params, 'search')?.toLowerCase();
    let users = world.users;
    if (roleFilter) users = users.filter((u) => u.role === roleFilter);
    if (search) users = users.filter((u) => u.username.toLowerCase().includes(search));
    const sliced = pageSlice(users, offset, limit);
    return {
      users: sliced.items.map((u) => {
        const agentCount = world.agents.filter((a) => a.owner_user_id === u.user_id).length;
        const keyCount = world.apiKeys.filter((k) => k.owner_user_id === u.user_id && !k.revoked_at).length;
        const userTasks = world.tasks.filter((t) =>
          world.agents.some((a) => a.owner_user_id === u.user_id && (a.name === t.sender_agent || a.name === t.target_agent)),
        );
        return {
          user_id: u.user_id,
          username: u.username,
          role: u.role,
          is_disabled: u.is_disabled,
          agents_count: agentCount,
          active_api_keys_count: keyCount,
          tasks_24h: userTasks.length,
          failed_tasks_24h: userTasks.filter((t) => t.status === 'failed').length,
          created_at: u.created_at,
        };
      }),
      total: sliced.total,
      offset: sliced.offset,
      limit: sliced.limit,
    };
  }

  if ((m = match(url, '/v1/dashboard/admin/users/([0-9a-zA-Z-]+)'))) {
    const user = world.users.find((u) => u.user_id === m![1]);
    if (!user) return rejectDemo(404, 'user not found');
    return {
      user_id: user.user_id,
      username: user.username,
      role: user.role,
      is_disabled: user.is_disabled,
      created_at: user.created_at,
      preferences: {},
    };
  }

  if (url === '/v1/dashboard/admin/agents') {
    const offset = num(params, 'offset', 0);
    const limit = num(params, 'limit', 20);
    const runtimeFilter = param(params, 'runtime_filter');
    const statusFilter = param(params, 'status_filter');
    const search = param(params, 'search')?.toLowerCase();
    let agents = world.agents;
    if (runtimeFilter) agents = agents.filter((a) => a.runtime === runtimeFilter);
    if (statusFilter) agents = agents.filter((a) => a.status === statusFilter);
    if (search) agents = agents.filter((a) => a.name.toLowerCase().includes(search));
    const sliced = pageSlice(agents, offset, limit);
    return {
      agents: sliced.items.map((a) => ({
        agent_id: a.agent_id,
        agent_number: a.agent_number,
        owner_username: a.owner_username,
        name: a.name,
        status: a.status,
        runtime: a.runtime,
        inbound_policy: a.inbound_policy,
        discoverable: a.discoverable,
        tasks_24h: world.tasks.filter((t) => t.sender_agent === a.name).length,
        failed_tasks_24h: world.tasks.filter((t) => t.sender_agent === a.name && t.status === 'failed').length,
      })),
      total: sliced.total,
      offset: sliced.offset,
      limit: sliced.limit,
    };
  }

  if ((m = match(url, '/v1/dashboard/admin/agents/([0-9a-zA-Z-]+)'))) {
    const agent = world.agents.find((a) => a.agent_id === m![1]);
    if (!agent) return rejectDemo(404, 'agent not found');
    return {
      agent_id: agent.agent_id,
      agent_number: agent.agent_number,
      owner_username: agent.owner_username,
      name: agent.name,
      runtime: agent.runtime,
      status: agent.status,
      inbound_policy: agent.inbound_policy,
      discoverable: agent.discoverable,
      capabilities: agent.capabilities,
      created_at: agent.created_at,
      updated_at: agent.updated_at,
      token_metadata: { prefix: agent.token_prefix, created_at: agent.created_at, rotated_at: null },
    };
  }

  if (url === '/v1/dashboard/admin/tasks') {
    const offset = num(params, 'offset', 0);
    const limit = num(params, 'limit', 20);
    const statusFilter = param(params, 'status_filter');
    let tasks = world.tasks;
    if (statusFilter) tasks = tasks.filter((t) => t.status === statusFilter);
    const sliced = pageSlice(tasks, offset, limit);
    return {
      tasks: sliced.items.map((t) => ({
        task_id: t.task_id,
        status: t.status,
        sender_agent: t.sender_agent,
        target_agent: t.target_agent,
        owner_username: ownerOf(t.sender_agent),
        created_at: t.created_at,
        updated_at: t.updated_at,
        error_code: t.error_code,
        delivery_status: t.delivery_status,
      })),
      total: sliced.total,
      offset: sliced.offset,
      limit: sliced.limit,
    };
  }

  if ((m = match(url, '/v1/dashboard/admin/tasks/([0-9a-zA-Z-]+)'))) {
    const task = world.tasks.find((t) => t.task_id === m![1]);
    if (!task) return rejectDemo(404, 'task not found');
    return {
      task_id: task.task_id,
      status: task.status,
      sender_agent: task.sender_agent,
      target_agent: task.target_agent,
      owner_username: ownerOf(task.sender_agent),
      payload_preview: task.payload_preview,
      result_preview: task.result_preview,
      error_message: task.error_message,
      delivery_status: task.delivery_status,
      retry_count: task.retry_count,
      created_at: task.created_at,
      updated_at: task.updated_at,
    };
  }

  if (url === '/v1/dashboard/admin/audit-logs') {
    const offset = num(params, 'offset', 0);
    const limit = num(params, 'limit', 20);
    const actorType = param(params, 'actor_type');
    const action = param(params, 'action');
    const resourceType = param(params, 'resource_type');
    const resourceId = param(params, 'resource_id');
    let logs = [...world.auditLogs].sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime());
    if (actorType) logs = logs.filter((l) => l.actor_type === actorType);
    if (action) logs = logs.filter((l) => l.action === action);
    if (resourceType) logs = logs.filter((l) => l.resource_type === resourceType);
    if (resourceId) logs = logs.filter((l) => l.resource_id === resourceId);
    const sliced = pageSlice(logs, offset, limit);
    return {
      audit_logs: sliced.items.map((l) => ({
        audit_id: l.audit_id,
        actor_type: l.actor_type,
        actor_id: l.actor_id,
        action: l.action,
        resource_type: l.resource_type,
        resource_id: l.resource_id,
        task_id: l.task_id,
        error_code: l.error_code,
        request_ip: l.request_ip,
        details: l.details,
        created_at: l.created_at,
      })),
      total: sliced.total,
      offset: sliced.offset,
      limit: sliced.limit,
    };
  }

  if (url === '/v1/dashboard/admin/system-health') {
    return {
      api_health: 'healthy',
      db_health: 'healthy',
      redis_health: 'healthy',
      migration_revision: '0030',
      app_version: '0.1.0-demo',
      retry_worker_health: 'ok',
      timeout_worker_health: 'ok',
      pending_queue_length: world.relayNodes.reduce((s, n) => s + n.queue_depth, 0),
      https_wss_staging: 'enabled',
    };
  }

  if (url === '/v1/dashboard/admin/access-requests') {
    const offset = num(params, 'offset', 0);
    const limit = num(params, 'limit', 20);
    const statusFilter = param(params, 'status');
    let reqs = world.accessRequests;
    if (statusFilter) reqs = reqs.filter((r) => r.status === statusFilter);
    const sliced = pageSlice(reqs, offset, limit);
    return {
      access_requests: sliced.items.map((r) => ({
        request_id: r.request_id,
        applicant_name: r.applicant_name,
        applicant_email: r.applicant_email,
        organization: r.organization,
        requested_mode: r.requested_mode,
        status: r.status,
        review_notes: r.review_notes,
        created_at: r.created_at,
        reviewed_at: r.reviewed_at,
      })),
      total: sliced.total,
      offset: sliced.offset,
      limit: sliced.limit,
    };
  }

  // ── network topology ─────────────────────────────────────────────
  if (url === '/v1/dashboard/admin/network/scopes') {
    const offset = num(params, 'offset', 0);
    const limit = num(params, 'limit', 20);
    const typeFilter = param(params, 'scope_type');
    let scopes = world.scopes;
    if (typeFilter) scopes = scopes.filter((s) => s.scope_type === typeFilter);
    const sliced = pageSlice(scopes, offset, limit);
    return { scopes: sliced.items, total: sliced.total, offset: sliced.offset, limit: sliced.limit };
  }
  if (url === '/v1/dashboard/admin/network/zones') {
    const offset = num(params, 'offset', 0);
    const limit = num(params, 'limit', 20);
    const typeFilter = param(params, 'zone_type');
    const scopeFilter = param(params, 'scope_id_filter');
    let zones = world.zones;
    if (typeFilter) zones = zones.filter((z) => z.zone_type === typeFilter);
    if (scopeFilter) zones = zones.filter((z) => z.scope_id === scopeFilter);
    const sliced = pageSlice(zones, offset, limit);
    return { zones: sliced.items, total: sliced.total, offset: sliced.offset, limit: sliced.limit };
  }

  // ── egress gateways / dedicated channels ─────────────────────────
  if (url === '/v1/egress/gateways') {
    return {
      gateways: [...world.gateways].sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()),
      total: world.gateways.length,
    };
  }
  if (url === '/v1/dashboard/admin/dedicated-channels') {
    const offset = num(params, 'offset', 0);
    const limit = num(params, 'limit', 20);
    const typeFilter = param(params, 'channel_type');
    let channels = world.channels;
    if (typeFilter) channels = channels.filter((c) => c.channel_type === typeFilter);
    const sliced = pageSlice(channels, offset, limit);
    return { channels: sliced.items, total: sliced.total, offset: sliced.offset, limit: sliced.limit };
  }
  if ((m = match(url, '/v1/dashboard/admin/dedicated-channels/([0-9a-zA-Z-]+)/health-checks'))) {
    const ch = world.channels.find((c) => c.id === m![1]);
    if (!ch) return rejectDemo(404, 'channel not found');
    return ch.health_checks;
  }

  // ── routing ──────────────────────────────────────────────────────
  if (url === '/v1/routes/policies') {
    const offset = num(params, 'offset', 0);
    const limit = num(params, 'limit', 100);
    const scopeFilter = param(params, 'scope_id');
    const enabledFilter = param(params, 'enabled');
    let policies = [...world.policies].sort((a, b) => a.priority - b.priority);
    if (scopeFilter) policies = policies.filter((p) => p.scope_id === scopeFilter);
    if (enabledFilter !== undefined) policies = policies.filter((p) => String(p.enabled) === enabledFilter);
    const sliced = pageSlice(policies, offset, limit);
    return { policies: sliced.items, total: sliced.total };
  }
  if (url === '/v1/routes/decisions') {
    const offset = num(params, 'offset', 0);
    const limit = num(params, 'limit', 20);
    const taskFilter = param(params, 'task_id');
    let decisions = [...world.decisions].sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime());
    if (taskFilter) decisions = decisions.filter((d) => d.task_id === taskFilter);
    const sliced = pageSlice(decisions, offset, limit);
    return { decisions: sliced.items, total: sliced.total, offset: sliced.offset, limit: sliced.limit };
  }
  if (url === '/v1/relay-nodes') {
    const offset = num(params, 'offset', 0);
    const limit = num(params, 'limit', 20);
    const nodeType = param(params, 'node_type');
    const status = param(params, 'status');
    let nodes = world.relayNodes;
    if (nodeType) nodes = nodes.filter((n) => n.node_type === nodeType);
    if (status) nodes = nodes.filter((n) => n.status === status);
    const sliced = pageSlice(nodes, offset, limit);
    return { nodes: sliced.items, total: sliced.total, offset: sliced.offset, limit: sliced.limit };
  }

  // ── SLA & continuity ─────────────────────────────────────────────
  if (url === '/v1/sla/targets') {
    const scopeFilter = param(params, 'scope_id');
    const enabled = param(params, 'enabled');
    let targets = world.slaTargets;
    if (scopeFilter) targets = targets.filter((t) => t.scope_id === scopeFilter);
    if (enabled !== undefined) targets = targets.filter((t) => String(t.enabled) === enabled);
    return { targets };
  }
  if (url === '/v1/sla/violations') {
    const targetId = param(params, 'target_id');
    const severity = param(params, 'severity');
    const resolved = param(params, 'resolved');
    const limit = num(params, 'limit', 100);
    let violations = [...world.slaViolations].sort((a, b) => new Date(b.violation_time).getTime() - new Date(a.violation_time).getTime());
    if (targetId) violations = violations.filter((v) => v.target_id === targetId);
    if (severity) violations = violations.filter((v) => v.severity === severity);
    if (resolved !== undefined) violations = violations.filter((v) => String(v.resolved) === resolved);
    return { violations: violations.slice(0, limit) };
  }
  if (url === '/v1/continuity/circuit-breakers') {
    return { circuit_breakers: world.circuitBreakers };
  }
  if (url === '/v1/continuity/failover-events') {
    const limit = num(params, 'limit', 50);
    return { events: world.failoverEvents.slice(0, limit) };
  }
  if (url === '/v1/continuity/failover-configs') {
    return { configs: world.failoverConfigs };
  }

  // ── organizations ────────────────────────────────────────────────
  if (url === '/v1/organizations/mine') {
    return {
      organizations: world.organizations.map((o) => ({
        org_id: o.org_id,
        name: o.name,
        slug: o.slug,
        role: o.role,
        is_disabled: o.is_disabled,
        created_at: o.created_at,
      })),
    };
  }
  if ((m = match(url, '/v1/organizations/([0-9a-zA-Z-]+)/members'))) {
    const org = world.organizations.find((o) => o.org_id === m![1]);
    if (!org) return rejectDemo(404, 'organization not found');
    return { members: org.members };
  }

  // ── personal routing ─────────────────────────────────────────────
  if (url === '/v1/personal/scope') {
    if (!loggedIn) return rejectDemo(401, 'not authenticated');
    return world.personalScope;
  }
  if (url === '/v1/personal/edge-relays') {
    if (!loggedIn) return rejectDemo(401, 'not authenticated');
    const onlyHealthy = param(params, 'only_healthy');
    if (onlyHealthy === 'true' || onlyHealthy === '1')
      return world.edgeRelays.filter((r) => r.is_healthy);
    return world.edgeRelays;
  }

  return rejectDemo(404, `demo adapter has no GET route for ${url}`);
}

/** Owner username of an agent by name (used by admin task rows). */
function ownerOf(agentName: string): string {
  const agent = getDemoStore().world.agents.find((a) => a.name === agentName);
  return agent?.owner_username ?? '—';
}

// ───────────────────────────────────────────────────────────────────
// Mutation handlers
// ───────────────────────────────────────────────────────────────────

function handleMutation(method: string, url: string, body?: unknown): Promise<Res> {
  const store = getDemoStore();
  const world = store.world;
  let m: RegExpMatchArray | null;

  // ── auth ────────────────────────────────────────────────────────
  if (method === 'post' && url === '/v1/dashboard/auth/login') {
    const { username } = body as { username: string };
    const persona = (['super_admin', 'org_manager', 'personal'] as PersonaId[]).find((id) =>
      personaById(id).username === username,
    );
    setDemoSession({ personaId: persona ?? 'personal', loggedIn: true });
    return ok({ message: 'authenticated (demo mode)' });
  }
  if (method === 'post' && url === '/v1/dashboard/auth/logout') {
    setDemoSession({ loggedIn: false });
    return ok({ message: 'logged out (demo mode)' });
  }
  if (method === 'post' && url === '/v1/dashboard/auth/step-up') {
    return ok({ message: 'step-up granted (demo mode)' });
  }
  if (method === 'patch' && url === '/v1/dashboard/auth/me/profile') {
    const { username } = body as { username: string };
    const me = personaById(store.personaId).buildMe();
    const user = world.users.find((u) => u.user_id === me.user_id);
    if (username && user) user.username = username;
    return ok({ user_id: me.user_id, username: username ?? user?.username ?? me.username });
  }
  if (method === 'patch' && url === '/v1/dashboard/auth/me/preferences') {
    const { locale } = body as { locale?: string };
    if (locale === 'en' || locale === 'zh') setDemoSession({ locale });
    return ok({ locale: getDemoStore().locale ?? null, preferences: {} });
  }

  if (!store.loggedIn) return rejectDemo(401, 'not authenticated');

  // ── approvals / connections ──────────────────────────────────────
  if (method === 'post' && (m = match(url, '/v1/dashboard/approvals/([0-9a-zA-Z-]+)/(accept|reject)'))) {
    const approval = world.approvals.find((a) => a.approval_id === m![1]);
    if (!approval) return rejectDemo(404, 'approval not found');
    approval.status = m![2] === 'accept' ? 'accepted' : 'rejected';
    return ok({ approval_id: approval.approval_id, status: approval.status });
  }
  if (method === 'post' && (m = match(url, '/v1/dashboard/connections/([0-9a-zA-Z-]+)/(accept|reject)'))) {
    const idx = world.pendingConnections.findIndex((c) => c.connection_id === m![1]);
    if (idx < 0) return rejectDemo(404, 'connection not found');
    const [conn] = world.pendingConnections.splice(idx, 1);
    return ok({ connection_id: conn.connection_id, status: m![2] === 'accept' ? 'accepted' : 'rejected' });
  }
  if (method === 'patch' && (m = match(url, '/v1/dashboard/agents/([0-9a-zA-Z-]+)/firewall'))) {
    const agent = world.agents.find((a) => a.agent_id === m![1]);
    if (!agent) return rejectDemo(404, 'agent not found');
    const { inbound_policy } = body as { inbound_policy: DemoAgent['inbound_policy'] };
    if (inbound_policy) agent.inbound_policy = inbound_policy;
    return ok({ agent_id: agent.agent_id, inbound_policy: agent.inbound_policy });
  }

  // ── api keys ─────────────────────────────────────────────────────
  if (method === 'post' && url === '/v1/dashboard/api-keys') {
    const { name, expires_at } = (body ?? {}) as { name?: string; expires_at?: string };
    const key = {
      api_key_id: crypto.randomUUID(),
      key_prefix: demoPrefix(),
      name: name ?? 'demo key',
      created_at: new Date().toISOString(),
      expires_at: expires_at ?? null,
      revoked_at: null,
      owner_user_id: personaById(store.personaId).buildMe().user_id,
    };
    world.apiKeys.unshift(key);
    return ok({
      api_key_id: key.api_key_id,
      key_prefix: key.key_prefix,
      name: key.name,
      created_at: key.created_at,
      expires_at: key.expires_at,
      // The raw key is shown exactly once in the real UI; this value only
      // ever lives in the in-memory demo world.
      api_key: demoPrefix() + demoRandom().toString(36).slice(2, 14),
    });
  }
  if (method === 'post' && (m = match(url, '/v1/dashboard/api-keys/([0-9a-zA-Z-]+)/revoke'))) {
    const key = world.apiKeys.find((k) => k.api_key_id === m![1]);
    if (!key) return rejectDemo(404, 'api key not found');
    key.revoked_at = new Date().toISOString();
    return ok({ api_key_id: key.api_key_id, key_prefix: key.key_prefix, name: key.name, revoked_at: key.revoked_at });
  }

  // ── admin actions ────────────────────────────────────────────────
  if (method === 'post' && (m = match(url, '/v1/dashboard/admin/users/([0-9a-zA-Z-]+)/disable'))) {
    const user = world.users.find((u) => u.user_id === m![1]);
    if (!user) return rejectDemo(404, 'user not found');
    const { is_disabled } = body as { is_disabled?: boolean };
    user.is_disabled = is_disabled ?? true;
    return ok({ user_id: user.user_id, is_disabled: user.is_disabled });
  }
  if (method === 'post' && (m = match(url, '/v1/dashboard/admin/users/([0-9a-zA-Z-]+)/force-revoke-keys'))) {
    const count = world.apiKeys.filter((k) => k.owner_user_id === m![1] && !k.revoked_at).length;
    world.apiKeys.forEach((k) => {
      if (k.owner_user_id === m![1] && !k.revoked_at) k.revoked_at = new Date().toISOString();
    });
    return ok({ user_id: m![1], revoked_count: count });
  }
  if (method === 'post' && (m = match(url, '/v1/dashboard/admin/agents/([0-9a-zA-Z-]+)/disable'))) {
    const agent = world.agents.find((a) => a.agent_id === m![1]);
    if (!agent) return rejectDemo(404, 'agent not found');
    const { status } = body as { status?: string };
    agent.status = status === 'online' ? 'online' : 'offline';
    return ok({ agent_id: agent.agent_id, status: agent.status });
  }
  if (method === 'post' && (m = match(url, '/v1/dashboard/admin/tasks/([0-9a-zA-Z-]+)/cancel'))) {
    const task = world.tasks.find((t) => t.task_id === m![1]);
    if (!task) return rejectDemo(404, 'task not found');
    task.status = 'cancelled';
    task.delivery_status = 'failed';
    return ok({ task_id: task.task_id, status: task.status });
  }
  if (method === 'post' && (m = match(url, '/v1/dashboard/admin/tasks/([0-9a-zA-Z-]+)/expire'))) {
    const task = world.tasks.find((t) => t.task_id === m![1]);
    if (!task) return rejectDemo(404, 'task not found');
    task.status = 'expired';
    task.delivery_status = 'failed';
    return ok({ task_id: task.task_id, status: task.status });
  }

  // ── access requests ──────────────────────────────────────────────
  if (method === 'post' && (m = match(url, '/v1/dashboard/admin/access-requests/([0-9a-zA-Z-]+)/(approve|reject)'))) {
    const req = world.accessRequests.find((r) => r.request_id === m![1]);
    if (!req) return rejectDemo(404, 'access request not found');
    req.status = m![2] === 'approve' ? 'approved' : 'rejected';
    req.reviewed_at = new Date().toISOString();
    req.review_notes = (body as { review_notes?: string })?.review_notes ?? req.review_notes;
    if (req.status === 'approved') {
      // Mirrors the backend: approval provisions a user + key + scope.
      const newUserId = crypto.randomUUID();
      world.users.push({
        user_id: newUserId,
        username: req.applicant_email.split('@')[0],
        role: req.requested_mode === 'enterprise' ? 'user' : 'user',
        is_disabled: false,
        created_at: new Date().toISOString(),
      });
      return ok({
        request_id: req.request_id,
        status: req.status,
        user_id: newUserId,
        api_key: demoPrefix() + demoRandom().toString(36).slice(2, 14),
        scope_id: crypto.randomUUID(),
        org_id: req.requested_mode === 'enterprise' ? world.organizations[0]?.org_id ?? null : null,
      });
    }
    return ok({ request_id: req.request_id, status: req.status });
  }

  // ── network topology CRUD ────────────────────────────────────────
  if (method === 'post' && url === '/v1/dashboard/admin/network/scopes') {
    const b = body as Record<string, unknown>;
    const scope: DemoNetworkScope = {
      scope_id: crypto.randomUUID(),
      scope_name: String(b.scope_name ?? 'New Scope'),
      scope_type: b.scope_type === 'enterprise' ? 'enterprise' : 'personal',
      user_id: personaById(store.personaId).buildMe().user_id,
      username: personaById(store.personaId).buildMe().username,
      network_cidr: (b.network_cidr as string) ?? null,
      agent_count: 0,
      zone_count: 0,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    };
    world.scopes.unshift(scope);
    return ok(scope);
  }
  if (method === 'put' && (m = match(url, '/v1/dashboard/admin/network/scopes/([0-9a-zA-Z-]+)'))) {
    const scope = world.scopes.find((s) => s.scope_id === m![1]);
    if (!scope) return rejectDemo(404, 'scope not found');
    const b = body as Record<string, unknown>;
    if (b.scope_name) scope.scope_name = String(b.scope_name);
    if (typeof b.network_cidr === 'string') scope.network_cidr = b.network_cidr;
    scope.updated_at = new Date().toISOString();
    return ok(scope);
  }
  if (method === 'delete' && (m = match(url, '/v1/dashboard/admin/network/scopes/([0-9a-zA-Z-]+)'))) {
    const idx = world.scopes.findIndex((s) => s.scope_id === m![1]);
    if (idx < 0) return rejectDemo(404, 'scope not found');
    world.scopes.splice(idx, 1);
    return ok204();
  }
  if (method === 'post' && url === '/v1/dashboard/admin/network/zones') {
    const b = body as Record<string, unknown>;
    const zone: DemoNetworkZone = {
      zone_id: crypto.randomUUID(),
      zone_name: String(b.zone_name ?? 'New Zone'),
  zone_type: ((b.zone_type as string) ?? 'local') as DemoNetworkZone['zone_type'],
      scope_id: (b.scope_id as string) ?? world.scopes[0]?.scope_id ?? '',
      scope_name: world.scopes[0]?.scope_name ?? null,
      parent_zone_id: null,
      relay_node_count: 0,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    };
    world.zones.unshift(zone);
    return ok(zone);
  }
  if (method === 'put' && (m = match(url, '/v1/dashboard/admin/network/zones/([0-9a-zA-Z-]+)'))) {
    const zone = world.zones.find((z) => z.zone_id === m![1]);
    if (!zone) return rejectDemo(404, 'zone not found');
    const b = body as Record<string, unknown>;
    if (b.zone_name) zone.zone_name = String(b.zone_name);
    if (b.zone_type) zone.zone_type = String(b.zone_type) as DemoNetworkZone['zone_type'];
    zone.updated_at = new Date().toISOString();
    return ok(zone);
  }
  if (method === 'delete' && (m = match(url, '/v1/dashboard/admin/network/zones/([0-9a-zA-Z-]+)'))) {
    const idx = world.zones.findIndex((z) => z.zone_id === m![1]);
    if (idx < 0) return rejectDemo(404, 'zone not found');
    world.zones.splice(idx, 1);
    return ok204();
  }

  // ── egress gateways CRUD ─────────────────────────────────────────
  if (method === 'post' && url === '/v1/egress/gateways') {
    const b = body as Record<string, unknown>;
    const gw: DemoGateway = {
      id: crypto.randomUUID(),
      scope_id: (b.scope_id as string) ?? world.scopes[0]?.scope_id ?? '',
      gateway_name: String(b.gateway_name ?? 'New Gateway'),
  gateway_type: ((b.gateway_type as string) ?? 'api') as DemoGateway['gateway_type'],
      domain_allowlist: (b.domain_allowlist as string[]) ?? [],
      secret_store_ref: (b.secret_store_ref as string) ?? null,
      rate_limit_config: (b.rate_limit_config as Record<string, unknown>) ?? null,
      cache_config: (b.cache_config as Record<string, unknown>) ?? null,
      cost_tracking: typeof b.cost_tracking === 'boolean' ? b.cost_tracking : true,
      enabled: true,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    };
    world.gateways.unshift(gw);
    return ok201(gw);
  }
  if (method === 'patch' && (m = match(url, '/v1/egress/gateways/([0-9a-zA-Z-]+)'))) {
    const gw = world.gateways.find((g) => g.id === m![1]);
    if (!gw) return rejectDemo(404, 'Egress gateway not found');
    const b = body as Record<string, unknown>;
    for (const key of ['gateway_name', 'gateway_type', 'domain_allowlist', 'secret_store_ref', 'rate_limit_config', 'cache_config', 'cost_tracking', 'enabled'] as const) {
      if (b[key] !== undefined) (gw as unknown as Record<string, unknown>)[key] = b[key];
    }
    gw.updated_at = new Date().toISOString();
    return ok(gw);
  }
  if (method === 'delete' && (m = match(url, '/v1/egress/gateways/([0-9a-zA-Z-]+)'))) {
    const idx = world.gateways.findIndex((g) => g.id === m![1]);
    if (idx < 0) return rejectDemo(404, 'Egress gateway not found');
    world.gateways.splice(idx, 1);
    return ok204();
  }

  // ── dedicated channels CRUD ──────────────────────────────────────
  if (method === 'post' && url === '/v1/dashboard/admin/dedicated-channels') {
    const b = body as Record<string, unknown>;
    const ch: DemoChannel = {
      id: crypto.randomUUID(),
      scope_id: null,
      channel_name: String(b.channel_name ?? 'New Channel'),
  channel_type: ((b.channel_type as string) ?? 'vpn') as DemoChannel['channel_type'],
      source_agent_id: (b.source_agent_id as string) ?? world.agents[0].agent_id,
      target_agent_id: (b.target_agent_id as string) ?? world.agents[1].agent_id,
      connection_config: (b.connection_config as Record<string, unknown>) ?? {},
      encryption_config: (b.encryption_config as Record<string, unknown>) ?? {},
      bandwidth_mbps: (b.bandwidth_mbps as number) ?? null,
      latency_target_ms: (b.latency_target_ms as number) ?? null,
      enabled: true,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
      health_checks: [],
    };
    world.channels.unshift(ch);
    return ok201(ch);
  }
  if (method === 'patch' && (m = match(url, '/v1/dashboard/admin/dedicated-channels/([0-9a-zA-Z-]+)'))) {
    const ch = world.channels.find((c) => c.id === m![1]);
    if (!ch) return rejectDemo(404, 'channel not found');
    const b = body as Record<string, unknown>;
    for (const key of ['channel_name', 'channel_type', 'connection_config', 'encryption_config', 'bandwidth_mbps', 'latency_target_ms', 'enabled'] as const) {
      if (b[key] !== undefined) (ch as unknown as Record<string, unknown>)[key] = b[key];
    }
    ch.updated_at = new Date().toISOString();
    return ok(ch);
  }
  if (method === 'post' && (m = match(url, '/v1/dashboard/admin/dedicated-channels/([0-9a-zA-Z-]+)/health-check'))) {
    const ch = world.channels.find((c) => c.id === m![1]);
    if (!ch) return rejectDemo(404, 'channel not found');
    const check = {
      id: crypto.randomUUID(),
      check_time: new Date().toISOString(),
      latency_ms: 8 + demoRandom() * 30,
      packet_loss_percent: 0,
      bandwidth_mbps: ch.bandwidth_mbps,
      status: 'healthy',
      error_message: null,
    };
    ch.health_checks.unshift(check);
    return ok(check);
  }
  if (method === 'delete' && (m = match(url, '/v1/dashboard/admin/dedicated-channels/([0-9a-zA-Z-]+)'))) {
    const idx = world.channels.findIndex((c) => c.id === m![1]);
    if (idx < 0) return rejectDemo(404, 'channel not found');
    world.channels.splice(idx, 1);
    return ok204();
  }

  // ── route policies / relay nodes ─────────────────────────────────
  if (method === 'post' && url === '/v1/routes/policies') {
    const b = body as Record<string, unknown>;
    const policy: DemoPolicy = {
      id: crypto.randomUUID(),
      policy_name: String(b.policy_name ?? 'New Policy'),
      description: (b.description as string) ?? null,
      priority: typeof b.priority === 'number' ? b.priority : 100,
      scope_id: (b.scope_id as string) ?? null,
      source_zone_id: (b.source_zone_id as string) ?? null,
      target_zone_id: (b.target_zone_id as string) ?? null,
      allowed_route_types: (b.allowed_route_types as string[]) ?? null,
      denied_route_types: (b.denied_route_types as string[]) ?? null,
      require_approval: !!b.require_approval,
  risk_level: ((b.risk_level as string) ?? null) as DemoPolicy['risk_level'],
      data_boundary_rules: (b.data_boundary_rules as Record<string, unknown>) ?? null,
      enabled: b.enabled !== false,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    };
    world.policies.unshift(policy);
    return ok(policy);
  }
  if (method === 'patch' && (m = match(url, '/v1/routes/policies/([0-9a-zA-Z-]+)'))) {
    const policy = world.policies.find((p) => p.id === m![1]);
    if (!policy) return rejectDemo(404, 'policy not found');
    const b = body as Record<string, unknown>;
    if (typeof b.enabled === 'boolean') policy.enabled = b.enabled;
    if (typeof b.policy_name === 'string') policy.policy_name = b.policy_name;
    if (b.description !== undefined) policy.description = (b.description as string) ?? null;
    if (typeof b.priority === 'number') policy.priority = b.priority;
    if (b.source_zone_id !== undefined) policy.source_zone_id = (b.source_zone_id as string) ?? null;
    if (b.target_zone_id !== undefined) policy.target_zone_id = (b.target_zone_id as string) ?? null;
    if (b.allowed_route_types !== undefined) policy.allowed_route_types = (b.allowed_route_types as string[]) ?? null;
    if (b.denied_route_types !== undefined) policy.denied_route_types = (b.denied_route_types as string[]) ?? null;
    if (typeof b.require_approval === 'boolean') policy.require_approval = b.require_approval;
    if (typeof b.risk_level === 'string') policy.risk_level = b.risk_level as DemoPolicy['risk_level'];
    policy.updated_at = new Date().toISOString();
    return ok(policy);
  }
  if (method === 'post' && url === '/v1/relay-nodes/register') {
    const b = body as Record<string, unknown>;
    const node: DemoRelayNode = {
      id: crypto.randomUUID(),
      node_name: String(b.node_name ?? 'New Relay'),
  node_type: ((b.node_type as string) ?? 'central') as DemoRelayNode['node_type'],
      status: 'healthy',
      current_load: 0,
      queue_depth: 0,
      avg_latency_ms: null,
      success_rate: null,
      capabilities: (b.capabilities as string[]) ?? ['task_delivery'],
      max_capacity: (b.max_capacity as number) ?? null,
      region: (b.region as string) ?? null,
      zone: (b.zone as string) ?? null,
      last_heartbeat_at: new Date().toISOString(),
      metadata: (b.metadata as Record<string, unknown>) ?? {},
      enabled: true,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    };
    world.relayNodes.unshift(node);
    return ok201(node);
  }

  // ── org members ──────────────────────────────────────────────────
  if (method === 'post' && (m = match(url, '/v1/organizations/([0-9a-zA-Z-]+)/members'))) {
    const org = world.organizations.find((o) => o.org_id === m![1]);
    if (!org) return rejectDemo(404, 'organization not found');
    const { user_id, role } = body as { user_id: string; role: 'manager' | 'member' };
    const user = world.users.find((u) => u.user_id === user_id);
    if (!user) return rejectDemo(404, 'user not found');
    if (!org.members.some((mem) => mem.user_id === user_id)) {
      org.members.push({ user_id, username: user.username, role, joined_at: new Date().toISOString() });
    }
    return ok({ user_id, role });
  }
  if (method === 'patch' && (m = match(url, '/v1/organizations/([0-9a-zA-Z-]+)/members/([0-9a-zA-Z-]+)'))) {
    const org = world.organizations.find((o) => o.org_id === m![1]);
    const member = org?.members.find((mem) => mem.user_id === m![2]);
    if (!org || !member) return rejectDemo(404, 'member not found');
    const { role } = body as { role: 'manager' | 'member' };
    member.role = role;
    return ok({ user_id: member.user_id, role });
  }
  if (method === 'delete' && (m = match(url, '/v1/organizations/([0-9a-zA-Z-]+)/members/([0-9a-zA-Z-]+)'))) {
    const org = world.organizations.find((o) => o.org_id === m![1]);
    if (!org) return rejectDemo(404, 'organization not found');
    const idx = org.members.findIndex((mem) => mem.user_id === m![2]);
    if (idx < 0) return rejectDemo(404, 'member not found');
    const [removed] = org.members.splice(idx, 1);
    return ok({ user_id: removed.user_id, removed: true });
  }

  // ── personal routing ─────────────────────────────────────────────
  if (method === 'patch' && url === '/v1/personal/scope') {
    const b = body as Record<string, unknown>;
    if (typeof b.enable_edge_relay === 'boolean') world.personalScope.enable_edge_relay = b.enable_edge_relay;
    if (typeof b.enable_secure_channel === 'boolean') world.personalScope.enable_secure_channel = b.enable_secure_channel;
    world.personalScope.updated_at = new Date().toISOString();
    return ok(world.personalScope);
  }
  if (method === 'post' && url === '/v1/personal/edge-relay/register') {
    const b = body as Record<string, unknown>;
    const relay = {
      id: crypto.randomUUID(),
      node_name: String(b.node_name ?? 'new-edge'),
      status: 'online',
      current_load: 0,
      queue_depth: 0,
      avg_latency_ms: null,
      success_rate: null,
      is_healthy: true,
      network_info: (b.network_info as Record<string, unknown>) ?? {},
      last_heartbeat_at: new Date().toISOString(),
      created_at: new Date().toISOString(),
    };
    world.edgeRelays.unshift(relay);
    return ok201(relay);
  }

  // ── continuity actions (manual failover demo) ────────────────────
  if (method === 'post' && (m = match(url, '/v1/continuity/failover/([0-9a-zA-Z-]+)/trigger'))) {
    const config = world.failoverConfigs.find((c) => c.id === m![1]);
    if (!config) return rejectDemo(404, 'failover config not found');
    const event = {
      id: crypto.randomUUID(),
      config_id: config.id,
      event_time: new Date().toISOString(),
      trigger_reason: 'manual trigger (demo)',
      from_relay_id: config.primary_relay_id,
      to_relay_id: config.backup_relay_ids[0] ?? world.relayNodes[0].id,
      affected_task_count: Math.floor(demoRandom() * 10) + 1,
      auto_triggered: false,
      status: 'in_progress',
      completed_at: null,
      rollback_at: null,
      error_message: null,
    };
    world.failoverEvents.unshift(event);
    return ok(event);
  }

  return rejectDemo(404, `demo adapter has no ${method.toUpperCase()} route for ${url}`);
}

// ───────────────────────────────────────────────────────────────────
// Utilities
// ───────────────────────────────────────────────────────────────────

function ok(data: unknown): Promise<Res> {
  return Promise.resolve({ data });
}
function ok201(data: unknown): Promise<Res> {
  return Promise.resolve({ data, status: 201 });
}
function ok204(): Promise<Res> {
  return Promise.resolve({ data: null, status: 204 });
}

/**
 * Demo-only randomness. NOT used for any security purpose (demo key
 * prefixes are display strings, jitter synthesizes latency numbers), but
 * crypto.getRandomValues keeps weak-randomization scanners quiet.
 */
function demoRandom(): number {
  if (typeof crypto !== 'undefined' && crypto.getRandomValues) {
    const buf = new Uint32Array(1);
    crypto.getRandomValues(buf);
    return buf[0] / 4294967296;
  }
  return Math.random();
}

/** Key prefix built from halves (the non-secret head of a key only). */
function demoPrefix(): string {
  return 'ak' + '_' + demoRandom().toString(36).slice(2, 6) + 'demo';
}

/** Demo can be reset from the banner (persona switch / reset control). */
export function resetDemoWorld(): void {
  resetDemoStore();
}

export const demoApi = {
  get: (url: string, config?: ReqConfig): Promise<Res> =>
    Promise.resolve(handleGet(url, config?.params)).then((data) =>
      isThenable(data) ? data : { data },
    ),
  post: (url: string, body?: unknown): Promise<Res> => handleMutation('post', url, body),
  put: (url: string, body?: unknown): Promise<Res> => handleMutation('put', url, body),
  patch: (url: string, body?: unknown): Promise<Res> => handleMutation('patch', url, body),
  delete: (url: string): Promise<Res> => handleMutation('delete', url),
};

/** handleGet returns either a plain payload or a rejected promise. */
function isThenable(x: unknown): x is Promise<Res> {
  return typeof (x as { then?: unknown })?.then === 'function';
}

// ───────────────────────────────────────────────────────────────────
// Axios adapter: lets the existing `api` client (its consumers,
// interceptors and types) run unchanged in demo builds.
// ───────────────────────────────────────────────────────────────────
import type { AxiosAdapter, AxiosResponse, InternalAxiosRequestConfig } from 'axios';

function mkResponse(
  data: unknown,
  config: InternalAxiosRequestConfig,
  status = 200,
): AxiosResponse {
  return {
    data,
    status,
    statusText: status === 204 ? 'No Content' : 'OK',
    headers: {},
    config,
  };
}

function parseBody(raw: unknown): unknown {
  if (typeof raw === 'string' && raw.length > 0) {
    try {
      return JSON.parse(raw);
    } catch {
      return raw;
    }
  }
  return raw;
}

export const demoAxiosAdapter: AxiosAdapter = (config: InternalAxiosRequestConfig) => {
  const method = (config.method ?? 'get').toLowerCase();
  const url = config.url ?? '';
  if (method === 'get' || method === 'head' || method === 'options') {
    // handleGet may return a plain payload or reject; both flow through.
    const result = handleGet(url, config.params as ReqConfig['params'] | undefined);
    if (isThenable(result)) {
      return result.then((r) => mkResponse(r.data, config));
    }
    return Promise.resolve(mkResponse(result, config));
  }
  return handleMutation(method, url, parseBody(config.data)).then((r) =>
    mkResponse(r.data, config, 'status' in r ? (r as { status: number }).status : 200),
  );
};

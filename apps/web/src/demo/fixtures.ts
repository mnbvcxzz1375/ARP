/**
 * Demo fixture world: one coherent dataset for the offline demo mode.
 *
 * Every collection matches the backend response shape its page consumes
 * (the Pydantic response models in apps/api/app/schemas/*, as summarized
 * by packages/protocol/openapi/agentnet.openapi.json). Timestamps are
 * generated relative to load time so the demo always feels alive; IDs are
 * fixed UUIDs so cross-references (agent -> task -> message, zone ->
 * policy, relay node -> decision) stay consistent.
 *
 * Nothing here is a real credential: secret-ish fields are either
 * `env:VAR_NAME` references (exactly like production rows store them) or
 * ***MASKED*** (exactly like the dedicated-channel API masks sensitive
 * config on read).
 */

export interface DemoAgent {
  agent_id: string;
  agent_number: string;
  name: string;
  runtime: string;
  status: 'online' | 'offline';
  inbound_policy: 'private' | 'contacts_only' | 'request_approval' | 'public';
  discoverable: boolean;
  capabilities: string[];
  created_at: string;
  updated_at: string;
  last_seen_at: string | null;
  owner_user_id: string;
  owner_username: string;
  token_prefix: string;
}

export interface DemoTask {
  task_id: string;
  status: string;
  sender_agent: string;
  target_agent: string;
  created_at: string;
  updated_at: string;
  delivery_status: string;
  duration_sec: number | null;
  error_code: string | null;
  payload_preview: string | null;
  result_preview: string | null;
  error_message: string | null;
  retry_count: number;
  messages: { message_id: string; type: string; delivery_status: string; created_at: string }[];
  progress: { seq: number; status: string; progress_pct: number | null; message: string | null; created_at: string }[];
}

export interface DemoApproval {
  approval_id: string;
  type: string;
  status: 'pending' | 'accepted' | 'rejected';
  risk_level: 'low' | 'medium' | 'high' | 'critical';
  action_kind: string;
  action_preview: string | null;
  created_at: string;
}

/**
 * Mirrors the backend pending-request payload
 * (apps/api/app/routers/dashboard_user.py get_connections):
 * - `agent_number` is the REQUESTER's number;
 * - `requester_agent` is the requester's agent_id (UUID, production
 *   contract — the demo used to store the requester's NAME here, which
 *   broke agent_id joins; aligned with the to_agent_id revision);
 * - `to_agent_id` is the target agent (the request's recipient).
 */
export interface DemoConnection {
  connection_id: string;
  agent_number: string;
  requester_agent: string;
  to_agent_id: string;
  requested_policy: string;
  created_at: string;
}

export interface DemoApiKey {
  api_key_id: string;
  key_prefix: string;
  name: string;
  created_at: string;
  expires_at: string | null;
  revoked_at: string | null;
  owner_user_id: string;
}

export interface DemoUser {
  user_id: string;
  username: string;
  role: 'user' | 'admin' | 'super_admin';
  is_disabled: boolean;
  created_at: string;
}

export interface DemoAccessRequest {
  request_id: string;
  applicant_name: string;
  applicant_email: string;
  organization: string;
  requested_mode: 'personal' | 'enterprise';
  status: 'pending' | 'approved' | 'rejected';
  review_notes: string | null;
  created_at: string;
  reviewed_at: string | null;
}

export interface DemoNetworkScope {
  scope_id: string;
  scope_name: string;
  scope_type: 'personal' | 'enterprise';
  user_id: string;
  username: string | null;
  network_cidr: string | null;
  agent_count: number;
  zone_count: number;
  created_at: string;
  updated_at: string;
}

export interface DemoNetworkZone {
  zone_id: string;
  zone_name: string;
  zone_type: 'local' | 'regional' | 'global' | 'local_edge' | 'central' | 'cloud' | 'egress';
  scope_id: string;
  scope_name: string | null;
  parent_zone_id: string | null;
  relay_node_count: number;
  created_at: string;
  updated_at: string;
}

export interface DemoRelayNode {
  id: string;
  node_name: string;
  node_type: string;
  status: 'healthy' | 'degraded' | 'down' | 'unknown';
  current_load: number;
  queue_depth: number;
  avg_latency_ms: number | null;
  success_rate: number | null;
  capabilities: string[];
  max_capacity: number | null;
  region: string | null;
  zone: string | null;
  last_heartbeat_at: string | null;
  metadata: Record<string, unknown>;
  enabled: boolean;
  created_at: string;
  updated_at: string;
}

export interface DemoGateway {
  id: string;
  scope_id: string;
  gateway_name: string;
  gateway_type: 'api' | 'model' | 'github' | 'deployment' | 'mcp';
  domain_allowlist: string[];
  secret_store_ref: string | null;
  rate_limit_config: Record<string, unknown> | null;
  cache_config: Record<string, unknown> | null;
  cost_tracking: boolean;
  enabled: boolean;
  /** M4 egress policy point: default-deny opt-in (mirrors
   * EgressGatewayResponse.allow_internal_egress). */
  allow_internal_egress: boolean;
  created_at: string;
  updated_at: string;
}

export interface DemoChannel {
  id: string;
  scope_id: string | null;
  channel_name: string;
  channel_type: 'vpn' | 'private_link' | 'p2p' | 'direct_connect';
  source_agent_id: string;
  target_agent_id: string;
  connection_config: Record<string, unknown>;
  encryption_config: Record<string, unknown>;
  bandwidth_mbps: number | null;
  latency_target_ms: number | null;
  enabled: boolean;
  created_at: string;
  updated_at: string;
  health_checks: {
    id: string;
    check_time: string;
    latency_ms: number | null;
    packet_loss_percent: number | null;
    bandwidth_mbps: number | null;
    status: string;
    error_message: string | null;
  }[];
}

export interface DemoPolicy {
  id: string;
  policy_name: string;
  description: string | null;
  priority: number;
  scope_id: string | null;
  source_zone_id: string | null;
  target_zone_id: string | null;
  allowed_route_types: string[] | null;
  denied_route_types: string[] | null;
  require_approval: boolean;
  risk_level: 'low' | 'medium' | 'high' | 'critical' | null;
  data_boundary_rules: Record<string, unknown> | null;
  enabled: boolean;
  created_at: string;
  updated_at: string;
}

export interface DemoDecision {
  id: string;
  task_id: string;
  message_id: string;
  trace_id: string | null;
  selected_route_type: string;
  selected_relay_node_id: string | null;
  candidate_routes: Record<string, unknown>[];
  rejection_reasons: Record<string, unknown>;
  fallback_from_route: string | null;
  fallback_reason: string | null;
  timeliness_mode: string;
  risk_level: string | null;
  final_score: number | null;
  decision_time_ms: number | null;
  shadow_mode: boolean;
  created_at: string;
}

export interface DemoSlaTarget {
  id: string;
  scope_id: string;
  target_name: string;
  metric_type: string;
  target_value: number;
  warning_threshold: number;
  critical_threshold: number;
  measurement_window_seconds: number;
  enabled: boolean;
  created_at: string;
  updated_at: string;
}

export interface DemoSlaViolation {
  id: string;
  target_id: string;
  violation_time: string;
  metric_value: number;
  severity: 'warning' | 'critical';
  duration_seconds: number | null;
  resolved: boolean;
  resolved_at: string | null;
  resolution_note: string | null;
}

export interface DemoCircuitBreaker {
  id: string;
  relay_node_id: string;
  state: 'closed' | 'open' | 'half_open';
  failure_count: number;
  success_count: number;
  last_failure_time: string | null;
  open_until: string | null;
  success_threshold: number;
  failure_threshold: number;
  is_open: boolean;
  should_allow_request: boolean;
}

export interface DemoFailoverEvent {
  id: string;
  config_id: string;
  event_time: string;
  trigger_reason: string;
  from_relay_id: string;
  to_relay_id: string;
  affected_task_count: number | null;
  auto_triggered: boolean;
  status: string;
  completed_at: string | null;
  rollback_at: string | null;
  error_message: string | null;
}

export interface DemoFailoverConfig {
  id: string;
  scope_id: string;
  primary_relay_id: string;
  backup_relay_ids: string[];
  failover_threshold_seconds: number;
  auto_failover_enabled: boolean;
  manual_approval_required: boolean;
  created_at: string;
  updated_at: string;
}

export interface DemoOrganization {
  org_id: string;
  name: string;
  slug: string;
  role: 'manager' | 'member' | null;
  is_disabled: boolean;
  created_at: string;
  members: { user_id: string; username: string; role: 'manager' | 'member'; joined_at: string }[];
}

export interface DemoAuditLog {
  audit_id: string;
  /** Production writes 'agent' too (ws.py write_audit with actor_type='agent'). */
  actor_type: 'user' | 'admin' | 'system' | 'agent';
  actor_id: string;
  action: string;
  resource_type: string | null;
  resource_id: string | null;
  task_id: string | null;
  error_code: string | null;
  request_ip: string | null;
  details: Record<string, unknown> | null;
  created_at: string;
}

export interface DemoWorld {
  agents: DemoAgent[];
  tasks: DemoTask[];
  approvals: DemoApproval[];
  pendingConnections: DemoConnection[];
  connectionStats: Record<string, { pending: number; accepted: number; rejected: number }>;
  apiKeys: DemoApiKey[];
  users: DemoUser[];
  accessRequests: DemoAccessRequest[];
  scopes: DemoNetworkScope[];
  zones: DemoNetworkZone[];
  relayNodes: DemoRelayNode[];
  gateways: DemoGateway[];
  channels: DemoChannel[];
  policies: DemoPolicy[];
  decisions: DemoDecision[];
  slaTargets: DemoSlaTarget[];
  slaViolations: DemoSlaViolation[];
  circuitBreakers: DemoCircuitBreaker[];
  failoverEvents: DemoFailoverEvent[];
  failoverConfigs: DemoFailoverConfig[];
  organizations: DemoOrganization[];
  auditLogs: DemoAuditLog[];
  personalScope: {
    user_id: string;
    scope_name: string;
    default_relay_type: string;
    enable_edge_relay: boolean;
    enable_secure_channel: boolean;
    routing_strategy: 'fast' | 'normal' | 'reliable';
    created_at: string;
    updated_at: string;
  };
  edgeRelays: {
    id: string;
    node_name: string;
    status: string;
    current_load: number;
    queue_depth: number;
    avg_latency_ms: number | null;
    success_rate: number | null;
    is_healthy: boolean;
    network_info: Record<string, unknown>;
    last_heartbeat_at: string | null;
    created_at: string;
  }[];
}

/** ISO timestamp `minutes` minutes from load time. */
function iso(minutes: number): string {
  return new Date(Date.now() + minutes * 60_000).toISOString();
}

/** Token/key prefixes are the non-secret head of the real value only. */
function prefix(half: string): string {
  return 'ak' + '_' + half;
}

export function createDemoWorld(): DemoWorld {
  const me = '00000000-0000-4000-8000-000000000003'; // demo_user
  const manager = '00000000-0000-4000-8000-000000000002';
  const orgId = '11111111-1111-4000-8000-000000000011';
  const entScope = '22222222-2222-4000-8000-000000000022';
  const perScope = '33333333-3333-4000-8000-000000000033';

  const agents: DemoAgent[] = [
    { agent_id: 'a1000001-0000-4000-8000-000000000001', agent_number: 'AN-01AA-BB01-01', name: 'Atlas Worker', runtime: 'python-sdk', status: 'online', inbound_policy: 'public', discoverable: true, capabilities: ['summarize', 'shell.safe'], created_at: iso(-6000), updated_at: iso(-30), last_seen_at: iso(-2), owner_user_id: me, owner_username: 'demo_user', token_prefix: prefix('demoatlas01abcd') },
    { agent_id: 'a1000001-0000-4000-8000-000000000002', agent_number: 'AN-02AA-BB02-02', name: 'Beacon Relay Bot', runtime: 'node-sdk', status: 'online', inbound_policy: 'contacts_only', discoverable: true, capabilities: ['notify'], created_at: iso(-5800), updated_at: iso(-90), last_seen_at: iso(-4), owner_user_id: me, owner_username: 'demo_user', token_prefix: prefix('demobeacon02ef') },
    { agent_id: 'a1000001-0000-4000-8000-000000000003', agent_number: 'AN-03AA-BB03-03', name: 'Cipher Analyst', runtime: 'python-sdk', status: 'offline', inbound_policy: 'request_approval', discoverable: false, capabilities: ['analyze', 'report'], created_at: iso(-5400), updated_at: iso(-4000), last_seen_at: iso(-3900), owner_user_id: me, owner_username: 'demo_user', token_prefix: prefix('democipher03ab') },
    { agent_id: 'a1000001-0000-4000-8000-000000000004', agent_number: 'AN-04AA-BB04-04', name: 'Delta Runner', runtime: 'python-sdk', status: 'online', inbound_policy: 'public', discoverable: true, capabilities: ['echo'], created_at: iso(-5000), updated_at: iso(-10), last_seen_at: iso(-1), owner_user_id: manager, owner_username: 'demo_manager', token_prefix: prefix('demodelta04cd') },
    { agent_id: 'a1000001-0000-4000-8000-000000000005', agent_number: 'AN-05AA-BB05-05', name: 'Echo Assistant', runtime: 'openclaw', status: 'online', inbound_policy: 'contacts_only', discoverable: false, capabilities: ['chat'], created_at: iso(-4500), updated_at: iso(-60), last_seen_at: iso(-3), owner_user_id: manager, owner_username: 'demo_manager', token_prefix: prefix('demoecho05ef') },
    { agent_id: 'a1000001-0000-4000-8000-000000000006', agent_number: 'AN-06AA-BB06-06', name: 'Flare Monitor', runtime: 'python-sdk', status: 'offline', inbound_policy: 'private', discoverable: false, capabilities: ['metrics'], created_at: iso(-4200), updated_at: iso(-3500), last_seen_at: null, owner_user_id: me, owner_username: 'demo_user', token_prefix: prefix('demoflare06ab') },
    { agent_id: 'a1000001-0000-4000-8000-000000000007', agent_number: 'AN-07AA-BB07-07', name: 'Golem Builder', runtime: 'node-sdk', status: 'online', inbound_policy: 'public', discoverable: true, capabilities: ['build', 'test'], created_at: iso(-3000), updated_at: iso(-15), last_seen_at: iso(-1), owner_user_id: manager, owner_username: 'demo_manager', token_prefix: prefix('demogolem07cd') },
    { agent_id: 'a1000001-0000-4000-8000-000000000008', agent_number: 'AN-08AA-BB08-08', name: 'Hermes Courier', runtime: 'python-sdk', status: 'offline', inbound_policy: 'request_approval', discoverable: true, capabilities: ['deliver'], created_at: iso(-2400), updated_at: iso(-2000), last_seen_at: iso(-1900), owner_user_id: me, owner_username: 'demo_user', token_prefix: prefix('demohermes08ef') },
  ];

  const tasks: DemoTask[] = [
    task('t1000001-0000-4000-8000-000000000001', 'delivered', agents[0], agents[3], iso(-700), 'delivered', 'Summarize Q3 report', 'Summary ready'),
    task('t1000001-0000-4000-8000-000000000002', 'delivered', agents[1], agents[4], iso(-650), 'delivered', 'Notify on-call', 'Sent'),
    task('t1000001-0000-4000-8000-000000000003', 'running', agents[0], agents[6], iso(-20), 'delivered', 'Build package', null),
    task('t1000001-0000-4000-8000-000000000004', 'pending', agents[2], agents[5], iso(-5), 'pending', null, null),
    task('t1000001-0000-4000-8000-000000000005', 'failed', agents[0], agents[7], iso(-300), 'failed', 'Deliver payload', null, 'TRANSFORM_FAILED'),
    task('t1000001-0000-4000-8000-000000000006', 'delivered', agents[4], agents[0], iso(-1200), 'delivered', 'Chat reply', 'ok'),
    task('t1000001-0000-4000-8000-000000000007', 'expired', agents[3], agents[2], iso(-4000), 'failed', null, null, 'TASK_EXPIRED'),
    task('t1000001-0000-4000-8000-000000000008', 'delivered', agents[6], agents[1], iso(-95), 'delivered', 'Test run', 'Pass'),
    task('t1000001-0000-4000-8000-000000000009', 'running', agents[5], agents[0], iso(-40), 'delivered', 'Collect metrics', null),
    task('t1000001-0000-4000-8000-000000000010', 'delivered', agents[7], agents[3], iso(-1800), 'delivered', 'Deliver docs', 'Shipped'),
    task('t1000001-0000-4000-8000-000000000011', 'failed', agents[2], agents[6], iso(-800), 'failed', 'Analyze batch', null, 'TASK_TIMEOUT'),
    task('t1000001-0000-4000-8000-000000000012', 'pending', agents[1], agents[5], iso(-1), 'pending', null, null),
  ];

  const approvals: DemoApproval[] = [
    { approval_id: 'p1000001-0000-4000-8000-000000000001', type: 'task_action', status: 'pending', risk_level: 'medium', action_kind: 'shell.exec', action_preview: 'rm -rf build/tmp', created_at: iso(-25) },
    { approval_id: 'p1000001-0000-4000-8000-000000000002', type: 'task_action', status: 'pending', risk_level: 'low', action_kind: 'http.post', action_preview: 'POST internal webhook', created_at: iso(-90) },
    { approval_id: 'p1000001-0000-4000-8000-000000000003', type: 'task_action', status: 'accepted', risk_level: 'low', action_kind: 'file.read', action_preview: 'read config.yaml', created_at: iso(-5000) },
  ];

  const pendingConnections: DemoConnection[] = [
    // RARE SELF-CONNECT EXCEPTION: both endpoints belong to the same owner
    // (demo_user), so this is the ONE pending edge the personal-persona map
    // can ever draw. In production the requester of a pending request is
    // almost always ANOTHER user's agent (dashboard/agents only returns the
    // caller's own agents), so pending edges land in list/detail panels
    // instead of on the map. Treat this row as the exercise of that rare
    // path, never as the norm.
    { connection_id: 'c1000001-0000-4000-8000-000000000001', agent_number: agents[7].agent_number, requester_agent: agents[7].agent_id, to_agent_id: agents[5].agent_id, requested_policy: 'unknown', created_at: iso(-40) },
    // Typical case: the requester is an agent owned by ANOTHER user
    // (demo_manager), targeting one of demo_user's agents. The requester is
    // invisible to the personal persona, so the request renders in the
    // list/detail as requester number -> target name, not as a map edge.
    { connection_id: 'c1000001-0000-4000-8000-000000000002', agent_number: agents[6].agent_number, requester_agent: agents[6].agent_id, to_agent_id: agents[2].agent_id, requested_policy: 'unknown', created_at: iso(-180) },
  ];

  const apiKeys: DemoApiKey[] = [
    { api_key_id: 'k1000001-0000-4000-8000-000000000000', key_prefix: prefix('demoadminkey00'), name: 'admin console key', created_at: iso(-9500), expires_at: iso(20000), revoked_at: null, owner_user_id: '00000000-0000-4000-8000-000000000001' },
    { api_key_id: 'k1000001-0000-4000-8000-000000000001', key_prefix: prefix('demomainkey01ab'), name: 'laptop', created_at: iso(-9000), expires_at: iso(20000), revoked_at: null, owner_user_id: me },
    { api_key_id: 'k1000001-0000-4000-8000-000000000002', key_prefix: prefix('demooldkey02cd'), name: 'ci-runner', created_at: iso(-30000), expires_at: null, revoked_at: iso(-26000), owner_user_id: me },
  ];

  const users: DemoUser[] = [
    { user_id: '00000000-0000-4000-8000-000000000001', username: 'demo_admin', role: 'super_admin', is_disabled: false, created_at: iso(-40000) },
    { user_id: '00000000-0000-4000-8000-000000000002', username: 'demo_manager', role: 'user', is_disabled: false, created_at: iso(-35000) },
    { user_id: me, username: 'demo_user', role: 'user', is_disabled: false, created_at: iso(-30000) },
    { user_id: '00000000-0000-4000-8000-000000000004', username: 'former_employee', role: 'user', is_disabled: true, created_at: iso(-28000) },
  ];

  const accessRequests: DemoAccessRequest[] = [
    { request_id: 'r1000001-0000-4000-8000-000000000001', applicant_name: 'Grace Hopper', applicant_email: 'grace@example.com', organization: 'Acme Corp', requested_mode: 'enterprise', status: 'pending', review_notes: null, created_at: iso(-300), reviewed_at: null },
    { request_id: 'r1000001-0000-4000-8000-000000000002', applicant_name: 'Alan Turing', applicant_email: 'alan@example.com', organization: '', requested_mode: 'personal', status: 'approved', review_notes: 'Standard personal access.', created_at: iso(-6000), reviewed_at: iso(-5900) },
  ];

  const scopes: DemoNetworkScope[] = [
    { scope_id: entScope, scope_name: 'Acme Enterprise', scope_type: 'enterprise', user_id: manager, username: 'demo_manager', network_cidr: '10.0.0.0/8', agent_count: 3, zone_count: 3, created_at: iso(-20000), updated_at: iso(-100) },
    { scope_id: perScope, scope_name: 'demo_user personal', scope_type: 'personal', user_id: me, username: 'demo_user', network_cidr: null, agent_count: 5, zone_count: 2, created_at: iso(-25000), updated_at: iso(-10) },
    { scope_id: '22222222-2222-4000-8000-000000000024', scope_name: 'Partner Network', scope_type: 'enterprise', user_id: manager, username: 'demo_manager', network_cidr: '172.16.0.0/12', agent_count: 0, zone_count: 0, created_at: iso(-8000), updated_at: iso(-5000) },
  ];

  const zones: DemoNetworkZone[] = [
    { zone_id: 'z1000001-0000-4000-8000-000000000001', zone_name: 'Central Hub', zone_type: 'central', scope_id: entScope, scope_name: 'Acme Enterprise', parent_zone_id: null, relay_node_count: 2, created_at: iso(-19000), updated_at: iso(-700) },
    { zone_id: 'z1000001-0000-4000-8000-000000000002', zone_name: 'US West Region', zone_type: 'regional', scope_id: entScope, scope_name: 'Acme Enterprise', parent_zone_id: 'z1000001-0000-4000-8000-000000000001', relay_node_count: 1, created_at: iso(-18500), updated_at: iso(-800) },
    { zone_id: 'z1000001-0000-4000-8000-000000000003', zone_name: 'Egress Pool', zone_type: 'egress', scope_id: entScope, scope_name: 'Acme Enterprise', parent_zone_id: 'z1000001-0000-4000-8000-000000000001', relay_node_count: 1, created_at: iso(-18000), updated_at: iso(-900) },
    { zone_id: 'z1000001-0000-4000-8000-000000000004', zone_name: 'Home Edge', zone_type: 'local_edge', scope_id: perScope, scope_name: 'demo_user personal', parent_zone_id: null, relay_node_count: 1, created_at: iso(-24000), updated_at: iso(-60) },
    { zone_id: 'z1000001-0000-4000-8000-000000000005', zone_name: 'Laptop LAN', zone_type: 'local', scope_id: perScope, scope_name: 'demo_user personal', parent_zone_id: 'z1000001-0000-4000-8000-000000000004', relay_node_count: 0, created_at: iso(-23000), updated_at: iso(-50) },
  ];

  const relayNodes: DemoRelayNode[] = [
    { id: 'n1000001-0000-4000-8000-000000000001', node_name: 'relay-eu-central', node_type: 'central', status: 'healthy', current_load: 0.42, queue_depth: 12, avg_latency_ms: 38, success_rate: 0.99, capabilities: ['websocket', 'task_delivery'], max_capacity: 1000, region: 'eu-central', zone: 'Central Hub', last_heartbeat_at: iso(-1), metadata: { provider: 'self-hosted' }, enabled: true, created_at: iso(-18000), updated_at: iso(-2) },
    { id: 'n1000001-0000-4000-8000-000000000002', node_name: 'relay-us-west', node_type: 'regional', status: 'degraded', current_load: 0.87, queue_depth: 96, avg_latency_ms: 145, success_rate: 0.91, capabilities: ['websocket', 'task_delivery'], max_capacity: 500, region: 'us-west', zone: 'US West Region', last_heartbeat_at: iso(-8), metadata: { provider: 'self-hosted' }, enabled: true, created_at: iso(-17500), updated_at: iso(-9) },
    { id: 'n1000001-0000-4000-8000-000000000003', node_name: 'egress-gw-relay', node_type: 'egress', status: 'healthy', current_load: 0.2, queue_depth: 3, avg_latency_ms: 22, success_rate: 0.995, capabilities: ['egress'], max_capacity: 200, region: 'eu-central', zone: 'Egress Pool', last_heartbeat_at: iso(-1), metadata: {}, enabled: true, created_at: iso(-17000), updated_at: iso(-3) },
    { id: 'n1000001-0000-4000-8000-000000000004', node_name: 'home-edge-01', node_type: 'local_edge', status: 'down', current_load: 0, queue_depth: 0, avg_latency_ms: null, success_rate: null, capabilities: ['task_delivery'], max_capacity: 50, region: 'home', zone: 'Home Edge', last_heartbeat_at: iso(-2200), metadata: {}, enabled: false, created_at: iso(-22000), updated_at: iso(-2100) },
  ];

  const gateways: DemoGateway[] = [
    { id: 'g1000001-0000-4000-8000-000000000001', scope_id: entScope, gateway_name: 'OpenAI Direct', gateway_type: 'model', domain_allowlist: ['api.openai.com'], secret_store_ref: 'env:EGRESS_OPENAI_KEY', rate_limit_config: { requests_per_minute: 60 }, cache_config: { ttl_seconds: 300 }, cost_tracking: true, enabled: true, allow_internal_egress: false, created_at: iso(-6000), updated_at: iso(-300) },
    { id: 'g1000001-0000-4000-8000-000000000002', scope_id: entScope, gateway_name: 'GitHub Packages', gateway_type: 'github', domain_allowlist: ['github.com', 'pkg.github.com'], secret_store_ref: 'env:EGRESS_GITHUB_KEY', rate_limit_config: null, cache_config: null, cost_tracking: true, enabled: true, allow_internal_egress: false, created_at: iso(-5500), updated_at: iso(-250) },
    { id: 'g1000001-0000-4000-8000-000000000003', scope_id: perScope, gateway_name: 'Generic API', gateway_type: 'api', domain_allowlist: [], secret_store_ref: null, rate_limit_config: null, cache_config: null, cost_tracking: false, enabled: false, allow_internal_egress: true, created_at: iso(-4000), updated_at: iso(-3500) },
  ];

  const channels: DemoChannel[] = [
    { id: 'd1000001-0000-4000-8000-000000000001', scope_id: entScope, channel_name: ' vpn-tunnel-primary', channel_type: 'vpn', source_agent_id: agents[3].agent_id, target_agent_id: agents[0].agent_id, connection_config: { endpoint: '***MASKED***', protocol: 'wireguard', public_key: '***MASKED***' }, encryption_config: { algorithm: 'AES-256-GCM', key_rotation_days: 30, tls_version: '1.3' }, bandwidth_mbps: 100, latency_target_ms: 10, enabled: true, created_at: iso(-5000), updated_at: iso(-120), health_checks: [ { id: 'h1000001-0000-4000-8000-000000000001', check_time: iso(-30), latency_ms: 9.4, packet_loss_percent: 0, bandwidth_mbps: 98.2, status: 'healthy', error_message: null }, { id: 'h1000001-0000-4000-8000-000000000002', check_time: iso(-330), latency_ms: 88, packet_loss_percent: 1.2, bandwidth_mbps: 71, status: 'degraded', error_message: null } ] },
    { id: 'd1000001-0000-4000-8000-000000000002', scope_id: entScope, channel_name: 'private-link-west', channel_type: 'private_link', source_agent_id: agents[4].agent_id, target_agent_id: agents[6].agent_id, connection_config: { endpoint: '***MASKED***', protocol: 'private-link' }, encryption_config: { algorithm: 'AES-256-GCM' }, bandwidth_mbps: 500, latency_target_ms: 5, enabled: true, created_at: iso(-4500), updated_at: iso(-90), health_checks: [ { id: 'h1000001-0000-4000-8000-000000000003', check_time: iso(-20), latency_ms: 4.1, packet_loss_percent: 0, bandwidth_mbps: 500, status: 'healthy', error_message: null } ] },
    { id: 'd1000001-0000-4000-8000-000000000003', scope_id: null, channel_name: 'direct-p2p-remote', channel_type: 'p2p', source_agent_id: agents[0].agent_id, target_agent_id: agents[7].agent_id, connection_config: { transport: 'webrtc' }, encryption_config: { algorithm: 'ChaCha20-Poly1305' }, bandwidth_mbps: 20, latency_target_ms: 40, enabled: false, created_at: iso(-3800), updated_at: iso(-3700), health_checks: [] },
  ];

  const policies: DemoPolicy[] = [
    { id: 'y1000001-0000-4000-8000-000000000001', policy_name: 'Deny Personal Edge', description: 'Personal edge relays never carry enterprise traffic.', priority: 10, scope_id: entScope, source_zone_id: null, target_zone_id: null, allowed_route_types: null, denied_route_types: ['personal_edge'], require_approval: false, risk_level: 'low', data_boundary_rules: null, enabled: true, created_at: iso(-15000), updated_at: iso(-2000) },
    { id: 'y1000001-0000-4000-8000-000000000002', policy_name: 'Central Relay Default', description: 'Default allow-list for the central route.', priority: 50, scope_id: entScope, source_zone_id: 'z1000001-0000-4000-8000-000000002', target_zone_id: null, allowed_route_types: ['central_relay'], denied_route_types: null, require_approval: false, risk_level: 'low', data_boundary_rules: null, enabled: true, created_at: iso(-14000), updated_at: iso(-3000) },
    { id: 'y1000001-0000-4000-8000-000000000003', policy_name: 'High-Risk Needs Approval', description: 'Critical payloads route only after approval.', priority: 90, scope_id: null, source_zone_id: null, target_zone_id: null, allowed_route_types: null, denied_route_types: null, require_approval: true, risk_level: 'critical', data_boundary_rules: { encrypt_at_rest: true }, enabled: true, created_at: iso(-13000), updated_at: iso(-4000) },
  ];

  const decisions: DemoDecision[] = [
    { id: 'e1000001-0000-4000-8000-000000000001', task_id: tasks[0].task_id, message_id: 'm1000001-0000-4000-8000-000000000001', trace_id: 'tr-0001', selected_route_type: 'central_relay', selected_relay_node_id: relayNodes[0].id, candidate_routes: [{ route_type: 'central_relay', score: 0.92 }], rejection_reasons: { personal_edge: 'policy deny' }, fallback_from_route: null, fallback_reason: null, timeliness_mode: 'normal', risk_level: 'low', final_score: 0.92, decision_time_ms: 14, shadow_mode: false, created_at: iso(-690) },
    { id: 'e1000001-0000-4000-8000-000000000002', task_id: tasks[2].task_id, message_id: 'm1000001-0000-4000-8000-000000000002', trace_id: 'tr-0002', selected_route_type: 'central_relay', selected_relay_node_id: relayNodes[0].id, candidate_routes: [{ route_type: 'central_relay', score: 0.88 }], rejection_reasons: {}, fallback_from_route: null, fallback_reason: null, timeliness_mode: 'express', risk_level: 'medium', final_score: 0.88, decision_time_ms: 11, shadow_mode: false, created_at: iso(-19) },
    { id: 'e1000001-0000-4000-8000-000000000003', task_id: tasks[4].task_id, message_id: 'm1000001-0000-4000-8000-000000000003', trace_id: 'tr-0003', selected_route_type: 'dedicated_channel', selected_relay_node_id: null, candidate_routes: [{ route_type: 'dedicated_channel', score: 0.81 }], rejection_reasons: { public_network: 'data boundary rule' }, fallback_from_route: 'central_relay', fallback_reason: 'policy deny on default route', timeliness_mode: 'normal', risk_level: 'high', final_score: 0.81, decision_time_ms: 22, shadow_mode: false, created_at: iso(-290) },
    { id: 'e1000001-0000-4000-8000-000000000004', task_id: tasks[5].task_id, message_id: 'm1000001-0000-4000-8000-000000000004', trace_id: null, selected_route_type: 'regional_relay', selected_relay_node_id: relayNodes[1].id, candidate_routes: [{ route_type: 'regional_relay', score: 0.76 }], rejection_reasons: {}, fallback_from_route: null, fallback_reason: null, timeliness_mode: 'normal', risk_level: 'low', final_score: 0.76, decision_time_ms: 9, shadow_mode: false, created_at: iso(-1190) },
    { id: 'e1000001-0000-4000-8000-000000000005', task_id: tasks[7].task_id, message_id: 'm1000001-0000-4000-8000-000000000005', trace_id: 'tr-0005', selected_route_type: 'central_relay', selected_relay_node_id: relayNodes[0].id, candidate_routes: [{ route_type: 'central_relay', score: 0.94 }, { route_type: 'regional_relay', score: 0.71 }], rejection_reasons: { personal_edge: 'policy deny' }, fallback_from_route: null, fallback_reason: null, timeliness_mode: 'express', risk_level: null, final_score: 0.94, decision_time_ms: 12, shadow_mode: false, created_at: iso(-90) },
    { id: 'e1000001-0000-4000-8000-000000000006', task_id: tasks[8].task_id, message_id: 'm1000001-0000-4000-8000-000000000006', trace_id: 'tr-0006', selected_route_type: 'local_edge', selected_relay_node_id: relayNodes[3].id, candidate_routes: [{ route_type: 'local_edge', score: 0.6 }], rejection_reasons: {}, fallback_from_route: 'central_relay', fallback_reason: 'relay degraded', timeliness_mode: 'normal', risk_level: 'medium', final_score: 0.6, decision_time_ms: 18, shadow_mode: true, created_at: iso(-35) },
  ];

  const slaTargets: DemoSlaTarget[] = [
    { id: 's1000001-0000-4000-8000-000000000001', scope_id: entScope, target_name: 'Global P99 Latency', metric_type: 'latency_p99', target_value: 500, warning_threshold: 0.9, critical_threshold: 0.8, measurement_window_seconds: 300, enabled: true, created_at: iso(-16000), updated_at: iso(-400) },
    { id: 's1000001-0000-4000-8000-000000000002', scope_id: entScope, target_name: 'Delivery Success Rate', metric_type: 'success_rate', target_value: 99, warning_threshold: 0.98, critical_threshold: 0.95, measurement_window_seconds: 600, enabled: true, created_at: iso(-15500), updated_at: iso(-300) },
    { id: 's1000001-0000-4000-8000-000000000003', scope_id: perScope, target_name: 'Personal P95 Latency', metric_type: 'latency_p95', target_value: 800, warning_threshold: 0.9, critical_threshold: 0.75, measurement_window_seconds: 300, enabled: true, created_at: iso(-15000), updated_at: iso(-200) },
    { id: 's1000001-0000-4000-8000-000000000004', scope_id: entScope, target_name: 'Legacy Uptime (unused)', metric_type: 'uptime', target_value: 99.9, warning_threshold: 0.99, critical_threshold: 0.95, measurement_window_seconds: 3600, enabled: false, created_at: iso(-12000), updated_at: iso(-11000) },
  ];

  const slaViolations: DemoSlaViolation[] = [
    { id: 'v1000001-0000-4000-8000-000000000001', target_id: slaTargets[0].id, violation_time: iso(-1200), metric_value: 612, severity: 'critical', duration_seconds: 900, resolved: false, resolved_at: null, resolution_note: null },
    { id: 'v1000001-0000-4000-8000-000000000002', target_id: slaTargets[0].id, violation_time: iso(-3600), metric_value: 523, severity: 'warning', duration_seconds: 420, resolved: true, resolved_at: iso(-3300), resolution_note: 'Traffic shifted to backup relay.' },
    { id: 'v1000001-0000-4000-8000-000000000003', target_id: slaTargets[1].id, violation_time: iso(-700), metric_value: 96.4, severity: 'warning', duration_seconds: null, resolved: false, resolved_at: null, resolution_note: null },
  ];

  const circuitBreakers: DemoCircuitBreaker[] = [
    { id: 'b1000001-0000-4000-8000-000000000001', relay_node_id: relayNodes[0].id, state: 'closed', failure_count: 1, success_count: 240, last_failure_time: iso(-6000), open_until: null, success_threshold: 3, failure_threshold: 5, is_open: false, should_allow_request: true },
    { id: 'b1000001-0000-4000-8000-000000000002', relay_node_id: relayNodes[1].id, state: 'open', failure_count: 6, success_count: 18, last_failure_time: iso(-3), open_until: iso(57), success_threshold: 3, failure_threshold: 5, is_open: true, should_allow_request: false },
    { id: 'b1000001-0000-4000-8000-000000000003', relay_node_id: relayNodes[3].id, state: 'half_open', failure_count: 5, success_count: 2, last_failure_time: iso(-3200), open_until: null, success_threshold: 3, failure_threshold: 5, is_open: false, should_allow_request: true },
  ];

  const failoverConfigs: DemoFailoverConfig[] = [
    { id: 'f1000001-0000-4000-8000-000000000001', scope_id: entScope, primary_relay_id: relayNodes[0].id, backup_relay_ids: [relayNodes[1].id], failover_threshold_seconds: 30, auto_failover_enabled: true, manual_approval_required: false, created_at: iso(-17000), updated_at: iso(-16000) },
  ];

  const failoverEvents: DemoFailoverEvent[] = [
    { id: 'f1000002-0000-4000-8000-000000000001', config_id: failoverConfigs[0].id, event_time: iso(-2400), trigger_reason: 'latency_p99 critical', from_relay_id: relayNodes[1].id, to_relay_id: relayNodes[0].id, affected_task_count: 14, auto_triggered: true, status: 'completed', completed_at: iso(-2380), rollback_at: null, error_message: null },
    { id: 'f1000002-0000-4000-8000-000000000002', config_id: failoverConfigs[0].id, event_time: iso(-60), trigger_reason: 'manual trigger', from_relay_id: relayNodes[0].id, to_relay_id: relayNodes[1].id, affected_task_count: 3, auto_triggered: false, status: 'in_progress', completed_at: null, rollback_at: null, error_message: null },
  ];

  const organizations: DemoOrganization[] = [
    {
      org_id: orgId, name: 'Acme Corp', slug: 'acme-corp', role: 'manager', is_disabled: false, created_at: iso(-20000),
      members: [
        { user_id: manager, username: 'demo_manager', role: 'manager', joined_at: iso(-20000) },
        { user_id: me, username: 'demo_user', role: 'member', joined_at: iso(-12000) },
      ],
    },
  ];

  const auditLogs: DemoAuditLog[] = [
    mkAudit('u-0001', 'admin', '00000000-0000-4000-8000-000000000001', 'egress_gateway.create', 'egress_gateway', gateways[0].id, 'Created OpenAI Direct'),
    mkAudit('u-0002', 'admin', '00000000-0000-4000-8000-000000000001', 'egress_gateway.update', 'egress_gateway', gateways[0].id, 'Toggled enabled'),
    mkAudit('u-0003', 'user', me, 'agent.create', 'agent', agents[0].agent_id, 'Registered Atlas Worker'),
    mkAudit('u-0004', 'user', me, 'apikey.revoke', 'api_key', apiKeys[1].api_key_id, 'Revoked ci-runner key'),
    mkAudit('u-0005', 'user', me, 'task.create', 'task', tasks[0].task_id, 'Summarize Q3 report'),
    mkAudit('u-0006', 'admin', manager, 'org.member.add', 'organization', orgId, 'Added demo_user as member'),
    mkAudit('u-0007', 'admin', '00000000-0000-4000-8000-000000000001', 'access_request.approve', 'access_request', accessRequests[1].request_id, 'Approved personal access'),
    mkAudit('u-0008', 'user', me, 'agent.rotate-token', 'agent', agents[2].agent_id, 'Rotated token'),
    // Agent-initiated audits: the ONLY rows production's narrow overview
    // filter (resource_type='agent' AND actor_id IN the user's own agent
    // ids — see dashboard_service.py / ws.py write_audit with
    // actor_type='agent') ever returns, so recent_agent_status_changes is
    // populated by ws.connected / ws.disconnected events, not by the
    // user-initiated rows above.
    mkAudit('u-0009', 'agent', agents[0].agent_id, 'ws.connected', 'agent', agents[0].agent_id, 'Atlas Worker connected'),
    mkAudit('u-0010', 'agent', agents[1].agent_id, 'ws.disconnected', 'agent', agents[1].agent_id, 'Beacon Relay Bot disconnected'),
  ];

  return {
    agents,
    tasks,
    approvals,
    pendingConnections,
    connectionStats: {
      [agents[2].agent_id]: { pending: 1, accepted: 4, rejected: 2 },
      [agents[5].agent_id]: { pending: 1, accepted: 1, rejected: 0 },
      [agents[0].agent_id]: { pending: 0, accepted: 9, rejected: 1 },
    },
    apiKeys,
    users,
    accessRequests,
    scopes,
    zones,
    relayNodes,
    gateways,
    channels,
    policies,
    decisions,
    slaTargets,
    slaViolations,
    circuitBreakers,
    failoverEvents,
    failoverConfigs,
    organizations,
    auditLogs,
    personalScope: {
      user_id: me,
      scope_name: 'demo_user',
      default_relay_type: 'central_relay',
      enable_edge_relay: true,
      enable_secure_channel: false,
      routing_strategy: 'normal',
      created_at: iso(-26000),
      updated_at: iso(-1000),
    },
    edgeRelays: [
      { id: 'q1000001-0000-4000-8000-000000000001', node_name: 'laptop-edge', status: 'online', current_load: 0.15, queue_depth: 1, avg_latency_ms: 6, success_rate: 0.99, is_healthy: true, network_info: { local_ip: '192.168.1.42', subnet: '192.168.1.0/24' }, last_heartbeat_at: iso(-1), created_at: iso(-6000) },
      { id: 'q1000001-0000-4000-8000-000000000002', node_name: 'pi-edge', status: 'offline', current_load: 0, queue_depth: 0, avg_latency_ms: null, success_rate: 0.8, is_healthy: false, network_info: { local_ip: '192.168.1.7', subnet: '192.168.1.0/24' }, last_heartbeat_at: iso(-5000), created_at: iso(-9000) },
    ],
  };
}

function task(
  task_id: string,
  status: string,
  sender: DemoAgent,
  target: DemoAgent,
  created: string,
  delivery_status: string,
  payload_preview: string | null,
  result_preview: string | null,
  error_code?: string,
): DemoTask {
  const message_id = 'm' + task_id.slice(1);
  return {
    task_id,
    status,
    sender_agent: sender.name,
    target_agent: target.name,
    created_at: created,
    updated_at: new Date(new Date(created).getTime() + 60_000).toISOString(),
    delivery_status,
    duration_sec: status === 'delivered' ? 3 : null,
    error_code: error_code ?? null,
    payload_preview,
    result_preview,
    error_message: error_code ? 'Demo failure recorded by the fixture world.' : null,
    retry_count: error_code ? 1 : 0,
    messages: [
      { message_id, type: 'task_request', delivery_status, created_at: created },
      ...(status === 'delivered'
        ? [{ message_id: message_id + '-ack', type: 'task_ack', delivery_status: 'delivered', created_at: new Date(new Date(created).getTime() + 60_000).toISOString() }]
        : []),
    ],
    progress: [
      { seq: 1, status: 'sent', progress_pct: 0, message: null, created_at: created },
      ...(status === 'delivered' || status === 'running'
        ? [{ seq: 2, status: 'progress', progress_pct: status === 'running' ? 55 : 100, message: status === 'running' ? 'Working' : null, created_at: new Date(new Date(created).getTime() + 30_000).toISOString() }]
        : []),
    ],
  };
}

/** Deterministic offset sequence so audit timestamps scatter without
 * Math.random (which trips weak-randomness scanners). */
let auditSeq = 0;

function mkAudit(
  audit_id: string,
  actor_type: 'user' | 'admin' | 'system' | 'agent',
  actor_id: string,
  action: string,
  resource_type: string | null,
  resource_id: string | null,
  detail: string,
): DemoAuditLog {
  auditSeq += 137;
  return {
    audit_id,
    actor_type,
    actor_id,
    action,
    resource_type,
    resource_id,
    task_id: null,
    error_code: null,
    request_ip: '127.0.0.1',
    details: { note: detail },
    created_at: iso(-auditSeq - 100),
  };
}

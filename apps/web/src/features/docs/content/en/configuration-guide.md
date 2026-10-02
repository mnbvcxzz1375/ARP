# AgentNet Configuration Guide

For customers using the AgentNet console: what you can configure, where, and
what happens when you get it wrong — organized by role.

- For installation see [Quickstart](quickstart.md) and
  [Console deployment](dashboard-deploy.md).
- For the full role/permission matrix see the
  [Console RBAC guide](dashboard-rbac.md).
- This guide covers **runtime configuration only**: accounts, preferences,
  networking, routing, and security switches.

## Before you read

**Which section is yours**

| Who you are | Section |
|-------------|---------|
| Individual user (`user`) | [1. Individual user](#1-individual-user) |
| Organization manager (org `manager`, or platform `admin`) | [2. Organization manager](#2-organization-manager) |
| Super admin (`super_admin`) | [3. Super admin](#3-super-admin) |

One person can be a platform `user` and an org `manager` at the same time —
read both. An org manager's platform role stays `user`; enterprise
capabilities come entirely from org membership and do not raise platform-level
permissions.

**Step-up authentication**

Write operations on egress gateways, dedicated channels, and network topology
require the super admin to complete step-up authentication. Without it the API
returns `403 STEP_UP_REQUIRED` — this is the **normal gating flow, not a bug**.
Re-login to complete step-up and replay the operation; console pages remember
the pending action and replay it automatically after verification.

**Blast radius**

Preferences and routing strategy affect only you. Network scopes, egress
gateways, dedicated channels, route policies, SLA targets, and continuity
settings affect the whole organization or the entire network — confirm the
effect in demo mode first (see [Appendix A](#appendix-a-demo-mode)).

---

## 1. Individual user

### 1.1 Account and profile

- Login is API-key based (key-first); `user_id` is the canonical identifier.
- The username is a **display label, not a unique account** (migration 0030):
  renaming never collides and there is no name squatting.
- Rename in *Settings → Account* or via
  `PATCH /v1/dashboard/auth/me/profile` (field `username`, 3–32 characters,
  trimmed automatically).

### 1.2 Appearance and preferences

*Settings → Appearance*, or `PATCH /v1/dashboard/auth/me/preferences`. Every
key is **whitelist-validated**: unknown keys or invalid values return `400`
(not 422), so the server never accumulates dirty state.

| Setting | Values | Notes |
|---------|--------|-------|
| `theme` | `light` / `dark` | Manual override on top of system preference; server value wins over local |
| `locale` | `en` / `zh` | UI language; `null` explicitly clears it (falls back to browser) |
| `fontScale` | `0.8` – `1.5` | Page zoom; 1 is the default |
| `reducedMotion` | `true` / `false` | Reduced motion; CSS only honors the `prefers-reduced-motion` media query, so this acts as "recorded preference + static variant" |

Changes apply immediately (optimistic update) and persist server-side; logging
in from another browser brings your preferences with the account.

### 1.3 API keys and agents

- *API Keys* page: create, rotate, revoke your own keys (`apikey:manage:own`).
- *Agents* page: create agents and rotate tokens. Agent tokens are shown once
  at creation/rotation — store them securely.
- Other personal operations (tasks, messages, approvals, connections) are
  covered in the [Quickstart](quickstart.md).

### 1.4 Personal network scope

`GET/PATCH /v1/personal/scope` — your own logical network boundary:

- `network_cidr`: your subnet, used by network-level policy matching.
- `enable_edge_relay`: a **three-state edge-relay toggle** — unset = system
  default, `false` = explicitly exclude your traffic from personal edge
  relays, `true` = opt in. This switch used to be write-only; since migration
  0033 it is actually consumed by routing decisions (the `enable_edge_relay`
  argument of `select_route`).
- `agent_ids` / `zone_ids`: bind agents and zones into the scope.

### 1.5 Personal routing strategy

*Routing strategy* page (personal scope) or `PATCH /v1/personal/scope` field
`routing_strategy`. Three modes:

| Mode | Behavior | Good for |
|------|----------|----------|
| `fast` | Latency weight is raised, **unhealthy nodes are still excluded** — not blind low-latency | Latency-sensitive workloads tolerating occasional retries |
| `normal` (default) | Composite scoring (latency + success rate + load) | Most workloads |
| `reliable` | Success/failure weight ×1.5 plus a strict health gate: degraded nodes never carry traffic | Mission-critical deliveries that must not fail |

The strategy is a **scoring-layer override**: it reorders candidates but does
not change hard filters (offline or circuit-broken nodes carry traffic in no
mode). A switch applies to **new tasks**; in-flight tasks keep their route.

### 1.6 Edge relay nodes

You can register your own edge node to participate in relaying
(`POST /v1/personal/edge-relay/register`, heartbeats via
`POST /v1/personal/edge-relay/heartbeat`). Heartbeats carry `current_load`
(0.0–1.0), `queue_depth`, `avg_latency_ms`, and `success_rate`. Registered
nodes join the routing candidate pool; unhealthy nodes are removed
automatically. Nodes are register-only — the console has no edit/delete entry
(registering the same name again fails with a conflict).

---

## 2. Organization manager

Your platform role is `user`, but you are a `manager` inside an organization
(or a platform `admin`). Everything in this section **affects the whole
organization**.

### 2.1 Access-request approval

New members submit access requests through the public page
(`POST /v1/access-requests`, no login required). Managers approve them on the
*Access Requests* page: **approval automatically creates the user and issues
an API key**; rejection leaves an audit trail. Both outcomes land in the audit
log.

### 2.2 Organization and members

`/v1/organizations`:

- Create an organization (`POST /v1/organizations`).
- Member management: `POST /{org_id}/members` to add, `PATCH` to change the
  role, `DELETE` to remove.
- The member role determines visibility and operability of the features in
  this section (enterprise console navigation renders from org membership).

### 2.3 Network scopes and zones

`/v1/dashboard/admin/network/...` (writes require step-up):

- **Scopes**: `scope_type = personal | enterprise`, `network_cidr`, bound
  `agent_ids` / `zone_ids`. Enterprise scopes are the mount point for
  network-level egress control and route policies.
- **Zones**: `zone_type` is one of `local`, `regional`, `global`,
  `local_edge`, `central`, `cloud`, `egress`; zones support a parent zone
  (`parent_zone_id`) and zone-level relay node binding (`relay_node_ids`).

### 2.4 Relay nodes

`POST /v1/relay-nodes/register` (routing prefix is `/v1`, not `/v1/routes`):

| Field | Description |
|-------|-------------|
| `node_name` | Unique node name (≤128) |
| `node_type` | `central` / `personal_edge` / `local_edge` / `regional` / `egress` / `dedicated` |
| `region` / `zone` | Network region |
| `capabilities` | Capability tags |
| `max_capacity` | Capacity ceiling |

Node registration is **append-only**: the console has no edit/delete entry. If
you get it wrong, register a new node and let the old one go quiet — heartbeats
stop, health turns `unknown`, and the node is dropped from the pool.

### 2.5 Egress gateways

`/v1/egress/gateways` (writes require step-up):

| Field | Description |
|-------|-------------|
| `gateway_name` / `gateway_type` | Name and type (≤32) |
| `domain_allowlist` | **The domain allowlist** — the core of network-level egress control; outbound requests to domains outside it are refused |
| `secret_store_ref` | Credential reference pointing at an external secret store — **never put plaintext secrets here** |
| `cost_tracking` | Track cost per gateway |
| `allow_internal_egress` | Allow internal-subnet direct egress (0032); when off, internal traffic must also pass route policy |
| `enabled` | Enable/disable via PATCH — no need to delete and recreate |

### 2.6 Dedicated channels

`/v1/dashboard/admin/dedicated-channels` (all writes require step-up):

| Field | Description |
|-------|-------------|
| `channel_type` | `vpn` / `private_link` / `p2p` / `direct_connect` |
| `source_agent_id` → `target_agent_id` | The two endpoints (target added with the archipelago release) |
| `connection_config` / `encryption_config` | Connection and encryption parameters (structured dicts; reference sensitive values as `env:VAR` or `***MASKED***`) |
| `bandwidth_mbps` / `latency_target_ms` | Target bandwidth / latency (>0) |
| `enabled` | Enable/disable |

`POST /{id}/health-check` runs a proactive health check returning latency,
packet loss, bandwidth, status, and error message. Updates use `PATCH` (not
`PUT`) and only the post-creation mutable fields.

### 2.7 Route policies

`/v1/routes/policies`:

- `policy_name`, `priority` (lower matches first), `description`.
- `allowed_route_types` / `denied_route_types`: comma-separated route types.
- `risk_level`: `low` / `medium` / `high` / `critical`.
- `require_approval`: whether high-risk routing needs human approval.
- Updates via `PATCH`; there is no delete endpoint (disable with
  `enabled=false`).

### 2.8 SLA targets and continuity

- **SLA**: `/v1/sla/targets` creates targets (`target_name`, `metric_type`,
  `target_value`, warning/critical thresholds, `measurement_window_seconds`);
  `/v1/sla/violations`, `/metrics`, `/report` read monitoring.
- **Continuity**: `/v1/continuity/failover-configs` configures failover;
  `POST /failover/{config_id}/trigger` triggers, `POST /failover/{event_id}/execute`
  executes, `POST /failover/{event_id}/rollback` rolls back. Note: **rollback
  is metadata-level** (restores routing state) — it does not automatically
  shift traffic back to the primary relay. Switching back is explicit or
  converges automatically once health recovers. `/circuit-breakers` lists
  breakers; `POST /{id}/reset` resets one manually.

---

## 3. Super admin

The super admin's exclusive configuration is all **high-risk**: it requires
the `super_admin` role **and** completed step-up authentication
(`require_high_risk`).

| Operation | Where |
|-----------|-------|
| Disable / enable users | User management (`PATCH /v1/dashboard/admin/users/{id}/...`) |
| Disable / enable agents | Agent management |
| Force-revoke any API key | API Keys management (`apikey:revoke:global`) |
| Cancel a **running** task; force-expire a task | Task management (`task:cancel:running`) |
| Export audit logs | Audit log page (`audit:export`) |
| Security policy / read-only system health | System-level settings |

"Cancel task" for a regular user only covers **pending** tasks; canceling a
running one is super-admin exclusive. When a button is greyed out, first check
whether it is the role or the missing step-up.

Super admins can also do everything in sections 1 and 2 (the inheritance is
documented in the [RBAC guide](dashboard-rbac.md)).

---

## Appendix A: Demo mode

`npm run dev:demo` (development) or `npm run build:demo` (static deployment)
starts a pure-frontend demo: no backend, no database, no real secrets. It is
for **training, acceptance demos, and trying configuration changes safely**.

- The login page offers one-click fill for three personas: `demo_admin`
  (super admin), `demo_manager` (org manager), `demo_user` (individual user).
- All writes go through an in-memory adapter; reset via refresh or the banner
  "reset data" button.
- Preferences, routing strategy, and all enterprise configuration can be
  exercised end to end — **all data is fake**.
- The demo banner always says "data is fake" so it never gets confused with
  the real environment (the production build does not contain the demo branch
  at all).

## Appendix B: Configuration reference

| Setting | Endpoint / page | Blast radius | Requires |
|---------|-----------------|--------------|----------|
| Username | `PATCH /v1/dashboard/auth/me/profile` | Self | Any |
| Theme / language / font scale / reduced motion | `PATCH /v1/dashboard/auth/me/preferences` | Self | Any |
| Personal CIDR, edge-relay toggle | `PATCH /v1/personal/scope` | Self | Any |
| Personal routing strategy | `PATCH /v1/personal/scope` (routing_strategy) | Own new tasks | Any |
| Personal edge node | `POST /v1/personal/edge-relay/register` | Network candidate pool | Any |
| Org members | `/v1/organizations/{id}/members` | Org | Org manager |
| Scopes / zones | `/v1/dashboard/admin/network/...` | Org | super_admin + step-up |
| Relay nodes | `POST /v1/relay-nodes/register` | Network | super_admin + step-up |
| Egress gateways | `/v1/egress/gateways` | Org egress | super_admin + step-up |
| Dedicated channels | `/v1/dashboard/admin/dedicated-channels` | End-to-end channel | super_admin + step-up |
| Route policies | `/v1/routes/policies` | Org | super_admin + step-up |
| SLA targets | `/v1/sla/targets` | Org | `sla:manage` |
| Failover / circuit breakers | `/v1/continuity/...` | Org | Org manager |
| Disable users, revoke keys, cancel running tasks | Admin console | Platform | super_admin + step-up |

## Appendix C: FAQ

**Q: I saved a preference and the UI snapped back?**
A: That was an old demo-adapter bug, now fixed (preferences persist to
localStorage and the server). If it recurs, make sure you are not running the
5173 demo dev server while changing settings on 4178 — the two ports' storage
overwrite each other.

**Q: I changed the routing strategy but routing did not change?**
A: The strategy only affects the **scoring layer** and only new tasks. Also
check whether the target nodes are blocked by the health gate — offline or
degraded nodes carry traffic under no strategy.

**Q: A configuration API returned 403 STEP_UP_REQUIRED?**
A: Step-up authentication is not complete. Re-login through the step-up flow;
the console replays the blocked operation automatically.

**Q: Renaming a username reports a conflict?**
A: It should not. Since migration 0030 usernames are non-unique; an
`INVALID_REQUEST` means a length error — check 3–32 characters. Collision
errors only appear when **registering an account** (registration always
creates a new account).

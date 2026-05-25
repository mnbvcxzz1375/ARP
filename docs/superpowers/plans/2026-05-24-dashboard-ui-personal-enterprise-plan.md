# Dashboard Personal / Enterprise UI Upgrade Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Redesign the AgentNet Dashboard into a production-grade personal and enterprise console with explicit access request flows, complete feature navigation, clear status feedback, and strict no-fallback acceptance gates.

**Architecture:** Keep the existing React + Vite + Tailwind + React Query stack and evolve the product surface around two modes: Personal Console and Enterprise Console. Public pages become an explicit access funnel; authenticated pages become role-aware operational workspaces; enterprise-only surfaces are permission-gated and never exposed through UI-only checks.

**Tech Stack:** React 18, React Router, React Query, TypeScript, Tailwind CSS, lucide-react, FastAPI dashboard APIs, pytest, Vitest, Playwright.

---

## 0. First Principles And Non-Negotiable Constraints

### 0.1 First Principles

AgentNet exists to answer five questions for a human operator:

1. Who am I and what scope am I operating in?
2. Which agents exist, where are they, and can they communicate?
3. What is being requested, delivered, processed, blocked, approved, retried, or expired?
4. Which path, policy, gateway, or channel controls the communication?
5. What can I safely do next, and what will be audited?

Every UI screen must make one or more of these questions easier to answer. Decorative pages, marketing-only pages, hidden critical states, and optimistic fake success are plan failures.

### 0.2 No Fallback Success

The UI and backend must not do any of the following in production paths:

- Show mock KPI data when the API fails.
- Treat missing API endpoints as empty successful states.
- Hide failed authorization behind a generic blank page.
- Convert unknown role, unknown plan, unknown permission, unknown feature flag, or failed policy fetch into a permissive UI.
- Submit access applications without durable server-side persistence and audit evidence.
- Mark a request as sent unless the server returns a real created resource.
- Show “connected”, “delivered”, “healthy”, “approved”, or “protected” unless backed by actual API state.

Allowed exceptions:

- Test-only fixtures inside test files.
- Story/demo components only if they live outside production routes and are never bundled as live product behavior.
- UI skeleton/loading states while a real request is pending.

### 0.3 No Minimal Acceptance

Every phase must include:

- File-level deliverables.
- Unit/component tests.
- At least one failure-path test.
- Browser-level verification where UI is changed.
- Documentation update.
- A phase report under `reports/ui_phase_<n>_report.md`.
- Human review notes that inspect real code and visible behavior, not just test output.

### 0.4 Design Direction

Use the design references as inspiration only:

- Linear-like operational density: quiet side navigation, scannable tables, precise status labels.
- Vercel-like production surfaces: clear environment/status separation, restrained typography, no decorative dashboards.
- Notion-like onboarding clarity: simple request forms, progressive disclosure, readable empty states.

Do not copy logos, brand assets, colors, or proprietary layouts. AgentNet’s own identity should be calm, technical, enterprise-capable, and audit-oriented.

### 0.5 Visual System Rules

- No emoji in visible UI.
- No one-note blue/purple dashboard palette.
- Cards only for repeated items, modals, and framed tools; avoid nested cards.
- Use lucide icons for navigation and actions.
- Use segmented controls for Personal / Enterprise / Admin context switching.
- Use badges for state and risk.
- Use tables for operational data, not decorative grids.
- Keep compact layouts readable on 1440px desktop and 375px mobile.
- System pages must not reveal connection strings, secrets, raw env vars, tokens, or sensitive payloads.

---

## 1. Current UI Reality Check

### Existing Auth/Public Surface

Files:

- `apps/web/src/App.tsx`
- `apps/web/src/app/PublicLayout.tsx`
- `apps/web/src/features/auth/LoginPage.tsx`

Current state:

- Public route only exposes `/login`.
- Login requires username + API key.
- No visible request access, invite, personal bootstrap, enterprise contact, or admin seed explanation.
- PublicLayout redirects authenticated users to `/app/overview`.

Gap:

- New users cannot understand how to get access.
- Public production deployment should not present `/v1/auth/register` as a casual open signup without policy controls.

### Existing User Console

Files:

- `apps/web/src/app/AppLayout.tsx`
- `apps/web/src/features/overview/OverviewPage.tsx`
- `apps/web/src/features/agents/AgentsPage.tsx`
- `apps/web/src/features/agents/AgentDetailPage.tsx`
- `apps/web/src/features/tasks/TasksPage.tsx`
- `apps/web/src/features/tasks/TaskDetailPage.tsx`
- `apps/web/src/features/approvals/ApprovalsPage.tsx`
- `apps/web/src/features/connections/ConnectionsPage.tsx`
- `apps/web/src/features/api-keys/ApiKeysPage.tsx`

Current state:

- Basic pages exist.
- Personal and enterprise mental models are not separated.
- Navigation does not expose routing, local edge, egress, dedicated channels, SLA, continuity, or access request concepts.

Gap:

- The product looks like a simple personal dashboard even though the backend now contains enterprise-grade routing, egress, dedicated channel, SLA, observability, and audit capabilities.

### Existing Admin Console

Files:

- `apps/web/src/app/AdminLayout.tsx`
- `apps/web/src/features/admin/AdminOverviewPage.tsx`
- `apps/web/src/features/admin/AdminUsersPage.tsx`
- `apps/web/src/features/admin/AdminUserDetailPage.tsx`
- `apps/web/src/features/admin/AdminAgentsPage.tsx`
- `apps/web/src/features/admin/AdminAgentDetailPage.tsx`
- `apps/web/src/features/admin/AdminTasksPage.tsx`
- `apps/web/src/features/admin/AdminTaskDetailPage.tsx`
- `apps/web/src/features/admin/AuditLogsPage.tsx`
- `apps/web/src/features/admin/SystemHealthPage.tsx`

Current state:

- Admin routes exist and are role-gated.
- Admin banner contains an emoji and should be replaced.
- Enterprise operations are not grouped by risk or operational domain.

Gap:

- Admin console needs to become an enterprise operations console, not just a dark sidebar variant.

---

## 2. Target Information Architecture

### 2.1 Public Area

Routes:

- `/` public product entry, not marketing-heavy, explains access paths.
- `/login` secure sign-in.
- `/request-access` access application page.
- `/request-access/submitted` durable confirmation page using returned request id.
- `/invite/:token` reserved invite landing if backend support exists; otherwise show “invite validation unavailable” from a real 404/501 response, not fake success.

Public user choices:

- Personal: “I want to connect my own agents.”
- Enterprise: “I need managed scopes, policies, audit, routing, and operations.”
- Existing user: “Sign in.”

### 2.2 Personal Console

Base route: `/app`

Navigation groups:

- Home: Overview
- Agents: Agents, Agent Detail
- Work: Tasks, Task Detail
- Trust: Approvals, Connection Requests / Firewall
- Access: API Keys, Sessions
- Network: Local Routing, Edge Relays, Route Events

Personal emphasis:

- Local-first routing.
- Personal edge relay health.
- Agent delivery status: queued, delivered, acked, processing, completed, failed, expired.
- Simple mode controls: fast, balanced, reliable.

### 2.3 Enterprise Console

Base route: `/enterprise`

Access:

- `admin` and `super_admin` only.
- Unknown role fails closed to `/app/overview` with no enterprise data loaded.

Navigation groups:

- Command Center: Enterprise Overview
- Topology: Network Scopes, Zones, Relay Nodes, Route Policies
- Traffic: Route Decisions, Route Metrics, Egress Gateway, Dedicated Channels
- Governance: Users, Roles, Permissions, Approval Queues, Connection Firewall
- Continuity: SLA Targets, Incidents, Backup/Restore Drill Status
- Audit: Audit Logs, Viewed Resource Logs
- System: Health, Readiness, Dependencies, Alert Status

Enterprise emphasis:

- Policy-aware routing.
- Scope/zone topology.
- Egress governance.
- Dedicated channel management.
- Business continuity and SLA status.
- Audit evidence.

### 2.4 Admin Console Compatibility

Existing `/admin` routes may remain as compatibility aliases, but the UI should steer operators to `/enterprise`. Any alias must:

- Preserve RBAC checks.
- Not duplicate business logic.
- Not show different data for the same resource.

---

## 3. Phase Plan

## Phase UI-0: Public Entry And Access Request Contract

**Goal:** Replace the “login-only” public surface with explicit access paths and no fake signup success.

**Files:**

- Modify: `apps/web/src/App.tsx`
- Modify: `apps/web/src/app/PublicLayout.tsx`
- Modify: `apps/web/src/features/auth/LoginPage.tsx`
- Create: `apps/web/src/features/public/PublicHomePage.tsx`
- Create: `apps/web/src/features/public/RequestAccessPage.tsx`
- Create: `apps/web/src/features/public/RequestAccessSubmittedPage.tsx`
- Create: `apps/web/src/features/public/__tests__/RequestAccessPage.test.tsx`
- Create or modify backend only if missing: `apps/api/app/models/access_request.py`
- Create or modify backend only if missing: `apps/api/app/routers/access_requests.py`
- Create or modify backend only if missing: `apps/api/app/schemas/access_request.py`
- Create or modify migration only if backend persistence is missing.
- Create: `reports/ui_phase_0_report.md`

**Backend contract:**

If no durable access request API exists, implement:

```text
POST /v1/public/access-requests
GET /v1/dashboard/admin/access-requests
POST /v1/dashboard/admin/access-requests/{id}/approve
POST /v1/dashboard/admin/access-requests/{id}/reject
```

Required server behavior:

- Request is persisted.
- Duplicate email or organization request returns a real duplicate status, not generic success.
- Approval/rejection is admin-gated.
- Audit is written for create, approve, reject, and view list.
- No raw API key is emailed or displayed by the public request form.

UI behavior:

- `/` shows a compact operational product entry with three actions: Sign in, Request personal access, Request enterprise access.
- `/request-access` requires applicant name, email, use case, requested mode, and terms acknowledgement.
- Submit button remains disabled until fields are valid.
- Success page displays returned request id and next action.
- API failure displays the real failure state and does not navigate to success.

Tests:

- Component test: request form validates required fields.
- Component test: API 201 navigates to submitted page with request id.
- Failure test: API 409/500 keeps user on form and shows error.
- E2E: unauthenticated user can open `/`, `/login`, `/request-access`.

Acceptance:

- No code path displays “submitted” without a real server response.
- No production route uses localStorage or in-memory fake requests as persistence.
- Secret scan remains clean.
- `npm run lint`, `npm run typecheck`, `npm test`, `npm run build`, Playwright smoke pass.
- Backend pytest passes if backend files are changed.

## Phase UI-1: Unified Product Shell And Mode Switch

**Goal:** Build a coherent dashboard shell that clearly separates Personal, Enterprise, and Admin/Super Admin operations.

**Files:**

- Modify: `apps/web/src/app/AppLayout.tsx`
- Modify: `apps/web/src/app/AdminLayout.tsx`
- Create: `apps/web/src/app/DashboardShell.tsx`
- Create: `apps/web/src/app/navigation.ts`
- Create: `apps/web/src/app/__tests__/DashboardShell.test.tsx`
- Create: `reports/ui_phase_1_report.md`

Design requirements:

- Replace duplicate App/Admin layout logic with a shared shell.
- Add context switcher:
  - Personal
  - Enterprise, visible only to `admin` / `super_admin`
  - System Admin, visible only where separate admin operations remain
- Navigation groups must be explicit and collapsible on mobile.
- Header must show username, role, active scope/mode, session expiry indicator, and step-up state when available.
- Remove emoji from admin banner.
- Use neutral enterprise palette with restrained accents for risk, health, route, and approval states.

Failure behavior:

- Unknown role shows no enterprise navigation.
- Missing `permissions` array shows no privileged actions.
- Auth loading state must not flash privileged navigation.

Tests:

- Regular user sees Personal nav only.
- Admin sees Personal + Enterprise switch.
- Super admin sees high-risk admin actions.
- Unknown role sees Personal only.
- Mobile nav can open/close without layout overflow.

Acceptance:

- No duplicated route permission assumptions in UI without backend checks.
- No text overlaps at 375px width.
- No emoji.

## Phase UI-2: Personal Console Redesign

**Goal:** Make the personal console useful for individual operators and small local networks.

**Files:**

- Modify: `apps/web/src/features/overview/OverviewPage.tsx`
- Modify: `apps/web/src/features/agents/AgentsPage.tsx`
- Modify: `apps/web/src/features/agents/AgentDetailPage.tsx`
- Modify: `apps/web/src/features/tasks/TasksPage.tsx`
- Modify: `apps/web/src/features/tasks/TaskDetailPage.tsx`
- Modify: `apps/web/src/features/connections/ConnectionsPage.tsx`
- Create: `apps/web/src/features/routing/PersonalRoutingPage.tsx`
- Create: `apps/web/src/features/routing/RouteEventsPage.tsx`
- Create: `apps/web/src/features/routing/__tests__/PersonalRoutingPage.test.tsx`
- Create: `reports/ui_phase_2_report.md`

Required user-facing capabilities:

- Overview shows actual agent count, online count, pending approvals, failed deliveries, queue health, and recent route decisions from API.
- Agents page shows online/offline/disabled state, current relay, egress gateway assignment, last seen, and delivery capability.
- Agent detail shows:
  - identity and token status;
  - connection policy;
  - routing preference;
  - local edge relay status;
  - recent tasks and messages.
- Tasks list shows delivery lifecycle columns:
  - created;
  - route selected;
  - delivered;
  - acked;
  - processing;
  - completed/failed/expired.
- Task detail shows timeline with message id, route decision id, lease expiry, retry count, approval state.
- Connections page becomes “Connection Requests / Firewall” with inbound/outbound tabs.
- Personal routing page shows fast/balanced/reliable mode mapped to real timeliness configuration.

Failure behavior:

- If a routing API is unavailable, show a blocking error state, not empty metrics.
- If a task has no delivery event, show “No delivery event recorded” only when API explicitly returns none.
- If a message is unacked, show pending/expired based on real timestamps.

Tests:

- Task lifecycle renders all supported statuses.
- Unacked message state is visible.
- Failed route decision shows error code.
- Personal routing mode update requires API success.

Acceptance:

- A personal user can answer: “Did the other agent receive it, ack it, process it, or fail?”
- No UI invents delivery status client-side without server state.

## Phase UI-3: Enterprise Console Pages

**Goal:** Expose enterprise routing, governance, continuity, and audit as first-class operational surfaces.

**Files:**

- Modify: `apps/web/src/App.tsx`
- Create: `apps/web/src/app/EnterpriseLayout.tsx` or use `DashboardShell.tsx`
- Create: `apps/web/src/features/enterprise/EnterpriseOverviewPage.tsx`
- Create: `apps/web/src/features/enterprise/NetworkScopesPage.tsx`
- Create: `apps/web/src/features/enterprise/NetworkZonesPage.tsx`
- Create: `apps/web/src/features/enterprise/RelayNodesPage.tsx`
- Create: `apps/web/src/features/enterprise/RoutePoliciesPage.tsx`
- Create: `apps/web/src/features/enterprise/RouteDecisionsPage.tsx`
- Create: `apps/web/src/features/enterprise/EgressGatewaysPage.tsx`
- Create: `apps/web/src/features/enterprise/DedicatedChannelsPage.tsx`
- Create: `apps/web/src/features/enterprise/SlaAndContinuityPage.tsx`
- Create: `apps/web/src/features/enterprise/__tests__/*.test.tsx`
- Create: `reports/ui_phase_3_report.md`

Required enterprise capabilities:

- Topology:
  - scopes;
  - zones;
  - relay nodes;
  - health;
  - queue depth;
  - route policy assignment.
- Traffic:
  - route decisions;
  - fallback/failover events;
  - egress requests;
  - dedicated channel state.
- Governance:
  - user role matrix;
  - high-risk action visibility;
  - approval queues split by task action, connection request, egress request, route policy change.
- Continuity:
  - SLA target status;
  - incidents;
  - backup drill latest status;
  - restore readiness checklist.
- Audit:
  - who viewed what;
  - who changed what;
  - filtering by actor, action, resource, risk, time.

Failure behavior:

- Enterprise pages fail closed on 403 and show no partial privileged data.
- System/dependency failures are visible and actionable.
- High-risk mutation buttons require step-up state from backend.

Tests:

- Admin can open enterprise pages.
- Regular user is redirected and no enterprise request is fired after auth role is known.
- 403 response shows access denied.
- High-risk button opens step-up dialog.
- System page masks secret-like values.

Acceptance:

- Enterprise operator can see routing, egress, dedicated channels, SLA, audit, and governance from navigation.
- No enterprise data appears for regular users.

## Phase UI-4: Application Review And Onboarding Operations

**Goal:** Complete the access request lifecycle for administrators.

**Files:**

- Create: `apps/web/src/features/enterprise/AccessRequestsPage.tsx`
- Create: `apps/web/src/features/enterprise/AccessRequestDetailPage.tsx`
- Create: `apps/web/src/features/enterprise/__tests__/AccessRequestsPage.test.tsx`
- Modify: `apps/web/src/App.tsx`
- Modify: `apps/web/src/app/navigation.ts`
- Create: `reports/ui_phase_4_report.md`

Required flow:

- Public request creates durable pending request.
- Admin list shows pending, approved, rejected, expired.
- Admin detail shows applicant info, requested mode, risk notes, audit trail.
- Approve personal request creates/links user and prepares API key issuance flow.
- Approve enterprise request creates/links enterprise scope and owner admin assignment.
- Reject requires reason.
- Every action is audited.

No fallback:

- If approval API fails, status remains pending in UI.
- If API key creation fails, do not mark request approved.
- If scope creation fails, do not mark request approved.

Tests:

- Approve success transitions status.
- Reject without reason is blocked.
- Approve failure remains pending.
- Regular user cannot see page.

Acceptance:

- There is a real answer to “how does someone apply for dashboard access?”

## Phase UI-5: Visual Polish And Responsive Hardening

**Goal:** Bring the dashboard to production UI quality without masking operational data.

**Files:**

- Modify: `apps/web/src/index.css`
- Modify shared components under `apps/web/src/components`
- Create or modify component tests as needed.
- Create: `reports/ui_phase_5_report.md`

Requirements:

- Define design tokens for:
  - background;
  - surface;
  - border;
  - text;
  - muted text;
  - success;
  - warning;
  - danger;
  - route;
  - audit;
  - enterprise.
- Ensure dark admin/enterprise surfaces do not dominate the whole app unless the user chooses dark mode.
- Add accessible focus states.
- Ensure tables have responsive horizontal scroll where needed.
- Ensure buttons never overflow on mobile.
- Ensure empty/error/loading states are consistent.

Tests:

- Component tests for empty/error/loading states.
- Playwright screenshots for:
  - `/`;
  - `/login`;
  - `/request-access`;
  - `/app/overview`;
  - `/app/tasks/:id`;
  - `/enterprise/overview`;
  - `/enterprise/system`.

Acceptance:

- Manual screenshot review records no overlapping text, hidden buttons, or ambiguous risk states.

## Phase UI-6: Real API Browser End-To-End

**Goal:** Prove that the UI is not only pretty, but wired to real backend behavior.

**Files:**

- Create: `apps/web/e2e/authenticated.spec.ts`
- Create: `apps/web/e2e/access-request.spec.ts`
- Create: `apps/web/e2e/enterprise.spec.ts`
- Modify: `apps/web/playwright.config.ts` only if needed.
- Create: `reports/ui_phase_6_report.md`

Required E2E flows:

- Public access request success and failure.
- Login with real API key from test fixture.
- Regular user:
  - sees Personal console;
  - does not see Enterprise console;
  - can list agents/tasks;
  - sees connection/firewall page.
- Admin:
  - sees Enterprise console;
  - can view access requests;
  - can view audit/system without secrets.
- Task detail:
  - shows delivered/acked/processing/final state from seeded backend data.
- Failure path:
  - API 500 shows blocking error state;
  - 403 hides privileged data.

No fallback:

- Do not intercept all APIs with fake success.
- Test seeding may create real test rows through backend or direct DB fixtures, but the browser must call the real API.

Acceptance:

- E2E is run against local FastAPI + Postgres + Redis + built web app.
- Any skipped E2E must be reported with a concrete blocker and risk.

---

## 4. Final Acceptance Gate

Run from repository root unless specified:

```powershell
docker compose -f infra/docker-compose.yml up -d postgres redis
cd apps/api
$env:PYTHONPATH='../../adapters/base;../../adapters/openclaw'
alembic upgrade head
python -m pytest -q
cd ../..
python -m compileall -q apps/api/app adapters/base adapters/openclaw scripts tests/real_openclaw
cd apps/web
npm run lint
npm run typecheck
npm test
npm run build
npx playwright test
cd ../..
$env:PYTHONPATH='apps/api;adapters/base;adapters/openclaw'
python scripts/export_openapi.py --check
docker compose -f infra/docker-compose.yml -f infra/docker-compose.dev.yml config --quiet
docker compose -f infra/docker-compose.prod.yml --env-file infra/.env.production.example config --quiet
```

Manual review checklist:

- Public area includes Sign in and Request access.
- Login does not imply open self-service registration unless production config enables it.
- Personal console and Enterprise console are visually and conceptually distinct.
- User, admin, and super admin roles see different capabilities.
- Unknown role and missing permissions fail closed.
- Delivery state answers received / acked / processing / completed / failed.
- Routing, egress, dedicated channels, SLA, audit, and system health are represented in navigation.
- System pages do not reveal secrets, connection strings, raw env vars, tokens, or private payloads.
- No emoji appear in visible UI.
- No mock/fake/memory-only success is used in production routes.
- 375px mobile, 768px tablet, 1440px desktop screenshots have no overlapping text.

Final report:

- Create `reports/ui_final_acceptance_report.md`.
- Include commands, results, screenshots reviewed, gaps, risks, and final decision.


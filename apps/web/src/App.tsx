import { lazy, Suspense } from 'react';
import { Navigate, Route, Routes, useLocation } from 'react-router-dom';
import { useAuth } from './hooks/useAuth';
import AppLayout from './app/AppLayout';
import AdminLayout from './app/AdminLayout';
import LoadingState from './components/LoadingState';
import { hasEnterpriseConsoleAccess } from './lib/permissions';
import { DEFAULT_LOCALE, getLocale, loadNamespaces } from './i18n/core';

/**
 * Route-level code splitting.
 *
 * Page groups (and their i18n namespaces) load on demand:
 * - public pages (login, home, request access) + the docs namespace the
 *   public shell footer renders,
 * - the personal console `/app/*`,
 * - admin/enterprise pages (one chunk),
 * - the `/docs` sub-site, which drags the react-markdown/remark chain and
 *   the whole docs registry - the biggest byte block in the bundle.
 *
 * Each lazy import also loads the i18n namespaces the page renders (active
 * locale + English fallback) before the component mounts, so `t()` stays
 * synchronous and never falls through to a raw key. Infra namespaces
 * (common/nav/shell) are eager - see src/i18n/core.ts.
 */
function lazyPage<T extends { default: React.ComponentType }>(
  loader: () => Promise<T>,
  namespaces: readonly string[],
) {
  return lazy(() =>
    loader().then(async (module) => {
      const active = getLocale();
      await Promise.all([
        loadNamespaces(active, namespaces),
        loadNamespaces(DEFAULT_LOCALE, namespaces),
      ]);
      return module;
    }),
  );
}

// --- Public surface --------------------------------------------------------
const PublicLayout = lazyPage(() => import('./app/PublicLayout'), ['docs']);
const LoginPage = lazyPage(() => import('./features/auth/LoginPage'), ['auth']);
const PublicHomePage = lazyPage(() => import('./features/public/PublicHomePage'), ['public']);
const RequestAccessPage = lazyPage(() => import('./features/public/RequestAccessPage'), ['public']);
const RequestAccessSubmittedPage = lazyPage(
  () => import('./features/public/RequestAccessSubmittedPage'),
  ['public'],
);

// --- Docs sub-site (one chunk: pages + registry + markdown chain) -----------
// All three pages are reached through the docsSite barrel so Vite emits the
// whole sub-site (incl. react-markdown/remark and the docs registry) as a
// single lazy chunk; see features/docs/docsSite.ts.
const docsSite = () => import('./features/docs/docsSite');
const docsNamespaces = ['docs'] as const;
const DocsLayout = lazy(() =>
  docsSite().then(async (module) => {
    const active = getLocale();
    await Promise.all([
      loadNamespaces(active, docsNamespaces),
      loadNamespaces(DEFAULT_LOCALE, docsNamespaces),
    ]);
    return { default: module.DocsLayout };
  }),
);
const DocsPage = lazy(() =>
  docsSite().then(async (module) => {
    const active = getLocale();
    await Promise.all([
      loadNamespaces(active, docsNamespaces),
      loadNamespaces(DEFAULT_LOCALE, docsNamespaces),
    ]);
    return { default: module.DocsPage };
  }),
);
const ApiReferencePage = lazy(() =>
  docsSite().then(async (module) => {
    const active = getLocale();
    await Promise.all([
      loadNamespaces(active, docsNamespaces),
      loadNamespaces(DEFAULT_LOCALE, docsNamespaces),
    ]);
    return { default: module.ApiReferencePage };
  }),
);

// --- Personal console `/app` ------------------------------------------------
const OverviewPage = lazyPage(() => import('./features/overview/OverviewPage'), ['overview']);
const AgentsPage = lazyPage(() => import('./features/agents/AgentsPage'), ['agents']);
const AgentDetailPage = lazyPage(
  () => import('./features/agents/AgentDetailPage'),
  ['agents'],
);
const TasksPage = lazyPage(() => import('./features/tasks/TasksPage'), ['tasks']);
const TaskDetailPage = lazyPage(() => import('./features/tasks/TaskDetailPage'), ['tasks']);
const ApprovalsPage = lazyPage(() => import('./features/approvals/ApprovalsPage'), ['approvals']);
const ConnectionsPage = lazyPage(
  () => import('./features/connections/ConnectionsPage'),
  ['connections'],
);
const ApiKeysPage = lazyPage(() => import('./features/api-keys/ApiKeysPage'), ['apiKeys']);
const PersonalRoutingPage = lazyPage(
  () => import('./features/routing/PersonalRoutingPage'),
  ['routing'],
);
const SettingsPage = lazyPage(() => import('./features/settings/SettingsPage'), ['settings']);

// --- Admin / enterprise console (one chunk) ---------------------------------
const AdminUsersPage = lazyPage(() => import('./features/admin/AdminUsersPage'), ['admin']);
const AdminUserDetailPage = lazyPage(
  () => import('./features/admin/AdminUserDetailPage'),
  ['admin'],
);
const AdminAgentsPage = lazyPage(() => import('./features/admin/AdminAgentsPage'), ['admin']);
const AdminAgentDetailPage = lazyPage(
  () => import('./features/admin/AdminAgentDetailPage'),
  ['admin'],
);
const AdminTasksPage = lazyPage(() => import('./features/admin/AdminTasksPage'), ['admin']);
const AdminTaskDetailPage = lazyPage(
  () => import('./features/admin/AdminTaskDetailPage'),
  ['admin'],
);
const AuditLogsPage = lazyPage(() => import('./features/admin/AuditLogsPage'), ['admin']);
const SystemHealthPage = lazyPage(() => import('./features/admin/SystemHealthPage'), ['admin']);

const EnterpriseOverviewPage = lazyPage(
  () => import('./features/enterprise/EnterpriseOverviewPage'),
  ['enterprise'],
);
const RelayNodesPage = lazyPage(
  () => import('./features/enterprise/RelayNodesPage'),
  ['enterprise'],
);
const RoutePoliciesPage = lazyPage(
  () => import('./features/enterprise/RoutePoliciesPage'),
  ['enterprise'],
);
const RouteDecisionsPage = lazyPage(
  () => import('./features/enterprise/RouteDecisionsPage'),
  ['enterprise'],
);
const EgressGatewaysPage = lazyPage(
  () => import('./features/enterprise/EgressGatewaysPage'),
  ['enterprise'],
);
const DedicatedChannelsPage = lazyPage(
  () => import('./features/enterprise/DedicatedChannelsPage'),
  ['enterprise'],
);
const AccessRequestsPage = lazyPage(
  () => import('./features/enterprise/AccessRequestsPage'),
  ['enterprise'],
);
const AccessRequestDetailPage = lazyPage(
  () => import('./features/enterprise/AccessRequestDetailPage'),
  ['enterprise'],
);
const NetworkScopesPage = lazyPage(
  () => import('./features/enterprise/NetworkScopesPage'),
  ['enterprise'],
);
const NetworkZonesPage = lazyPage(
  () => import('./features/enterprise/NetworkZonesPage'),
  ['enterprise'],
);
const SlaAndContinuityPage = lazyPage(
  () => import('./features/enterprise/SlaAndContinuityPage'),
  ['enterprise'],
);
const OrgMembersPage = lazyPage(
  () => import('./features/enterprise/OrgMembersPage'),
  ['enterprise'],
);

const NoAccessPage = lazyPage(() => import('./features/no-access/NoAccessPage'), ['noAccess']);

const pageFallback = <LoadingState />;

/**
 * Global-scope permission names from the backend RBAC map
 * (apps/api/app/services/rbac_service.py, ROLE_PERMISSIONS for admin and
 * super_admin). Possession of any one of them grants the enterprise
 * console; the guard stays fail-closed without them.
 *
 * The set lives in src/lib/permissions.ts, which also carries the
 * org-domain mapping: an organization manager/member is admitted on their
 * ':org' permission strings alone ('overview:read:org', 'org:manage', ... -
 * the exact list /me.permissions echoes per the backend contract).
 */

/** Build the login redirect target carrying the current path + search. */
function useLoginRedirectPath(): string {
  const { pathname, search } = useLocation();
  return `/login?next=${encodeURIComponent(pathname + search)}`;
}

export function RequireAuth({ children }: { children: React.ReactNode }) {
  const { data, isLoading, isError } = useAuth();
  const loginPath = useLoginRedirectPath();
  if (isLoading) return <LoadingState />;
  if (isError || !data) {
    // Truly unauthenticated: go pick up credentials, keep the deep link.
    return <Navigate to={loginPath} replace />;
  }
  // Fail-closed: a session without any granted permission
  // (`/me.permissions`) is not allowed past the guard. Redirect to login
  // would loop (PublicLayout bounces an authenticated session straight back
  // to next), so an authenticated-but-empty session lands on the public
  // no-access page instead.
  if (!Array.isArray(data.permissions) || data.permissions.length === 0) {
    return <Navigate to="/no-access" replace />;
  }
  return <>{children}</>;
}

export function RequireAdmin({ children }: { children: React.ReactNode }) {
  const { data, isLoading, isError } = useAuth();
  const loginPath = useLoginRedirectPath();
  if (isLoading) return <LoadingState />;
  if (isError || !data) {
    return <Navigate to={loginPath} replace />;
  }
  if (!Array.isArray(data.permissions) || data.permissions.length === 0) {
    return <Navigate to="/no-access" replace />;
  }
  // Fail-closed: the enterprise console requires at least one global-scope
  // permission from the backend RBAC map, OR the equivalent org-domain
  // permission ('overview:read:org', 'org:manage', ... - the strings
  // /me.permissions echoes for organization managers/members). Role names
  // are not trusted; super_admin still passes on its global union.
  // An authenticated session lacking both goes to the no-access page, not
  // /login?next=... (that would loop - PublicLayout sends an authenticated
  // visitor straight back to next).
  if (!hasEnterpriseConsoleAccess(data.permissions)) {
    return <Navigate to="/no-access" replace />;
  }
  return <>{children}</>;
}

/**
 * Route-level alias: every legacy `/admin/*` path maps onto the enterprise
 * console (`/admin/overview` -> `/enterprise/overview`), keeping sub-paths
 * and the query string. Unauthenticated visitors hit RequireAdmin on the
 * destination and end up on `/login?next=...`, matching e2e/admin.spec.ts.
 */
function AdminAliasRedirect() {
  const { pathname, search } = useLocation();
  const rest = pathname.slice('/admin'.length);
  return <Navigate to={`/enterprise${rest}${search}`} replace />;
}

export default function App() {
  return (
    <Suspense fallback={pageFallback}>
      <Routes>
        {/* Public routes */}
        <Route element={<PublicLayout />}>
          <Route path="/" element={<PublicHomePage />} />
          <Route path="/login" element={<LoginPage />} />
          <Route path="/request-access" element={<RequestAccessPage />} />
          <Route path="/request-access/submitted" element={<RequestAccessSubmittedPage />} />
          <Route path="/no-access" element={<NoAccessPage />} />

          {/* Public docs site: no sign-in required. */}
          <Route path="/docs" element={<DocsLayout />}>
            <Route index element={<Navigate to="quickstart" replace />} />
            <Route path="api-reference" element={<ApiReferencePage />} />
            <Route path=":docId" element={<DocsPage />} />
          </Route>
        </Route>

        {/* Personal console */}
        <Route
          path="/app"
          element={
            <RequireAuth>
              <AppLayout />
            </RequireAuth>
          }
        >
          <Route index element={<Navigate to="overview" replace />} />
          <Route path="overview" element={<OverviewPage />} />
          <Route path="agents" element={<AgentsPage />} />
          <Route path="agents/:agentId" element={<AgentDetailPage />} />
          <Route path="tasks" element={<TasksPage />} />
          <Route path="tasks/:taskId" element={<TaskDetailPage />} />
          <Route path="approvals" element={<ApprovalsPage />} />
          <Route path="connections" element={<ConnectionsPage />} />
          <Route path="api-keys" element={<ApiKeysPage />} />
          <Route path="routing" element={<PersonalRoutingPage />} />
          <Route path="settings" element={<SettingsPage />} />
        </Route>

        {/* Legacy /admin alias: redirects into the enterprise console. */}
        <Route path="/admin" element={<AdminAliasRedirect />} />
        <Route path="/admin/*" element={<AdminAliasRedirect />} />

        {/* Enterprise console: dedicated pages for routing, egress, SLA, etc. */}
        <Route
          path="/enterprise"
          element={
            <RequireAdmin>
              <AdminLayout />
            </RequireAdmin>
          }
        >
          <Route index element={<Navigate to="overview" replace />} />
          <Route path="overview" element={<EnterpriseOverviewPage />} />
          {/* Organization members (org-domain managers; see OrgMembersPage) */}
          <Route path="members" element={<OrgMembersPage />} />
          <Route path="relay-nodes" element={<RelayNodesPage />} />
          <Route path="route-policies" element={<RoutePoliciesPage />} />
          <Route path="route-decisions" element={<RouteDecisionsPage />} />
          <Route path="egress" element={<EgressGatewaysPage />} />
          <Route path="dedicated-channels" element={<DedicatedChannelsPage />} />
          <Route path="access-requests" element={<AccessRequestsPage />} />
          <Route path="access-requests/:requestId" element={<AccessRequestDetailPage />} />
          <Route path="network-scopes" element={<NetworkScopesPage />} />
          <Route path="network-zones" element={<NetworkZonesPage />} />
          {/* Reuse admin pages for shared resources */}
          <Route path="users" element={<AdminUsersPage />} />
          <Route path="users/:userId" element={<AdminUserDetailPage />} />
          <Route path="agents" element={<AdminAgentsPage />} />
          <Route path="agents/:agentId" element={<AdminAgentDetailPage />} />
          <Route path="tasks" element={<AdminTasksPage />} />
          <Route path="tasks/:taskId" element={<AdminTaskDetailPage />} />
          <Route path="audit" element={<AuditLogsPage />} />
          <Route path="system" element={<SystemHealthPage />} />
          <Route path="sla" element={<SlaAndContinuityPage />} />
        </Route>

        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Suspense>
  );
}

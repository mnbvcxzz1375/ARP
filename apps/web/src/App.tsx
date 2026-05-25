import { Routes, Route, Navigate } from 'react-router-dom';
import { useAuth } from './hooks/useAuth';
import PublicLayout from './app/PublicLayout';
import AppLayout from './app/AppLayout';
import AdminLayout from './app/AdminLayout';
import LoginPage from './features/auth/LoginPage';
import PublicHomePage from './features/public/PublicHomePage';
import RequestAccessPage from './features/public/RequestAccessPage';
import RequestAccessSubmittedPage from './features/public/RequestAccessSubmittedPage';
import OverviewPage from './features/overview/OverviewPage';
import AgentsPage from './features/agents/AgentsPage';
import AgentDetailPage from './features/agents/AgentDetailPage';
import TasksPage from './features/tasks/TasksPage';
import TaskDetailPage from './features/tasks/TaskDetailPage';
import ApprovalsPage from './features/approvals/ApprovalsPage';
import ConnectionsPage from './features/connections/ConnectionsPage';
import ApiKeysPage from './features/api-keys/ApiKeysPage';
import PersonalRoutingPage from './features/routing/PersonalRoutingPage';
import AdminOverviewPage from './features/admin/AdminOverviewPage';
import AdminUsersPage from './features/admin/AdminUsersPage';
import AdminUserDetailPage from './features/admin/AdminUserDetailPage';
import AdminAgentsPage from './features/admin/AdminAgentsPage';
import AdminAgentDetailPage from './features/admin/AdminAgentDetailPage';
import AdminTasksPage from './features/admin/AdminTasksPage';
import AdminTaskDetailPage from './features/admin/AdminTaskDetailPage';
import AuditLogsPage from './features/admin/AuditLogsPage';
import SystemHealthPage from './features/admin/SystemHealthPage';
import EnterpriseOverviewPage from './features/enterprise/EnterpriseOverviewPage';
import RelayNodesPage from './features/enterprise/RelayNodesPage';
import RoutePoliciesPage from './features/enterprise/RoutePoliciesPage';
import RouteDecisionsPage from './features/enterprise/RouteDecisionsPage';
import EgressGatewaysPage from './features/enterprise/EgressGatewaysPage';
import DedicatedChannelsPage from './features/enterprise/DedicatedChannelsPage';
import AccessRequestsPage from './features/enterprise/AccessRequestsPage';
import AccessRequestDetailPage from './features/enterprise/AccessRequestDetailPage';
import NetworkScopesPage from './features/enterprise/NetworkScopesPage';
import NetworkZonesPage from './features/enterprise/NetworkZonesPage';
import SlaAndContinuityPage from './features/enterprise/SlaAndContinuityPage';
import LoadingState from './components/LoadingState';

function RequireAuth({ children }: { children: React.ReactNode }) {
  const { isLoading, isError } = useAuth();
  if (isLoading) return <LoadingState />;
  if (isError) return <Navigate to="/login" replace />;
  return <>{children}</>;
}

function RequireAdmin({ children }: { children: React.ReactNode }) {
  const { data, isLoading, isError } = useAuth();
  if (isLoading) return <LoadingState />;
  if (isError) return <Navigate to="/login" replace />;
  if (data?.role !== 'admin' && data?.role !== 'super_admin') {
    return <Navigate to="/app/overview" replace />;
  }
  return <>{children}</>;
}

export default function App() {
  return (
    <Routes>
      {/* Public routes */}
      <Route element={<PublicLayout />}>
        <Route path="/" element={<PublicHomePage />} />
        <Route path="/login" element={<LoginPage />} />
        <Route path="/request-access" element={<RequestAccessPage />} />
        <Route path="/request-access/submitted" element={<RequestAccessSubmittedPage />} />
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
      </Route>

      {/* Admin console (compatibility alias — enterprise routes preferred) */}
      <Route
        path="/admin"
        element={
          <RequireAdmin>
            <AdminLayout />
          </RequireAdmin>
        }
      >
        <Route index element={<Navigate to="overview" replace />} />
        <Route path="overview" element={<AdminOverviewPage />} />
        <Route path="users" element={<AdminUsersPage />} />
        <Route path="users/:userId" element={<AdminUserDetailPage />} />
        <Route path="agents" element={<AdminAgentsPage />} />
        <Route path="agents/:agentId" element={<AdminAgentDetailPage />} />
        <Route path="tasks" element={<AdminTasksPage />} />
        <Route path="tasks/:taskId" element={<AdminTaskDetailPage />} />
        <Route path="audit" element={<AuditLogsPage />} />
        <Route path="system" element={<SystemHealthPage />} />
      </Route>

      {/* Enterprise console — dedicated pages for routing, egress, SLA, etc. */}
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
        <Route path="relay-nodes" element={<RelayNodesPage />} />
        <Route path="route-policies" element={<RoutePoliciesPage />} />
        <Route path="route-decisions" element={<RouteDecisionsPage />} />
        <Route path="egress" element={<EgressGatewaysPage />} />
        <Route path="dedicated-channels" element={<DedicatedChannelsPage />} />
        <Route path="access-requests" element={<AccessRequestsPage />} />
        <Route path="access-requests/:requestId" element={<AccessRequestDetailPage />} />
        <Route path="network-scopes" element={<NetworkScopesPage />} />
        <Route path="network-zones" element={<NetworkZonesPage />} />
        <Route path="approvals" element={<ApprovalsPage />} />
        <Route path="sla" element={<SlaAndContinuityPage />} />
        {/* Reuse admin pages for shared resources */}
        <Route path="users" element={<AdminUsersPage />} />
        <Route path="users/:userId" element={<AdminUserDetailPage />} />
        <Route path="agents" element={<AdminAgentsPage />} />
        <Route path="agents/:agentId" element={<AdminAgentDetailPage />} />
        <Route path="tasks" element={<AdminTasksPage />} />
        <Route path="tasks/:taskId" element={<AdminTaskDetailPage />} />
        <Route path="audit" element={<AuditLogsPage />} />
        <Route path="system" element={<SystemHealthPage />} />
      </Route>

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
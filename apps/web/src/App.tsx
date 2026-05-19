import { Routes, Route, Navigate } from 'react-router-dom';
import { useAuth } from './hooks/useAuth';
import PublicLayout from './app/PublicLayout';
import AppLayout from './app/AppLayout';
import AdminLayout from './app/AdminLayout';
import LoginPage from './features/auth/LoginPage';
import OverviewPage from './features/overview/OverviewPage';
import AgentsPage from './features/agents/AgentsPage';
import TasksPage from './features/tasks/TasksPage';
import ApprovalsPage from './features/approvals/ApprovalsPage';
import ConnectionsPage from './features/connections/ConnectionsPage';
import ApiKeysPage from './features/api-keys/ApiKeysPage';
import AdminOverviewPage from './features/admin/AdminOverviewPage';
import AdminUsersPage from './features/admin/AdminUsersPage';
import AdminAgentsPage from './features/admin/AdminAgentsPage';
import AdminTasksPage from './features/admin/AdminTasksPage';
import AuditLogsPage from './features/admin/AuditLogsPage';
import SystemHealthPage from './features/admin/SystemHealthPage';
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
      <Route element={<PublicLayout />}>
        <Route path="/login" element={<LoginPage />} />
      </Route>

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
        <Route path="tasks" element={<TasksPage />} />
        <Route path="approvals" element={<ApprovalsPage />} />
        <Route path="connections" element={<ConnectionsPage />} />
        <Route path="api-keys" element={<ApiKeysPage />} />
      </Route>

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
        <Route path="agents" element={<AdminAgentsPage />} />
        <Route path="tasks" element={<AdminTasksPage />} />
        <Route path="audit" element={<AuditLogsPage />} />
        <Route path="system" element={<SystemHealthPage />} />
      </Route>

      <Route path="*" element={<Navigate to="/app/overview" replace />} />
    </Routes>
  );
}

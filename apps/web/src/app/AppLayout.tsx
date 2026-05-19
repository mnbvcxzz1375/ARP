import { useState } from 'react';
import { Outlet, Link, useLocation, useNavigate } from 'react-router-dom';
import {
  LayoutDashboard, Cpu, ListTodo, CheckSquare, GitBranch, Key, LogOut, Menu, X, Shield,
} from 'lucide-react';
import { useAuth, useLogout } from '../hooks/useAuth';
import RoleBadge from '../components/RoleBadge';
import LoadingState from '../components/LoadingState';

const NAV_ITEMS = [
  { to: '/app/overview', label: 'Overview', icon: LayoutDashboard },
  { to: '/app/agents', label: 'Agents', icon: Cpu },
  { to: '/app/tasks', label: 'Tasks', icon: ListTodo },
  { to: '/app/approvals', label: 'Approvals', icon: CheckSquare },
  { to: '/app/connections', label: 'Connections', icon: GitBranch },
  { to: '/app/api-keys', label: 'API Keys', icon: Key },
];

const ADMIN_NAV_ITEMS = [
  { to: '/admin/overview', label: 'Overview', icon: LayoutDashboard },
  { to: '/admin/users', label: 'Users', icon: Shield },
  { to: '/admin/agents', label: 'Agents', icon: Cpu },
  { to: '/admin/tasks', label: 'Tasks', icon: ListTodo },
  { to: '/admin/audit', label: 'Audit', icon: GitBranch },
  { to: '/admin/system', label: 'System', icon: Shield },
];

export default function AppLayout() {
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const { data, isLoading } = useAuth();
  const logout = useLogout();
  const location = useLocation();
  const navigate = useNavigate();

  const navItems = data?.role === 'admin' || data?.role === 'super_admin' ? [...NAV_ITEMS, ...ADMIN_NAV_ITEMS] : NAV_ITEMS;

  if (isLoading) return <LoadingState />;

  return (
    <div className="flex h-screen bg-gray-50">
      {/* Sidebar */}
      <aside className={`${sidebarOpen ? 'w-56' : 'w-16'} bg-white border-r border-gray-200 flex flex-col transition-all duration-200`}>
        <div className="flex items-center justify-between h-14 px-4 border-b border-gray-200">
          {sidebarOpen && <span className="font-bold text-lg">AgentNet</span>}
          <button onClick={() => setSidebarOpen(!sidebarOpen)} className="p-1 hover:bg-gray-100 rounded">
            {sidebarOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
          </button>
        </div>
        <nav className="flex-1 p-2 space-y-1">
          {navItems.map((item) => {
            const active = location.pathname === item.to || location.pathname.startsWith(item.to + '/');
            return (
              <Link
                key={item.to}
                to={item.to}
                className={`flex items-center gap-3 px-3 py-2 rounded text-sm font-medium ${
                  active ? 'bg-blue-50 text-blue-700' : 'text-gray-600 hover:bg-gray-100'
                }`}
              >
                <item.icon className="h-4 w-4 shrink-0" />
                {sidebarOpen && item.label}
              </Link>
            );
          })}
        </nav>
        <div className="p-2 border-t border-gray-200">
          <button
            onClick={() => logout.mutate()}
            className="flex items-center gap-3 px-3 py-2 rounded text-sm font-medium text-gray-600 hover:bg-gray-100 w-full"
          >
            <LogOut className="h-4 w-4" />
            {sidebarOpen && 'Logout'}
          </button>
        </div>
      </aside>

      {/* Main */}
      <div className="flex-1 flex flex-col overflow-hidden">
        <header className="h-14 bg-white border-b border-gray-200 flex items-center justify-between px-6">
          <h1 className="text-sm font-medium text-gray-500">
            {navItems.find(n => location.pathname.startsWith(n.to))?.label || 'Dashboard'}
          </h1>
          <div className="flex items-center gap-3">
            {data?.role === 'admin' || data?.role === 'super_admin' ? (
              <button
                onClick={() => navigate('/admin/overview')}
                className="px-3 py-1 text-xs font-medium bg-red-100 text-red-700 rounded hover:bg-red-200"
              >
                Admin Panel
              </button>
            ) : null}
            <span className="text-sm text-gray-600">{data?.username}</span>
            {data?.role && <RoleBadge role={data.role} />}
          </div>
        </header>
        <main className="flex-1 overflow-auto p-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
}

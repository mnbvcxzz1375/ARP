import { useState } from 'react';
import { Outlet, Link, useLocation, useNavigate } from 'react-router-dom';
import {
  LayoutDashboard, Shield, Cpu, ListTodo, GitBranch, LogOut, Menu, X, Users, Server,
} from 'lucide-react';
import { useAuth, useLogout } from '../hooks/useAuth';
import RoleBadge from '../components/RoleBadge';
import LoadingState from '../components/LoadingState';

const NAV_ITEMS = [
  { to: '/admin/overview', label: 'Overview', icon: LayoutDashboard },
  { to: '/admin/users', label: 'Users', icon: Users },
  { to: '/admin/agents', label: 'Agents', icon: Cpu },
  { to: '/admin/tasks', label: 'Tasks', icon: ListTodo },
  { to: '/admin/audit', label: 'Audit', icon: GitBranch },
  { to: '/admin/system', label: 'System', icon: Server },
];

export default function AdminLayout() {
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const { data, isLoading } = useAuth();
  const logout = useLogout();
  const location = useLocation();
  const navigate = useNavigate();

  if (isLoading) return <LoadingState />;

  return (
    <div className="flex h-screen bg-gray-50">
      <aside className={`${sidebarOpen ? 'w-56' : 'w-16'} bg-gray-900 flex flex-col transition-all duration-200`}>
        <div className="flex items-center justify-between h-14 px-4 border-b border-gray-700">
          {sidebarOpen && <span className="font-bold text-lg text-white">Admin</span>}
          <button onClick={() => setSidebarOpen(!sidebarOpen)} className="p-1 hover:bg-gray-800 rounded text-gray-400">
            {sidebarOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
          </button>
        </div>
        <nav className="flex-1 p-2 space-y-1">
          {NAV_ITEMS.map((item) => {
            const active = location.pathname === item.to;
            return (
              <Link
                key={item.to}
                to={item.to}
                className={`flex items-center gap-3 px-3 py-2 rounded text-sm font-medium ${
                  active ? 'bg-gray-700 text-white' : 'text-gray-400 hover:bg-gray-800 hover:text-white'
                }`}
              >
                <item.icon className="h-4 w-4 shrink-0" />
                {sidebarOpen && item.label}
              </Link>
            );
          })}
        </nav>
        <div className="p-2 border-t border-gray-700">
          <button
            onClick={() => navigate('/app/overview')}
            className="flex items-center gap-3 px-3 py-2 rounded text-sm font-medium text-gray-400 hover:bg-gray-800 w-full"
          >
            <Shield className="h-4 w-4" />
            {sidebarOpen && 'User Console'}
          </button>
          <button
            onClick={() => logout.mutate()}
            className="flex items-center gap-3 px-3 py-2 rounded text-sm font-medium text-gray-400 hover:bg-gray-800 w-full mt-1"
          >
            <LogOut className="h-4 w-4" />
            {sidebarOpen && 'Logout'}
          </button>
        </div>
      </aside>

      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Danger banner */}
        <div className="bg-red-600 text-white text-xs font-medium px-6 py-1 text-center">
          ⚠ Admin Console — actions affect all users
        </div>
        <header className="h-14 bg-white border-b border-gray-200 flex items-center justify-between px-6">
          <h1 className="text-sm font-medium text-gray-500">
            {NAV_ITEMS.find(n => location.pathname.startsWith(n.to))?.label || 'Admin'}
          </h1>
          <div className="flex items-center gap-3">
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

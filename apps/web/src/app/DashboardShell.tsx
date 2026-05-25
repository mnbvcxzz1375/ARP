import { useState, useEffect, useCallback } from 'react';
import { Outlet, NavLink, useNavigate, useLocation } from 'react-router-dom';
import { LogOut, PanelLeftClose, PanelLeftOpen, Menu, X } from 'lucide-react';
import { useAuth, useLogout } from '../hooks/useAuth';
import type { NavGroup } from './navigation';

type Scope = 'personal' | 'enterprise';

interface DashboardShellProps {
  navGroups: NavGroup[];
  scope: Scope;
}

export default function DashboardShell({ navGroups, scope }: DashboardShellProps) {
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const { data: user } = useAuth();
  const logoutMutation = useLogout();
  const navigate = useNavigate();
  const location = useLocation();

  const isAdmin = user?.role === 'admin' || user?.role === 'super_admin';
  const isEnterprise = scope === 'enterprise';

  // Close mobile drawer on route change
  useEffect(() => {
    setMobileOpen(false);
  }, [location.pathname]);

  const handleLogout = () => {
    logoutMutation.mutate(undefined, {
      onSuccess: () => navigate('/login'),
    });
  };

  const handleScopeSwitch = (newScope: Scope) => {
    if (newScope === scope) return;
    navigate(newScope === 'enterprise' ? '/enterprise/overview' : '/app/overview');
  };

  const closeMobile = useCallback(() => setMobileOpen(false), []);

  return (
    <div className="flex h-screen overflow-hidden">
      {/* Mobile hamburger */}
      <button
        onClick={() => setMobileOpen(true)}
        className={`md:hidden fixed top-3 left-3 z-40 p-2 rounded-md ${
          isEnterprise ? 'bg-gray-800 text-gray-300' : 'bg-white text-gray-700 shadow'
        }`}
        aria-label="Open menu"
      >
        <Menu size={20} />
      </button>

      {/* Mobile overlay backdrop */}
      {mobileOpen && (
        <div
          className="md:hidden fixed inset-0 z-30 bg-black/40"
          onClick={closeMobile}
        />
      )}

      {/* Sidebar */}
      <aside
        className={`flex flex-col border-r transition-all duration-200 ${
          isEnterprise
            ? 'bg-gray-900 border-gray-700 text-gray-300'
            : 'bg-white border-gray-200 text-gray-700'
        } ${
          mobileOpen
            ? 'fixed inset-y-0 left-0 z-30 w-64 md:relative md:z-0'
            : 'hidden md:flex'
        } ${collapsed ? 'md:w-16' : 'md:w-64'}`}
      >
        {/* Scope header */}
        <div className={`px-4 py-3 border-b ${isEnterprise ? 'border-gray-700' : 'border-gray-200'}`}>
          <div className="flex items-center justify-between">
            {(!collapsed || mobileOpen) && (
              <span className={`text-sm font-semibold ${isEnterprise ? 'text-white' : 'text-gray-900'}`}>
                {isEnterprise ? 'Enterprise Console' : 'Personal Console'}
              </span>
            )}
            <div className="flex items-center gap-1">
              <button
                onClick={() => setCollapsed(!collapsed)}
                className={`hidden md:block p-1 rounded ${isEnterprise ? 'hover:bg-gray-800 text-gray-400' : 'hover:bg-gray-100 text-gray-500'}`}
                aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
              >
                {collapsed ? <PanelLeftOpen size={18} /> : <PanelLeftClose size={18} />}
              </button>
              <button
                onClick={closeMobile}
                className="md:hidden p-1 rounded hover:bg-gray-200 text-gray-500"
                aria-label="Close menu"
              >
                <X size={18} />
              </button>
            </div>
          </div>

          {/* Scope switcher (admin/super_admin only) */}
          {isAdmin && !collapsed && (
            <div className="mt-2 flex rounded-md overflow-hidden border border-gray-300">
              <button
                onClick={() => handleScopeSwitch('personal')}
                className={`flex-1 py-1 text-xs font-medium ${
                  scope === 'personal'
                    ? 'bg-blue-600 text-white'
                    : isEnterprise
                      ? 'bg-gray-800 text-gray-400 hover:text-gray-200'
                      : 'bg-white text-gray-600 hover:text-gray-900'
                }`}
              >
                Personal
              </button>
              <button
                onClick={() => handleScopeSwitch('enterprise')}
                className={`flex-1 py-1 text-xs font-medium ${
                  scope === 'enterprise'
                    ? 'bg-blue-600 text-white'
                    : isEnterprise
                      ? 'bg-gray-800 text-gray-400 hover:text-gray-200'
                      : 'bg-white text-gray-600 hover:text-gray-900'
                }`}
              >
                Enterprise
              </button>
            </div>
          )}
        </div>

        {/* Navigation */}
        <nav className="flex-1 overflow-y-auto py-2">
          {navGroups.map((group) => (
            <div key={group.group} className="mb-3">
              {!collapsed && (
                <div
                  className={`px-4 py-1 text-[10px] font-semibold uppercase tracking-wider ${
                    isEnterprise ? 'text-gray-500' : 'text-gray-400'
                  }`}
                >
                  {group.group}
                </div>
              )}
              {group.items
                .filter((item) => !item.hidden)
                .map((item) => (
                  <NavLink
                    key={item.to}
                    to={item.to}
                    onClick={closeMobile}
                    className={({ isActive }) =>
                      `flex items-center gap-3 mx-2 px-2 py-1.5 rounded text-sm transition-colors ${
                        collapsed ? 'justify-center' : ''
                      } ${
                        isActive
                          ? isEnterprise
                            ? 'bg-gray-800 text-white'
                            : 'bg-gray-100 text-gray-900'
                          : isEnterprise
                            ? 'text-gray-400 hover:text-white hover:bg-gray-800'
                            : 'text-gray-600 hover:text-gray-900 hover:bg-gray-50'
                      }`
                    }
                  >
                    <item.icon size={18} />
                    {!collapsed && <span>{item.label}</span>}
                  </NavLink>
                ))}
            </div>
          ))}
        </nav>

        {/* User footer */}
        <div className={`px-4 py-3 border-t ${isEnterprise ? 'border-gray-700' : 'border-gray-200'}`}>
          {!collapsed && (
            <div className="flex items-center justify-between">
              <div className="min-w-0">
                <div className={`text-sm font-medium truncate ${isEnterprise ? 'text-white' : 'text-gray-900'}`}>
                  {user?.username || 'User'}
                </div>
                <div className={`text-xs ${isEnterprise ? 'text-gray-500' : 'text-gray-400'}`}>
                  {user?.role || 'unknown'}
                </div>
              </div>
              <button
                onClick={handleLogout}
                className={`p-1.5 rounded ${isEnterprise ? 'hover:bg-gray-800 text-gray-400' : 'hover:bg-gray-100 text-gray-500'}`}
                aria-label="Sign out"
              >
                <LogOut size={16} />
              </button>
            </div>
          )}
          {collapsed && (
            <button
              onClick={handleLogout}
              className={`mx-auto p-1.5 rounded ${isEnterprise ? 'hover:bg-gray-800 text-gray-400' : 'hover:bg-gray-100 text-gray-500'}`}
              aria-label="Sign out"
            >
              <LogOut size={16} />
            </button>
          )}
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-y-auto bg-gray-50">
        {isEnterprise && (
          <div className="bg-gray-800 text-gray-300 text-xs px-6 py-2 border-b border-gray-700">
            Enterprise Console -- actions affect all users and relay infrastructure
          </div>
        )}
        <div className="p-4 md:p-6 pt-14 md:pt-6">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
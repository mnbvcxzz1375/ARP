import { useState } from 'react';
import { NavLink, Outlet, useNavigate, Link } from 'react-router-dom';
import { BookOpen, LogOut, Menu, Moon, PanelLeftClose, PanelLeftOpen, Sun, X } from 'lucide-react';
import { useAuth, useLogout } from '../hooks/useAuth';
import { useTheme } from '../hooks/useTheme';
import { useT } from '../i18n';
import { hasEnterpriseConsoleAccess } from '../lib/permissions';
import LanguageSwitcher from '../components/LanguageSwitcher';
import { canSeeNavItem, type NavGroup, type NavItem } from './navigation';
import { rememberDocsOrigin } from '../features/docs/docsEntryMemory';

type Scope = 'personal' | 'enterprise';

interface DashboardShellProps {
  navGroups: NavGroup[];
  scope: Scope;
}

/**
 * Unified console shell (pixel design system).
 *
 * Layout: CSS Grid only - sidebar column + main column using
 * minmax(0,1fr) so wide tables can never force document-level horizontal
 * overflow (e2e asserts scrollWidth <= clientWidth + 2 at 375px).
 * Mobile (<768px): single column, navigation collapses to a fixed bottom
 * bar (icon + label, 44px touch targets, horizontal scroll when needed).
 *
 * Theme is locked once at the document root via useTheme; sections never
 * invert locally.
 */
export default function DashboardShell({ navGroups, scope }: DashboardShellProps) {
  const [collapsed, setCollapsed] = useState(false);
  // Mobile drawer (<768px): the console nav no longer fits a horizontal
  // bottom bar once the enterprise nav groups are in play (15+ items).
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const { data: user } = useAuth();
  const logoutMutation = useLogout();
  const navigate = useNavigate();
  const { theme, toggleTheme } = useTheme();
  const t = useT();

  const isAdmin = user?.role === 'admin' || user?.role === 'super_admin';
  const isEnterprise = scope === 'enterprise';

  // Data-driven permission gating (fail-closed), via the shared predicate
  // in navigation.ts (see its header for the org-domain equivalence):
  // - an item without `permission` is always visible;
  // - a gated item is only visible when the session's permission set
  //   (GET /v1/dashboard/auth/me -> permissions, mirroring the backend
  //   ROLE_PERMISSIONS in apps/api/app/services/rbac_service.py) contains
  //   the required string - or its ':org' variant for global-scope items;
  // - orgOnly items (org-domain strings like 'org:manage') are NOT covered
  //   by the super_admin short-circuit;
  // - an empty/missing permission set therefore hides every gated item.
  const permissions = user?.permissions ?? [];
  const isSuperAdmin = user?.role === 'super_admin';
  const canSee = (item: NavItem) => canSeeNavItem(item, permissions, isSuperAdmin);
  const isItemVisible = (item: NavItem) => !item.hidden && canSee(item);

  // Org-domain echo (GET /v1/dashboard/auth/me -> organizations). Absent or
  // empty for accounts without an org membership: the shell then keeps its
  // pre-org layout and copy. The first membership is the console's org
  // context (managers/admins typically hold one).
  const organizations = user?.organizations ?? [];
  const primaryOrg = organizations[0];
  const orgRoleLabel = (role: string) =>
    role === 'manager'
      ? t('enterprise.orgMembers.role.manager')
      : role === 'member'
        ? t('enterprise.orgMembers.role.member')
        : role;

  // Enterprise entry visibility: the scope switcher is shown to platform
  // admins/super_admin (unchanged) and additionally to accounts holding an
  // org-domain permission (org managers/members). Pure personal accounts
  // still see no enterprise entry at all.
  const canSwitchScope = isAdmin || hasEnterpriseConsoleAccess(permissions);

  const handleLogout = () => {
    logoutMutation.mutate(undefined, {
      onSuccess: () => navigate('/login'),
    });
  };

  const handleScopeSwitch = (newScope: Scope) => {
    if (newScope === scope) return;
    navigate(newScope === 'enterprise' ? '/enterprise/overview' : '/app/overview');
  };

  // Drop group headers whose every item is filtered out (fail-closed
  // should not leave orphaned section headers behind).
  const visibleGroups = navGroups.filter((g) => g.items.some(isItemVisible));

  const navLinkClass = ({ isActive }: { isActive: boolean }) =>
    `group relative flex items-center gap-3 mx-2 px-2 min-h-[44px] border-l-4 ${
      collapsed ? 'justify-center border-l-transparent px-0' : ''
    } ${
      // Active = solid accent block with dark text: #df7126 on #df7126 bg
      // measures 5.34:1 in BOTH themes (accent is theme-invariant), which
      // clears AA for the 11px PS2P label. Accent-as-text failed AA
      // (4.23:1 dark / 2.48:1 light).
      isActive
        ? 'border-l-[#191a26] bg-pixel-accent text-[#191a26]'
        : 'border-l-transparent text-pixel-muted hover:bg-pixel-raised hover:text-pixel-fg'
    }`;

  const mobileNavLinkClass = ({ isActive }: { isActive: boolean }) =>
    `flex flex-col items-start justify-center gap-1 min-h-[44px] px-4 py-2 border-l-4 ${
      isActive
        ? 'border-l-[#191a26] bg-pixel-accent text-[#191a26]'
        : 'border-l-transparent text-pixel-muted hover:bg-pixel-raised hover:text-pixel-fg'
    }`;

  return (
    <div
      className={
        collapsed
          ? 'grid grid-cols-1 grid-rows-[auto_minmax(0,1fr)] overflow-hidden bg-pixel-bg [height:var(--app-vh,100dvh)] md:grid-cols-[4rem_minmax(0,1fr)] md:grid-rows-[minmax(0,1fr)]'
          : 'grid grid-cols-1 grid-rows-[auto_minmax(0,1fr)] overflow-hidden bg-pixel-bg [height:var(--app-vh,100dvh)] md:grid-cols-[16rem_minmax(0,1fr)] md:grid-rows-[minmax(0,1fr)]'
      }
    >
      {/* CRT overlay layers: fixed, pointer-events:none; auto-disabled on
          mobile (<768px) and under prefers-reduced-motion (index.css). */}
      <div className="pixel-scanlines" aria-hidden="true" />
      <div className="pixel-rgb-stripes" aria-hidden="true" />

      {/* Sidebar (desktop only) */}
      <aside className="hidden md:flex md:[height:var(--app-vh,100dvh)] flex-col overflow-hidden border-r-2 border-pixel-line bg-pixel-surface">
        {/* Scope header - the single chromatic element per screen. */}
        <div className="px-4 py-4 border-b-2 border-pixel-line">
          <div className="flex items-center justify-between gap-2">
            {!collapsed && (
              <span className="font-display text-pixel-lg chromatic text-pixel-fg">
                {isEnterprise ? t('shell.console.enterprise') : t('shell.console.personal')}
              </span>
            )}
            <button
              onClick={() => setCollapsed(!collapsed)}
              className="inline-flex items-center justify-center min-h-[44px] min-w-[44px] text-pixel-muted hover:text-pixel-fg hover:bg-pixel-raised"
              aria-label={collapsed ? t('shell.sidebar.expand') : t('shell.sidebar.collapse')}
            >
              {collapsed ? (
                <PanelLeftOpen size={18} strokeWidth={2} />
              ) : (
                <PanelLeftClose size={18} strokeWidth={2} />
              )}
            </button>
          </div>

          {/* Scope switcher: platform admins/super_admin (unchanged) plus
              org-domain accounts (managers/members). Pure personal accounts
              still get no enterprise entry. */}
          {canSwitchScope && !collapsed && (
            <div className="flex mt-3 border-2 border-pixel-line">
              <button
                onClick={() => handleScopeSwitch('personal')}
                className={`flex-1 min-h-[44px] py-1 font-pixel text-pixel-sm ${
                  scope === 'personal'
                    ? 'bg-pixel-accent text-[#191a26]'
                    : 'text-pixel-muted hover:bg-pixel-raised'
                }`}
              >
                {t('shell.scope.personal')}
              </button>
              <button
                onClick={() => handleScopeSwitch('enterprise')}
                className={`flex-1 min-h-[44px] py-1 font-pixel text-pixel-sm ${
                  scope === 'enterprise'
                    ? 'bg-pixel-accent text-[#191a26]'
                    : 'text-pixel-muted hover:bg-pixel-raised'
                }`}
              >
                {t('shell.scope.enterprise')}
              </button>
            </div>
          )}
        </div>

        {/* Navigation */}
        <nav className="flex-1 min-h-0 overflow-y-auto py-2">
          {visibleGroups.map((group) => (
            <div key={group.group} className="mb-3">
              {!collapsed && (
                <div className="px-4 py-1 font-display text-[10px] uppercase tracking-pixel text-pixel-muted">
                  {t(group.group)}
                </div>
              )}
              {group.items.filter(isItemVisible).map((item) => (
                  <NavLink
                    key={item.to}
                    to={item.to}
                    className={navLinkClass}
                    title={collapsed ? t(item.label) : undefined}
                  >
                    <item.icon size={18} strokeWidth={2} />
                    {!collapsed && (
                      <span className="font-display text-[11px] leading-tight">
                        {t(item.label)}
                      </span>
                    )}
                  </NavLink>
                ))}
            </div>
          ))}
        </nav>

        {/* User footer */}
        <div className="shrink-0 border-t-2 border-pixel-line px-4 py-3">
          {!collapsed ? (
            <div className="flex flex-col gap-1">
              {/* Identity row: full width, truncated - never squeezed by
                  the controls row below (the previous single-row layout
                  let 5 x 44px buttons crowd the username into the
                  switcher at 16rem sidebar width). */}
              <div className="min-w-0">
                {/* title shows the full user_id: usernames are non-unique
                    display labels, the UUID is the canonical identity. */}
                <div
                  className="truncate text-lg text-pixel-fg"
                  title={user ? `${t('shell.user.userIdTitle')} ${user.user_id}` : undefined}
                >
                  {user?.username || t('shell.user.defaultName')}
                </div>
                <div className="font-pixel text-pixel-sm text-pixel-muted">
                  {user?.role || t('shell.user.unknownRole')}
                </div>
                {/* Org-domain echo: the session's org context. Omitted
                    entirely (no extra DOM row) when /me carries no org
                    membership, so those layouts stay byte-identical. */}
                {primaryOrg && (
                  <div className="truncate font-pixel text-pixel-sm text-pixel-muted">
                    {primaryOrg.name} -- {orgRoleLabel(primaryOrg.role)}
                  </div>
                )}
              </div>
              {/* Controls row: 44px touch targets wrap instead of
                  overlapping the identity. */}
              <div className="flex flex-wrap items-center gap-1">
                <LanguageSwitcher />
                <Link
                  to="/docs/quickstart"
                  onClick={() => rememberDocsOrigin()}
                  className="inline-flex items-center justify-center min-h-[44px] min-w-[44px] text-pixel-muted hover:text-pixel-fg hover:bg-pixel-raised"
                  aria-label={t('shell.docs.entry')}
                  title={t('shell.docs.label')}
                >
                  <BookOpen size={16} strokeWidth={2} aria-hidden="true" />
                </Link>
                <button
                  onClick={toggleTheme}
                  className="inline-flex items-center justify-center min-h-[44px] min-w-[44px] text-pixel-muted hover:text-pixel-fg hover:bg-pixel-raised"
                  aria-label={theme === 'dark' ? t('shell.theme.switchToLight') : t('shell.theme.switchToDark')}
                >
                  {theme === 'dark' ? (
                    <Sun size={16} strokeWidth={2} />
                  ) : (
                    <Moon size={16} strokeWidth={2} />
                  )}
                </button>
                <button
                  onClick={handleLogout}
                  className="inline-flex items-center justify-center min-h-[44px] min-w-[44px] text-pixel-muted hover:text-pixel-fg hover:bg-pixel-raised"
                  aria-label={t('shell.logout')}
                >
                  <LogOut size={16} strokeWidth={2} />
                </button>
              </div>
            </div>
          ) : (
            <div className="flex flex-col items-center gap-1">
              <LanguageSwitcher compact />
              <Link
                to="/docs/quickstart"
                onClick={() => rememberDocsOrigin()}
                className="inline-flex items-center justify-center min-h-[44px] min-w-[44px] text-pixel-muted hover:text-pixel-fg hover:bg-pixel-raised"
                aria-label={t('shell.docs.entry')}
                title={t('shell.docs.label')}
              >
                <BookOpen size={16} strokeWidth={2} aria-hidden="true" />
              </Link>
              <button
                onClick={toggleTheme}
                className="inline-flex items-center justify-center min-h-[44px] min-w-[44px] text-pixel-muted hover:text-pixel-fg hover:bg-pixel-raised"
                aria-label={theme === 'dark' ? t('shell.theme.switchToLight') : t('shell.theme.switchToDark')}
              >
                {theme === 'dark' ? (
                  <Sun size={16} strokeWidth={2} />
                ) : (
                  <Moon size={16} strokeWidth={2} />
                )}
              </button>
              <button
                onClick={handleLogout}
                className="inline-flex items-center justify-center min-h-[44px] min-w-[44px] text-pixel-muted hover:text-pixel-fg hover:bg-pixel-raised"
                aria-label={t('shell.logout')}
              >
                <LogOut size={16} strokeWidth={2} />
              </button>
            </div>
          )}
        </div>
      </aside>

      {/* Mobile top bar (only <768px): opens the nav drawer. The console
          nav is too long for a horizontal bottom tab bar once the
          enterprise groups are in play (15+ items). */}
      <div className="sticky top-0 z-30 flex items-center gap-3 border-b-2 border-pixel-line bg-pixel-surface px-4 py-2 md:hidden">
        <button
          type="button"
          onClick={() => setMobileNavOpen(true)}
          aria-label={t('shell.sidebar.open')}
          aria-expanded={mobileNavOpen}
          className="flex min-h-[44px] items-center gap-2 border-2 border-pixel-line bg-pixel-raised px-3 py-1 font-pixel text-pixel-base text-pixel-fg hover:bg-pixel-accent"
        >
          <Menu size={16} strokeWidth={2} aria-hidden="true" />
          {t('shell.sidebar.menu')}
        </button>
        <span className="font-display text-pixel-base chromatic text-pixel-fg">
          {isEnterprise ? t('shell.console.enterprise') : t('shell.console.personal')}
        </span>
      </div>

      {/* Drawer backdrop */}
      {mobileNavOpen && (
        <button
          type="button"
          aria-label={t('shell.sidebar.close')}
          onClick={() => setMobileNavOpen(false)}
          className="fixed inset-0 z-40 bg-black/50 md:hidden"
        />
      )}

      {/* Nav drawer (mobile only) */}
      {mobileNavOpen && (
        <aside
          aria-label={t('shell.bottomNav.aria')}
          className="fixed inset-y-0 left-0 z-50 flex w-72 max-w-[85vw] flex-col overflow-hidden border-r-2 border-pixel-line bg-pixel-surface md:hidden"
        >
          <div className="flex items-center justify-between border-b-2 border-pixel-line px-4 py-3">
            <span className="font-display text-pixel-base chromatic text-pixel-fg">
              {isEnterprise ? t('shell.console.enterprise') : t('shell.console.personal')}
            </span>
            <button
              type="button"
              onClick={() => setMobileNavOpen(false)}
              className="border-2 border-pixel-line bg-pixel-raised p-1 text-pixel-fg hover:bg-pixel-accent"
              aria-label={t('shell.sidebar.close')}
            >
              <X size={16} strokeWidth={2} aria-hidden="true" />
            </button>
          </div>
          {canSwitchScope && (
            <div className="flex border-b-2 border-pixel-line">
              <button
                onClick={() => handleScopeSwitch('personal')}
                className={`flex-1 min-h-[44px] py-1 font-pixel text-pixel-sm ${
                  scope === 'personal'
                    ? 'bg-pixel-accent text-[#191a26]'
                    : 'text-pixel-muted hover:bg-pixel-raised'
                }`}
              >
                {t('shell.scope.personal')}
              </button>
              <button
                onClick={() => handleScopeSwitch('enterprise')}
                className={`flex-1 min-h-[44px] py-1 font-pixel text-pixel-sm ${
                  scope === 'enterprise'
                    ? 'bg-pixel-accent text-[#191a26]'
                    : 'text-pixel-muted hover:bg-pixel-raised'
                }`}
              >
                {t('shell.scope.enterprise')}
              </button>
            </div>
          )}
          <nav className="min-h-0 flex-1 overflow-y-auto py-2">
            {visibleGroups.map((group) => (
              <div key={group.group} className="mb-3">
                <div className="px-4 py-1 font-display text-[10px] uppercase tracking-pixel text-pixel-muted">
                  {t(group.group)}
                </div>
                {group.items.filter(isItemVisible).map((item) => (
                  <NavLink
                    key={item.to}
                    to={item.to}
                    onClick={() => setMobileNavOpen(false)}
                    className={mobileNavLinkClass}
                    title={t(item.label)}
                  >
                    <span className="flex items-center gap-3">
                      <item.icon size={18} strokeWidth={2} />
                      <span className="font-display text-[11px] leading-tight">
                        {t(item.label)}
                      </span>
                    </span>
                  </NavLink>
                ))}
              </div>
            ))}
          </nav>
          <div className="shrink-0 border-t-2 border-pixel-line p-3">
            <div className="flex flex-wrap items-center gap-1">
              <LanguageSwitcher />
              <Link
                to="/docs/quickstart"
                onClick={() => {
                  rememberDocsOrigin();
                  setMobileNavOpen(false);
                }}
                className="inline-flex items-center justify-center min-h-[44px] min-w-[44px] text-pixel-muted hover:text-pixel-fg hover:bg-pixel-raised"
                aria-label={t('shell.docs.entry')}
                title={t('shell.docs.label')}
              >
                <BookOpen size={16} strokeWidth={2} aria-hidden="true" />
              </Link>
              <button
                onClick={toggleTheme}
                className="inline-flex items-center justify-center min-h-[44px] min-w-[44px] text-pixel-muted hover:text-pixel-fg hover:bg-pixel-raised"
                aria-label={theme === 'dark' ? t('shell.theme.switchToLight') : t('shell.theme.switchToDark')}
              >
                {theme === 'dark' ? (
                  <Sun size={16} strokeWidth={2} />
                ) : (
                  <Moon size={16} strokeWidth={2} />
                )}
              </button>
              <button
                onClick={handleLogout}
                className="inline-flex items-center justify-center min-h-[44px] min-w-[44px] text-pixel-muted hover:text-pixel-fg hover:bg-pixel-raised"
                aria-label={t('shell.logout')}
              >
                <LogOut size={16} strokeWidth={2} />
              </button>
            </div>
          </div>
        </aside>
      )}

      {/* Main content */}
      <main className="min-w-0 overflow-y-auto bg-pixel-bg pt-[52px] md:pt-0">
        {isEnterprise && (
          <div
            data-testid="enterprise-banner"
            className="flex items-center gap-2 px-4 md:px-6 py-2 border-b-2 border-pixel-line bg-pixel-raised text-pixel-muted"
          >
            <span className="pixel-led pixel-led-amber" aria-hidden="true" />
            <span className="font-pixel text-pixel-sm">
              {t('shell.banner.enterprise')}
            </span>
            {/* Org context for org-domain sessions; super_admin/platform
                admins without a membership keep the plain banner. */}
            {primaryOrg && (
              <span className="font-pixel text-pixel-sm">
                -- {primaryOrg.name} ({orgRoleLabel(primaryOrg.role)})
              </span>
            )}
          </div>
        )}
        <div className="p-4 md:p-6">
          <Outlet />
        </div>
      </main>
    </div>
  );
}

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { RouterForTesting } from '../../test-utils';
import DashboardShell from '../DashboardShell';
import { ENTERPRISE_NAV, PERSONAL_NAV } from '../navigation';

// Mocked auth: DashboardShell reads the session user (role + permissions)
// from useAuth(). The permission strings below are the REAL backend
// constants from apps/api/app/services/rbac_service.py ROLE_PERMISSIONS,
// so these tests exercise the same data /me returns.
vi.mock('../../hooks/useAuth', () => ({
  useAuth: vi.fn(),
  useLogout: vi.fn(() => ({ mutate: vi.fn() })),
}));

import { useAuth } from '../../hooks/useAuth';
import type { AuthUser } from '../../hooks/useAuth';

/** Mirror of _ADMIN_PERMS (apps/api/app/services/rbac_service.py:85). */
const ADMIN_PERMISSIONS = [
  'agent:read:own',
  'agent:create',
  'agent:edit:own',
  'agent:delete:own',
  'agent:rotate-token:own',
  'task:read:own',
  'task:create',
  'task:read:detail:own',
  'approval:handle:own',
  'connection:manage:own',
  'firewall:manage:own',
  'apikey:manage:own',
  'overview:read:global',
  'user:read:global',
  'agent:read:global',
  'task:read:global',
  'task:read:detail:global',
  'audit:read',
  'task:cancel:pending',
  'admin:read',
  'policy:read',
  'sla:read',
  'continuity:read',
];

/** Mirror of _USER_PERMS (apps/api/app/services/rbac_service.py:76). */
const USER_PERMISSIONS = ADMIN_PERMISSIONS.filter((p) => p.endsWith(':own'));

function renderShell(
  navGroups: typeof ENTERPRISE_NAV,
  scope: 'personal' | 'enterprise',
  auth: Partial<AuthUser> | null,
) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });

  vi.mocked(useAuth).mockReturnValue({
    data: auth
      ? ({
          user_id: 'u1',
          username: 'tester',
          csrf_required: true,
          session_expires_at: '2026-12-31T00:00:00Z',
          step_up_until: null,
          ...auth,
        } as AuthUser)
      : null,
    isLoading: false,
    isError: !auth,
    error: null,
  } as any);

  return render(
    <QueryClientProvider client={queryClient}>
      <RouterForTesting initialEntries={['/enterprise/overview']}>
        <DashboardShell navGroups={navGroups} scope={scope} />
      </RouterForTesting>
    </QueryClientProvider>,
  );
}

describe('DashboardShell permission gating', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('shows every gated enterprise item for an admin holding the backend admin permission set', () => {
    renderShell(ENTERPRISE_NAV, 'enterprise', {
      username: 'admin1',
      role: 'admin',
      permissions: ADMIN_PERMISSIONS,
    });

    // One representative item per mapped permission string.
    expect(screen.getAllByText('Overview').length).toBeGreaterThan(0); // overview:read:global
    expect(screen.getAllByText('Network Scopes').length).toBeGreaterThan(0); // admin:read
    expect(screen.getAllByText('Route Policies').length).toBeGreaterThan(0); // policy:read
    expect(screen.getAllByText('Egress Gateway').length).toBeGreaterThan(0); // admin:read
    expect(screen.getAllByText('Users').length).toBeGreaterThan(0); // user:read:global
    expect(screen.getAllByText('SLA & Continuity').length).toBeGreaterThan(0); // sla:read
    expect(screen.getAllByText('Audit Logs').length).toBeGreaterThan(0); // audit:read
    // system:read is super_admin-only on the backend (_SUPER_ADMIN_PERMS),
    // so a plain admin legitimately does NOT see System Health.
    expect(screen.queryByText('System Health')).not.toBeInTheDocument();
    // Ungated item (no backend permission to map) stays visible.
    expect(screen.getAllByText('Route Decisions').length).toBeGreaterThan(0);
  });

  it('hides gated enterprise items for a session whose permissions do not include them', () => {
    renderShell(ENTERPRISE_NAV, 'enterprise', {
      username: 'limited',
      role: 'admin',
      // Own-level permissions only: none of the enterprise read perms.
      permissions: USER_PERMISSIONS,
    });

    expect(screen.queryByText('Audit Logs')).not.toBeInTheDocument(); // audit:read
    expect(screen.queryByText('Users')).not.toBeInTheDocument(); // user:read:global
    expect(screen.queryByText('System Health')).not.toBeInTheDocument(); // system:read
    expect(screen.queryByText('Route Policies')).not.toBeInTheDocument(); // policy:read
    expect(screen.queryByText('Network Scopes')).not.toBeInTheDocument(); // admin:read
    // Ungated item is NOT a permission decision, so it remains visible.
    expect(screen.getAllByText('Route Decisions').length).toBeGreaterThan(0);
  });

  it('fails closed: a session with no permissions at all hides every gated item and orphaned group headers', () => {
    renderShell(ENTERPRISE_NAV, 'enterprise', {
      username: 'empty',
      role: 'admin',
      permissions: [],
    });

    expect(screen.queryByText('Audit Logs')).not.toBeInTheDocument();
    expect(screen.queryByText('Users')).not.toBeInTheDocument();
    expect(screen.queryByText('Overview')).not.toBeInTheDocument();
    // Orphaned group headers are dropped with their items.
    expect(screen.queryByText('Command Center')).not.toBeInTheDocument();
    expect(screen.queryByText('Governance')).not.toBeInTheDocument();
    // Ungated items survive fail-closed.
    expect(screen.getAllByText('Route Decisions').length).toBeGreaterThan(0);
    expect(screen.getAllByText('Traffic').length).toBeGreaterThan(0);
  });

  it('super_admin sees all items even when the transported permission set is empty (role short-circuit)', () => {
    renderShell(ENTERPRISE_NAV, 'enterprise', {
      username: 'root',
      role: 'super_admin',
      // Backend gives super_admin the full union; the short-circuit keeps
      // a transport hiccup (empty array) from locking the super admin out.
      permissions: [],
    });

    expect(screen.getAllByText('Audit Logs').length).toBeGreaterThan(0);
    expect(screen.getAllByText('Users').length).toBeGreaterThan(0);
    expect(screen.getAllByText('System Health').length).toBeGreaterThan(0);
    expect(screen.getAllByText('Route Policies').length).toBeGreaterThan(0);
  });

  it('shows own-level personal items for a plain user session', () => {
    renderShell(PERSONAL_NAV, 'personal', {
      username: 'user1',
      role: 'user',
      permissions: USER_PERMISSIONS,
    });

    expect(screen.getAllByText('Agents').length).toBeGreaterThan(0); // agent:read:own
    expect(screen.getAllByText('Tasks').length).toBeGreaterThan(0); // task:read:own
    expect(screen.getAllByText('Approvals').length).toBeGreaterThan(0); // approval:handle:own
    expect(screen.getAllByText('Connections').length).toBeGreaterThan(0); // connection:manage:own
    expect(screen.getAllByText('API Keys').length).toBeGreaterThan(0); // apikey:manage:own
  });

  it('does not render the removed Approval Queues destination', () => {
    renderShell(ENTERPRISE_NAV, 'enterprise', {
      username: 'admin1',
      role: 'admin',
      permissions: ADMIN_PERMISSIONS,
    });

    expect(screen.queryByText('Approval Queues')).not.toBeInTheDocument();
  });
});

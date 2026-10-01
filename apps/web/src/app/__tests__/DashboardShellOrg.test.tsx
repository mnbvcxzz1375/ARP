import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { RouterForTesting } from '../../test-utils';
import DashboardShell from '../DashboardShell';
import { ENTERPRISE_NAV } from '../navigation';

// Mocked auth: DashboardShell reads the session user (role + permissions +
// organizations) from useAuth(). The permission strings below are the REAL
// backend constants from apps/api/app/services/rbac_service.py:
// ORG_ROLE_PERMISSIONS['manager'] / ['member'], and the platform admin
// mirror _ADMIN_PERMS.
vi.mock('../../hooks/useAuth', () => ({
  useAuth: vi.fn(),
  useLogout: vi.fn(() => ({ mutate: vi.fn() })),
}));

import { useAuth } from '../../hooks/useAuth';
import type { AuthUser, OrgMembership } from '../../hooks/useAuth';

/** Backend ORG_ROLE_PERMISSIONS['manager'] (rbac_service.py). */
const ORG_MANAGER_PERMISSIONS = [
  'overview:read:org',
  'agent:read:org',
  'task:read:org',
  'approval:handle:org',
  'connection:read:org',
  'policy:read:org',
  'sla:read:org',
  'audit:read:org',
  'org:manage',
];

/** Backend ORG_ROLE_PERMISSIONS['member'] (rbac_service.py). */
const ORG_MEMBER_PERMISSIONS = ['overview:read:org'];

const ACME: OrgMembership = { org_id: 'org-1', name: 'Acme Corp', role: 'manager' };

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

describe('DashboardShell org-domain filtering (manager / member / super_admin)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('org manager sees Overview, the org Members entry, and the org-permission items', () => {
    renderShell(ENTERPRISE_NAV, 'enterprise', {
      username: 'org_manager',
      role: 'user',
      permissions: ORG_MANAGER_PERMISSIONS,
      organizations: [ACME],
    });

    // Command Center overview via the overview:read:org variant.
    expect(screen.getAllByText('Overview').length).toBeGreaterThan(0);
    // The org-domain members destination (org:manage).
    expect(screen.getAllByText('Organization Members').length).toBeGreaterThan(0);
    expect(screen.getByText('Organization')).toBeInTheDocument(); // group header
    // Items whose org variants the manager holds: policy/audit/sla.
    expect(screen.getAllByText('Route Policies').length).toBeGreaterThan(0);
    expect(screen.getAllByText('Audit Logs').length).toBeGreaterThan(0);
    expect(screen.getAllByText('SLA & Continuity').length).toBeGreaterThan(0);
    // The ungated Route Decisions entry stays visible.
    expect(screen.getAllByText('Route Decisions').length).toBeGreaterThan(0);
  });

  it('org manager does NOT see items behind permissions they lack', () => {
    renderShell(ENTERPRISE_NAV, 'enterprise', {
      username: 'org_manager',
      role: 'user',
      permissions: ORG_MANAGER_PERMISSIONS,
      organizations: [ACME],
    });

    // user:read:global (and its variant) is not held -> hidden.
    expect(screen.queryByText('Users')).not.toBeInTheDocument();
    expect(screen.queryByText('Access Requests')).not.toBeInTheDocument();
    // admin:read not held in either domain -> hidden.
    expect(screen.queryByText('Network Scopes')).not.toBeInTheDocument();
    expect(screen.queryByText('Network Zones')).not.toBeInTheDocument();
    expect(screen.queryByText('Relay Nodes')).not.toBeInTheDocument();
    expect(screen.queryByText('Egress Gateway')).not.toBeInTheDocument();
    expect(screen.queryByText('Dedicated Channels')).not.toBeInTheDocument();
    expect(screen.queryByText('System Health')).not.toBeInTheDocument();
    // No orphaned group header for the fully-hidden Governance group.
    // Topology keeps its header because the manager's policy:read:org
    // variant keeps Route Policies visible (org-domain equivalence).
    expect(screen.queryByText('Governance')).not.toBeInTheDocument();
    expect(screen.getAllByText('Topology').length).toBeGreaterThan(0);
  });

  it('org member sees the read-only Overview entry and no gated items', () => {
    renderShell(ENTERPRISE_NAV, 'enterprise', {
      username: 'org_member',
      role: 'user',
      permissions: ORG_MEMBER_PERMISSIONS,
      organizations: [{ ...ACME, role: 'member' }],
    });

    expect(screen.getAllByText('Overview').length).toBeGreaterThan(0);
    expect(screen.queryByText('Organization Members')).not.toBeInTheDocument();
    expect(screen.queryByText('Route Policies')).not.toBeInTheDocument();
    expect(screen.queryByText('Audit Logs')).not.toBeInTheDocument();
    expect(screen.queryByText('SLA & Continuity')).not.toBeInTheDocument();
    expect(screen.queryByText('Users')).not.toBeInTheDocument();
    expect(screen.queryByText('System Health')).not.toBeInTheDocument();
    // Route Decisions is ungated by design (no backend permission to map,
    // see navigation.ts header) and survives fail-closed for every
    // session; it is the single pre-existing ungated entry.
    expect(screen.getAllByText('Route Decisions').length).toBeGreaterThan(0);
  });

  it('super_admin sees every global item but NOT the orgOnly members entry without a membership', () => {
    renderShell(ENTERPRISE_NAV, 'enterprise', {
      username: 'e2e_admin',
      role: 'super_admin',
      // Backend gives super_admin the full union; the empty array case is
      // the transport-hiccup short-circuit the role covers.
      permissions: [],
    });

    expect(screen.getAllByText('Overview').length).toBeGreaterThan(0);
    expect(screen.getAllByText('Audit Logs').length).toBeGreaterThan(0);
    expect(screen.getAllByText('Users').length).toBeGreaterThan(0);
    expect(screen.getAllByText('System Health').length).toBeGreaterThan(0);
    expect(screen.getAllByText('Route Policies').length).toBeGreaterThan(0);
    // orgOnly items are out of the super_admin short-circuit: a
    // membership-less super admin has no org console in their sidebar, so
    // the pre-org layout (and the visual baselines) stay intact.
    expect(screen.queryByText('Organization Members')).not.toBeInTheDocument();
  });

  it('super_admin enrolled as an org manager sees the org members entry', () => {
    renderShell(ENTERPRISE_NAV, 'enterprise', {
      username: 'e2e_admin',
      role: 'super_admin',
      permissions: [...ORG_MANAGER_PERMISSIONS, 'system:read', 'super_admin:write'],
      organizations: [ACME],
    });

    expect(screen.getAllByText('Organization Members').length).toBeGreaterThan(0);
    expect(screen.getAllByText('System Health').length).toBeGreaterThan(0);
  });
});

describe('DashboardShell org echo and enterprise entry', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('echoes the primary organization and membership role in the sidebar footer', () => {
    renderShell(ENTERPRISE_NAV, 'enterprise', {
      username: 'org_manager',
      role: 'user',
      permissions: ORG_MANAGER_PERMISSIONS,
      organizations: [ACME],
    });

    expect(screen.getByText('Acme Corp -- Manager')).toBeInTheDocument();
  });

  it('shows the org context in the enterprise banner', () => {
    renderShell(ENTERPRISE_NAV, 'enterprise', {
      username: 'org_member',
      role: 'user',
      permissions: ORG_MEMBER_PERMISSIONS,
      organizations: [{ ...ACME, role: 'member' }],
    });

    const banner = document.querySelector('[data-testid="enterprise-banner"]');
    expect(banner?.textContent).toContain('Acme Corp');
    expect(banner?.textContent).toContain('Member');
  });

  it('keeps the pre-org layout when the session has no organization', () => {
    const { container } = renderShell(ENTERPRISE_NAV, 'enterprise', {
      username: 'e2e_admin',
      role: 'super_admin',
      permissions: ['overview:read:global', 'system:read', 'super_admin:write'],
    });

    const banner = container.querySelector('[data-testid="enterprise-banner"]');
    expect(banner?.textContent).not.toContain('Acme Corp');
    // No org echo row appears next to the role line.
    expect(screen.queryByText(/Acme Corp/)).not.toBeInTheDocument();
  });

  it('shows the enterprise scope switcher for an org manager in the personal console', () => {
    renderShell([], 'personal', {
      username: 'org_manager',
      role: 'user',
      permissions: ORG_MANAGER_PERMISSIONS,
      organizations: [ACME],
    });

    // Desktop sidebar scope switcher.
    expect(screen.getAllByText('Enterprise').length).toBeGreaterThan(0);
  });

  it('hides the enterprise entry for a pure personal account', () => {
    renderShell([], 'personal', {
      username: 'plain_user',
      role: 'user',
      permissions: ['agent:read:own', 'task:read:own'],
    });

    // Only the shell chromatic 'Enterprise' label would render if the
    // switcher were shown; a pure personal account shows none.
    expect(screen.queryByText('Enterprise')).not.toBeInTheDocument();
  });
});

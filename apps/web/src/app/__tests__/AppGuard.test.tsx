import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { Route, Routes } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { RouterForTesting } from '../../test-utils';
import { RequireAdmin } from '../../App';

// Mocked auth: RequireAdmin reads the session (role + permissions) from
// useAuth(). The permission strings below mirror the backend RBAC map
// (apps/api/app/services/rbac_service.py): the org manager list is
// ORG_ROLE_PERMISSIONS['manager'], the member list is
// ORG_ROLE_PERMISSIONS['member'] = ['overview:read:org'] - exactly what
// /me.permissions echoes per the backend contract.
vi.mock('../../hooks/useAuth', () => ({
  useAuth: vi.fn(),
  useLogout: vi.fn(() => ({ mutate: vi.fn() })),
}));

import { useAuth } from '../../hooks/useAuth';
import type { AuthUser } from '../../hooks/useAuth';

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

/**
 * Renders RequireAdmin inside a real route tree so the Navigate outcomes
 * (/login?next=..., /no-access) are observable as route markers instead
 * of silent in-memory jumps.
 */
function renderGuard(auth: Partial<AuthUser> | null) {
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
        <Routes>
          <Route
            path="/enterprise/*"
            element={
              <RequireAdmin>
                <div data-testid="console">enterprise console</div>
              </RequireAdmin>
            }
          />
          <Route path="/login" element={<div data-testid="login-page">login</div>} />
          <Route path="/no-access" element={<div data-testid="no-access">no access</div>} />
        </Routes>
      </RouterForTesting>
    </QueryClientProvider>,
  );
}

describe('RequireAdmin guard (org-domain acceptance, additive)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('admits a super_admin session holding the global union (unchanged)', () => {
    renderGuard({
      username: 'e2e_admin',
      role: 'super_admin',
      permissions: [
        'overview:read:global',
        'user:read:global',
        'agent:read:global',
        'audit:read',
        'policy:read',
        'sla:read',
        'system:read',
        'super_admin:write',
      ],
    });
    expect(screen.getByTestId('console')).toBeInTheDocument();
    expect(screen.queryByTestId('login-page')).not.toBeInTheDocument();
    expect(screen.queryByTestId('no-access')).not.toBeInTheDocument();
  });

  it('admits a platform admin holding a single global permission (unchanged)', () => {
    renderGuard({
      username: 'admin1',
      role: 'admin',
      permissions: ['overview:read:global', 'agent:read:own', 'task:read:own'],
    });
    expect(screen.getByTestId('console')).toBeInTheDocument();
  });

  it('admits an org manager holding ONLY org-domain strings', () => {
    renderGuard({
      username: 'org_manager',
      role: 'user',
      permissions: ORG_MANAGER_PERMISSIONS,
      organizations: [{ org_id: 'org-1', name: 'Acme Corp', role: 'manager' }],
    });
    expect(screen.getByTestId('console')).toBeInTheDocument();
  });

  it('admits an org member holding only overview:read:org (read-only console)', () => {
    renderGuard({
      username: 'org_member',
      role: 'user',
      permissions: ORG_MEMBER_PERMISSIONS,
      organizations: [{ org_id: 'org-1', name: 'Acme Corp', role: 'member' }],
    });
    expect(screen.getByTestId('console')).toBeInTheDocument();
  });

  it('redirects a personal account with only own-level permissions to /no-access', () => {
    renderGuard({
      username: 'plain_user',
      role: 'user',
      permissions: ['agent:read:own', 'task:read:own', 'apikey:manage:own'],
    });
    expect(screen.queryByTestId('console')).not.toBeInTheDocument();
    expect(screen.getByTestId('no-access')).toBeInTheDocument();
  });

  it('fails closed: an authenticated session without any permission goes to /no-access', () => {
    renderGuard({ username: 'empty', role: 'user', permissions: [] });
    expect(screen.queryByTestId('console')).not.toBeInTheDocument();
    expect(screen.getByTestId('no-access')).toBeInTheDocument();
  });

  it('sends an unauthenticated session to /login (deep-link login contract)', () => {
    renderGuard(null);
    expect(screen.queryByTestId('console')).not.toBeInTheDocument();
    expect(screen.getByTestId('login-page')).toBeInTheDocument();
  });
});

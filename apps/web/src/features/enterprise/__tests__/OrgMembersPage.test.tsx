import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent, within } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import OrgMembersPage from '../OrgMembersPage';

/** Backend ORG_ROLE_PERMISSIONS (rbac_service.py), the /me contract. */
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
const ORG_MEMBER_PERMISSIONS = ['overview:read:org'];

const ORG_MINE = {
  organizations: [
    {
      org_id: 'org-1',
      name: 'Acme Corp',
      slug: 'acme-corp',
      role: 'manager',
      is_disabled: false,
      created_at: '2026-01-01T00:00:00Z',
    },
  ],
};

/** /mine as a plain member sees it (membership role drives the permissions). */
const ORG_MINE_AS_MEMBER = {
  organizations: [
    { ...ORG_MINE.organizations[0], role: 'member' },
  ],
};

const MEMBERS = {
  members: [
    {
      user_id: 'u-1',
      username: 'alice',
      role: 'manager',
      created_at: '2026-01-15T10:00:00Z',
    },
    {
      user_id: 'u-2',
      username: 'bob',
      role: 'member',
      created_at: '2026-02-01T10:00:00Z',
    },
  ],
};

vi.mock('../../../hooks/useAuth', () => ({
  useAuth: vi.fn(),
  useLogout: vi.fn(() => ({ mutate: vi.fn() })),
}));

import { useAuth } from '../../../hooks/useAuth';
import type { AuthUser } from '../../../hooks/useAuth';

vi.mock('../../../api/client', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    patch: vi.fn(),
    delete: vi.fn(),
  },
}));

import api from '../../../api/client';

const mockedApi = vi.mocked(api, true);

function mockAuth(auth: Partial<AuthUser>) {
  vi.mocked(useAuth).mockReturnValue({
    data: {
      user_id: 'u-1',
      username: 'tester',
      role: 'user',
      csrf_required: true,
      session_expires_at: '2026-12-31T00:00:00Z',
      step_up_until: null,
      ...auth,
    } as AuthUser,
    isLoading: false,
    isError: false,
    error: null,
  } as any);
}

function renderPage(auth: Partial<AuthUser>) {
  mockAuth(auth);
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <OrgMembersPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

/** Route the mocked GET by URL so /mine and /members both resolve. */
function mockGets(handlers: Record<string, unknown>) {
  mockedApi.get.mockImplementation((url: string) => {
    for (const [key, payload] of Object.entries(handlers)) {
      if (url.includes(key)) return Promise.resolve({ data: payload });
    }
    return Promise.reject({ response: { status: 404, data: { detail: 'not found' } } });
  });
}

describe('OrgMembersPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders the member list with roles for an org manager', async () => {
    mockGets({ '/v1/organizations/mine': ORG_MINE, '/members': MEMBERS });
    renderPage({ permissions: ORG_MANAGER_PERMISSIONS });

    await waitFor(() => expect(screen.getByText('alice')).toBeInTheDocument());
    expect(screen.getByText('bob')).toBeInTheDocument();
    expect(screen.getAllByText('Manager').length).toBeGreaterThan(0);
    expect(screen.getAllByText('Member').length).toBeGreaterThan(0);
    expect(screen.getByText('Add Member')).toBeInTheDocument();
    // Joined date is locale-formatted, not raw ISO.
    expect(screen.getByText('1/15/2026')).toBeInTheDocument();
  });

  it('shows the read-only notice and no add button for a plain org member', async () => {
    mockGets({
      '/v1/organizations/mine': ORG_MINE_AS_MEMBER,
      '/members': { members: [] },
    });
    renderPage({ permissions: ORG_MEMBER_PERMISSIONS });

    await waitFor(() =>
      expect(screen.getByText(/only an organization manager can/)).toBeInTheDocument(),
    );
    expect(screen.queryByText('Add Member')).not.toBeInTheDocument();
  });

  it('shows the no-organizations empty state when /mine is empty', async () => {
    mockGets({ '/v1/organizations/mine': { organizations: [] } });
    renderPage({ permissions: ORG_MANAGER_PERMISSIONS });

    await waitFor(() =>
      expect(screen.getByText('You are not a member of any organization')).toBeInTheDocument(),
    );
  });

  it('adds a member by user id (UUID contract) on submit', async () => {
    mockGets({ '/v1/organizations/mine': ORG_MINE, '/members': MEMBERS });
    mockedApi.post.mockResolvedValueOnce({ data: MEMBERS.members[1] });
    renderPage({ permissions: ORG_MANAGER_PERMISSIONS });

    await waitFor(() => expect(screen.getByText('Add Member')).toBeInTheDocument());
    fireEvent.click(screen.getByText('Add Member'));

    // A manager has no user:read:global -> the UUID field, not the search.
    expect(await screen.findByLabelText('User ID')).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText('User ID'), {
      target: { value: '00000000-0000-0000-0000-000000000003' },
    });
    fireEvent.click(screen.getByText('Submit'));

    await waitFor(() =>
      expect(mockedApi.post).toHaveBeenCalledWith('/v1/organizations/org-1/members', {
        user_id: '00000000-0000-0000-0000-000000000003',
        role: 'member',
      }),
    );
  });

  it('blocks add when the user id is empty', async () => {
    mockGets({ '/v1/organizations/mine': ORG_MINE, '/members': MEMBERS });
    renderPage({ permissions: ORG_MANAGER_PERMISSIONS });

    await waitFor(() => expect(screen.getByText('Add Member')).toBeInTheDocument());
    fireEvent.click(screen.getByText('Add Member'));
    fireEvent.click(screen.getByText('Submit'));

    await waitFor(() =>
      expect(screen.getByText('User ID is required')).toBeInTheDocument(),
    );
    expect(mockedApi.post).not.toHaveBeenCalled();
  });

  it('surfaces the backend error when add fails', async () => {
    mockGets({ '/v1/organizations/mine': ORG_MINE, '/members': MEMBERS });
    mockedApi.post.mockRejectedValueOnce({
      response: { data: { error: { message: 'User is already a member of this organization.' } } },
    });
    renderPage({ permissions: ORG_MANAGER_PERMISSIONS });

    await waitFor(() => expect(screen.getByText('Add Member')).toBeInTheDocument());
    fireEvent.click(screen.getByText('Add Member'));
    fireEvent.change(screen.getByLabelText('User ID'), {
      target: { value: 'u-2' },
    });
    fireEvent.click(screen.getByText('Submit'));

    await waitFor(() =>
      expect(screen.getByText(/already a member/)).toBeInTheDocument(),
    );
  });

  it('changes a member role via the edit action', async () => {
    mockGets({ '/v1/organizations/mine': ORG_MINE, '/members': MEMBERS });
    mockedApi.patch.mockResolvedValueOnce({ data: MEMBERS.members[1] });
    renderPage({ permissions: ORG_MANAGER_PERMISSIONS });

    await waitFor(() => expect(screen.getByText('bob')).toBeInTheDocument());
    fireEvent.click(screen.getAllByText('Change Role')[0]);

    expect(await screen.findByRole('heading', { name: 'Change Member Role' })).toBeInTheDocument();
    // Switch the first member (alice, manager) down to member.
    fireEvent.change(screen.getByLabelText('Role'), { target: { value: 'member' } });
    fireEvent.click(screen.getByText('Submit'));

    await waitFor(() =>
      expect(mockedApi.patch).toHaveBeenCalledWith(
        '/v1/organizations/org-1/members/u-1',
        { role: 'member' },
      ),
    );
  });

  it('removes a member after confirmation', async () => {
    mockGets({ '/v1/organizations/mine': ORG_MINE, '/members': MEMBERS });
    mockedApi.delete.mockResolvedValueOnce({ data: { removed: true } });
    renderPage({ permissions: ORG_MANAGER_PERMISSIONS });

    await waitFor(() => expect(screen.getByText('bob')).toBeInTheDocument());
    fireEvent.click(screen.getAllByText('Delete')[0]);

    const dialog = await screen.findByRole('heading', { name: 'Remove Member' });
    const dialogContainer = dialog.closest('.bg-pixel-surface')!;
    fireEvent.click(
      within(dialogContainer as HTMLElement).getByRole('button', { name: 'Delete' }),
    );

    await waitFor(() =>
      expect(mockedApi.delete).toHaveBeenCalledWith('/v1/organizations/org-1/members/u-1'),
    );
  });

  it('renders the org selector when the session holds multiple memberships', async () => {
    mockGets({
      '/v1/organizations/mine': {
        organizations: [
          ...ORG_MINE.organizations,
          {
            org_id: 'org-2',
            name: 'Globex',
            slug: 'globex',
            role: 'member',
            is_disabled: false,
            created_at: '2026-03-01T00:00:00Z',
          },
        ],
      },
      '/members': MEMBERS,
    });
    renderPage({ permissions: ORG_MANAGER_PERMISSIONS });

    const selector = await screen.findByLabelText('Organization');
    expect(selector).toBeInTheDocument();
    expect((selector as HTMLSelectElement).value).toBe('org-1');
  });

  it('shows the load error when /mine fails', async () => {
    mockedApi.get.mockRejectedValueOnce({ response: { status: 500 } });
    renderPage({ permissions: ORG_MANAGER_PERMISSIONS });

    await waitFor(() =>
      expect(screen.getByText('Failed to load organizations')).toBeInTheDocument(),
    );
  });
});

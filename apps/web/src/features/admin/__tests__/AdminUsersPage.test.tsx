import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { RouterForTesting } from '../../../test-utils';
import AdminUsersPage from '../AdminUsersPage';

vi.mock('../../../api/client', () => ({
  default: { get: vi.fn(), post: vi.fn() },
}));

vi.mock('../../../hooks/useAuth', () => ({
  useAuth: vi.fn(),
}));

import api from '../../../api/client';
import { useAuth } from '../../../hooks/useAuth';

function renderWithClient(ui: React.ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false, refetchOnWindowFocus: false },
      mutations: { retry: false },
    },
  });
  return render(<QueryClientProvider client={queryClient}><RouterForTesting>{ui}</RouterForTesting></QueryClientProvider>);
}

const mockUsers = {
  users: [
    {
      user_id: 'u1',
      username: 'alice',
      role: 'user',
      is_disabled: false,
      agents_count: 2,
      active_api_keys_count: 1,
      tasks_24h: 5,
      failed_tasks_24h: 0,
      created_at: '2024-01-01',
    },
    {
      user_id: 'u2',
      username: 'bob',
      role: 'admin',
      is_disabled: true,
      agents_count: 0,
      active_api_keys_count: 0,
      tasks_24h: 0,
      failed_tasks_24h: 0,
      created_at: '2024-01-02',
    },
  ],
  total: 2,
};

function setupAuth(overrides: Record<string, any> = {}) {
  (useAuth as any).mockReturnValue({
    data: {
      user_id: 'admin1',
      username: 'admin',
      role: 'super_admin',
      permissions: [],
      step_up_until: null,
      ...overrides,
    },
    isLoading: false,
    isError: false,
  });
}

function clickDialogButton(label: string) {
  const buttons = screen.getAllByText(label);
  fireEvent.click(buttons[buttons.length - 1]);
}

describe('AdminUsersPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    (api.get as any).mockResolvedValue({ data: mockUsers });
  });

  it('renders user table with data', async () => {
    setupAuth();
    renderWithClient(<AdminUsersPage />);

    await waitFor(() => {
      expect(screen.getByText('alice')).toBeInTheDocument();
      expect(screen.getByText('bob')).toBeInTheDocument();
    });
  });

  it('shows action buttons for super_admin', async () => {
    setupAuth();
    renderWithClient(<AdminUsersPage />);

    await waitFor(() => {
      expect(screen.getByText('Disable')).toBeInTheDocument();
      expect(screen.getByText('Enable')).toBeInTheDocument();
      expect(screen.getAllByText('Revoke Keys')).toHaveLength(2);
    });
  });

  it('shows super admin required text for non-super-admin', async () => {
    setupAuth({ role: 'admin' });
    renderWithClient(<AdminUsersPage />);

    await waitFor(() => {
      const hints = screen.getAllByText('Super admin required');
      expect(hints.length).toBeGreaterThanOrEqual(1);
    });
  });

  it('opens confirm dialog when Disable is clicked', async () => {
    setupAuth();
    renderWithClient(<AdminUsersPage />);

    await waitFor(() => {
      expect(screen.getByText('Disable')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText('Disable'));

    expect(screen.getByText('Disable User')).toBeInTheDocument();
    expect(screen.getByText(/Disable user "alice"/)).toBeInTheDocument();
  });

  it('opens confirm dialog when Revoke Keys is clicked', async () => {
    setupAuth();
    renderWithClient(<AdminUsersPage />);

    await waitFor(() => {
      expect(screen.getAllByText('Revoke Keys').length).toBeGreaterThanOrEqual(1);
    });

    fireEvent.click(screen.getAllByText('Revoke Keys')[0]);

    expect(screen.getByText('Force Revoke API Keys')).toBeInTheDocument();
  });

  it('calls disable API after confirm when step-up is not needed', async () => {
    setupAuth({ step_up_until: new Date(Date.now() + 3600000).toISOString() });
    (api.post as any).mockResolvedValue({ data: { ok: true } });
    renderWithClient(<AdminUsersPage />);

    await waitFor(() => {
      expect(screen.getByText('Disable')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText('Disable')); // table action button
    clickDialogButton('Disable'); // confirm dialog button

    await waitFor(() => {
      expect(api.post).toHaveBeenCalledWith('/v1/dashboard/admin/users/u1/disable', {
        is_disabled: true,
      });
    });
  });

  it('shows step-up dialog when step-up is needed', async () => {
    setupAuth({ step_up_until: null });
    renderWithClient(<AdminUsersPage />);

    await waitFor(() => {
      expect(screen.getByText('Disable')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText('Disable')); // table action button
    clickDialogButton('Disable'); // confirm dialog button

    await waitFor(() => {
      expect(screen.getByText('Step-Up Verification')).toBeInTheDocument();
    });
  });

  it('shows error message on API failure', async () => {
    setupAuth({ step_up_until: new Date(Date.now() + 3600000).toISOString() });
    (api.post as any).mockRejectedValue({
      response: { data: { detail: 'User not found' } },
    });
    renderWithClient(<AdminUsersPage />);

    await waitFor(() => {
      expect(screen.getByText('Disable')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText('Disable')); // table action button
    clickDialogButton('Disable'); // confirm dialog button

    await waitFor(() => {
      expect(screen.getByTestId('action-error')).toHaveTextContent('User not found');
    });
  });

  it('calls force-revoke API after confirm without step-up', async () => {
    setupAuth({ step_up_until: new Date(Date.now() + 3600000).toISOString() });
    (api.post as any).mockResolvedValue({ data: { ok: true } });
    renderWithClient(<AdminUsersPage />);

    await waitFor(() => {
      expect(screen.getAllByText('Revoke Keys').length).toBeGreaterThanOrEqual(1);
    });

    fireEvent.click(screen.getAllByText('Revoke Keys')[0]); // table action button
    clickDialogButton('Revoke Keys'); // confirm dialog button

    await waitFor(() => {
      expect(api.post).toHaveBeenCalledWith('/v1/dashboard/admin/users/u1/force-revoke-keys');
    });
  });

  it('closes confirm dialog when cancel is clicked', async () => {
    setupAuth();
    renderWithClient(<AdminUsersPage />);

    await waitFor(() => {
      expect(screen.getByText('Disable')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText('Disable'));
    expect(screen.getByText('Disable User')).toBeInTheDocument();

    const cancelButtons = screen.getAllByText('Cancel');
    fireEvent.click(cancelButtons[cancelButtons.length - 1]);

    await waitFor(() => {
      expect(screen.queryByText('Disable User')).not.toBeInTheDocument();
    });
  });

  it('renders View links for each user', async () => {
    setupAuth();
    renderWithClient(<AdminUsersPage />);

    await waitFor(() => {
      const viewLinks = screen.getAllByText('View');
      expect(viewLinks.length).toBe(2);
    });

    const aliceLink = screen.getAllByText('View')[0].closest('a');
    expect(aliceLink).toHaveAttribute('href', '/admin/users/u1');

    const bobLink = screen.getAllByText('View')[1].closest('a');
    expect(bobLink).toHaveAttribute('href', '/admin/users/u2');
  });
});

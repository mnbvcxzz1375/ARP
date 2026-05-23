import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { RouterForTesting } from '../../../test-utils';
import AdminAgentsPage from '../AdminAgentsPage';

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

const mockAgents = {
  agents: [
    {
      agent_id: 'a1',
      name: 'Agent Alpha',
      agent_number: 'AGT-001',
      owner_username: 'alice',
      status: 'online',
      runtime: 'python',
      inbound_policy: 'contacts_only',
      tasks_24h: 10,
      failed_tasks_24h: 2,
    },
    {
      agent_id: 'a2',
      name: 'Agent Beta',
      agent_number: 'AGT-002',
      owner_username: 'bob',
      status: 'offline',
      runtime: 'node',
      inbound_policy: 'public',
      tasks_24h: 0,
      failed_tasks_24h: 0,
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

describe('AdminAgentsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    (api.get as any).mockResolvedValue({ data: mockAgents });
  });

  it('renders agent table with data', async () => {
    setupAuth();
    renderWithClient(<AdminAgentsPage />);

    await waitFor(() => {
      expect(screen.getByText('Agent Alpha')).toBeInTheDocument();
      expect(screen.getByText('Agent Beta')).toBeInTheDocument();
    });
  });

  it('shows Disable button for online agent as super_admin', async () => {
    setupAuth();
    renderWithClient(<AdminAgentsPage />);

    await waitFor(() => {
      expect(screen.getByText('Disable')).toBeInTheDocument();
      expect(screen.getByText('Enable')).toBeInTheDocument();
    });
  });

  it('shows super admin required text for non-super-admin', async () => {
    setupAuth({ role: 'admin' });
    renderWithClient(<AdminAgentsPage />);

    await waitFor(() => {
      const hints = screen.getAllByText('Super admin required');
      expect(hints.length).toBeGreaterThanOrEqual(1);
    });
  });

  it('opens confirm dialog when Disable is clicked', async () => {
    setupAuth();
    renderWithClient(<AdminAgentsPage />);

    await waitFor(() => {
      expect(screen.getByText('Disable')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText('Disable'));

    expect(screen.getByText('Disable Agent')).toBeInTheDocument();
  });

  it('calls disable API with status offline after confirm without step-up', async () => {
    setupAuth({ step_up_until: new Date(Date.now() + 3600000).toISOString() });
    (api.post as any).mockResolvedValue({ data: { ok: true } });
    renderWithClient(<AdminAgentsPage />);

    await waitFor(() => {
      expect(screen.getByText('Disable')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText('Disable')); // table action button
    clickDialogButton('Disable'); // confirm dialog button

    await waitFor(() => {
      expect(api.post).toHaveBeenCalledWith('/v1/dashboard/admin/agents/a1/disable', {
        status: 'offline',
      });
    });
  });

  it('calls disable API with status online for offline agent', async () => {
    setupAuth({ step_up_until: new Date(Date.now() + 3600000).toISOString() });
    (api.post as any).mockResolvedValue({ data: { ok: true } });
    renderWithClient(<AdminAgentsPage />);

    await waitFor(() => {
      expect(screen.getByText('Enable')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText('Enable')); // table action button
    clickDialogButton('Enable'); // confirm dialog button

    await waitFor(() => {
      expect(api.post).toHaveBeenCalledWith('/v1/dashboard/admin/agents/a2/disable', {
        status: 'online',
      });
    });
  });

  it('shows step-up dialog when step-up is needed', async () => {
    setupAuth({ step_up_until: null });
    renderWithClient(<AdminAgentsPage />);

    await waitFor(() => {
      expect(screen.getByText('Disable')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText('Disable')); // table action button
    clickDialogButton('Disable'); // confirm dialog button

    await waitFor(() => {
      expect(screen.getByText('Step-Up Verification')).toBeInTheDocument();
    });
  });

  it('renders View links for each agent', async () => {
    setupAuth();
    renderWithClient(<AdminAgentsPage />);

    await waitFor(() => {
      const viewLinks = screen.getAllByText('View');
      expect(viewLinks.length).toBe(2);
    });

    const alphaLink = screen.getAllByText('View')[0].closest('a');
    expect(alphaLink).toHaveAttribute('href', '/admin/agents/a1');

    const betaLink = screen.getAllByText('View')[1].closest('a');
    expect(betaLink).toHaveAttribute('href', '/admin/agents/a2');
  });

  it('shows error message on API failure', async () => {
    setupAuth({ step_up_until: new Date(Date.now() + 3600000).toISOString() });
    (api.post as any).mockRejectedValue({
      response: { data: { detail: 'Agent not found' } },
    });
    renderWithClient(<AdminAgentsPage />);

    await waitFor(() => {
      expect(screen.getByText('Disable')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText('Disable')); // table action button
    clickDialogButton('Disable'); // confirm dialog button

    await waitFor(() => {
      expect(screen.getByTestId('action-error')).toHaveTextContent('Agent not found');
    });
  });
});

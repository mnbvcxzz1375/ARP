import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import ConnectionsPage from '../ConnectionsPage';

vi.mock('../../../api/client', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    patch: vi.fn(),
  },
}));

import api from '../../../api/client';

const mockAgent = {
  agent_id: 'agent_001',
  agent_number: 'AN-000001',
  inbound_policy: 'private',
  pending_requests: 2,
  accepted_connections: 5,
  rejected_connections: 1,
};

const mockPendingRequest = {
  connection_id: 'conn_pending_001',
  agent_number: 'AN-000099',
  requester_agent: 'agent_099',
  requested_policy: 'request_approval',
  created_at: '2026-05-19T00:00:00Z',
};

const mockAgents = [
  mockAgent,
  {
    agent_id: 'agent_002',
    agent_number: 'AN-000002',
    inbound_policy: 'public',
    pending_requests: 0,
    accepted_connections: 3,
    rejected_connections: 0,
  },
];

const mockPendingRequests = [
  mockPendingRequest,
  {
    connection_id: 'conn_pending_002',
    agent_number: 'AN-000003',
    requester_agent: 'agent_003',
    requested_policy: 'public',
    created_at: '2026-05-18T00:00:00Z',
  },
];

function renderPage() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <ConnectionsPage />
    </QueryClientProvider>,
  );
}

describe('ConnectionsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders error state when query fails', async () => {
    (api.get as any).mockRejectedValue(new Error('Network error'));
    renderPage();
    await waitFor(() => {
      expect(screen.getByText('Failed to load connections')).toBeInTheDocument();
    });
  });

  it('renders the page title and both tables', async () => {
    (api.get as any).mockResolvedValue({
      data: { agents: mockAgents, pending_requests: mockPendingRequests },
    });
    renderPage();
    await waitFor(() => {
      expect(screen.getByText('Connections & Firewall')).toBeInTheDocument();
      expect(screen.getByText('Agents')).toBeInTheDocument();
      expect(screen.getByText('Pending Requests')).toBeInTheDocument();
      expect(screen.getByText('AN-000001')).toBeInTheDocument();
      expect(screen.getByText('AN-000002')).toBeInTheDocument();
    });
  });

  // ── Part A: Accept / Reject ──────────────────────────────────

  it('renders Accept and Reject buttons for pending requests', async () => {
    (api.get as any).mockResolvedValue({
      data: { agents: mockAgents, pending_requests: mockPendingRequests },
    });
    renderPage();
    await waitFor(() => {
      expect(screen.getAllByText('Accept').length).toBeGreaterThan(0);
      expect(screen.getAllByText('Reject').length).toBeGreaterThan(0);
    });
    expect(screen.getByText('Actions')).toBeInTheDocument();
  });

  it('opens the accept confirm dialog when Accept is clicked', async () => {
    (api.get as any).mockResolvedValue({
      data: { agents: mockAgents, pending_requests: [mockPendingRequest] },
    });
    renderPage();
    await waitFor(() => expect(screen.getByText('Accept')).toBeInTheDocument());

    fireEvent.click(screen.getByText('Accept'));

    expect(screen.getByText('Accept Connection')).toBeInTheDocument();
    expect(
      screen.getByText('Are you sure you want to accept this connection request?'),
    ).toBeInTheDocument();
  });

  it('opens the reject confirm dialog when Reject is clicked', async () => {
    (api.get as any).mockResolvedValue({
      data: { agents: mockAgents, pending_requests: [mockPendingRequest] },
    });
    renderPage();
    await waitFor(() => expect(screen.getByText('Reject')).toBeInTheDocument());

    fireEvent.click(screen.getByText('Reject'));

    expect(screen.getByText('Reject Connection')).toBeInTheDocument();
    expect(
      screen.getByText('Are you sure you want to reject this connection request?'),
    ).toBeInTheDocument();
  });

  it('calls the accept API endpoint when confirm is clicked', async () => {
    (api.get as any).mockResolvedValue({
      data: { agents: mockAgents, pending_requests: [mockPendingRequest] },
    });
    (api.post as any).mockResolvedValue({
      data: { connection_id: 'conn_pending_001', status: 'accepted' },
    });
    renderPage();

    await waitFor(() => expect(screen.getByText('Accept')).toBeInTheDocument());
    fireEvent.click(screen.getByText('Accept'));

    const allAcceptButtons = screen.getAllByText('Accept');
    fireEvent.click(allAcceptButtons[allAcceptButtons.length - 1]);

    await waitFor(() => {
      expect(api.post).toHaveBeenCalledWith(
        '/v1/dashboard/connections/conn_pending_001/accept',
      );
    });
  });

  it('calls the reject API endpoint when confirm is clicked', async () => {
    (api.get as any).mockResolvedValue({
      data: { agents: mockAgents, pending_requests: [mockPendingRequest] },
    });
    (api.post as any).mockResolvedValue({
      data: { connection_id: 'conn_pending_001', status: 'rejected' },
    });
    renderPage();

    await waitFor(() => expect(screen.getByText('Reject')).toBeInTheDocument());
    fireEvent.click(screen.getByText('Reject'));

    const allRejectButtons = screen.getAllByText('Reject');
    fireEvent.click(allRejectButtons[allRejectButtons.length - 1]);

    await waitFor(() => {
      expect(api.post).toHaveBeenCalledWith(
        '/v1/dashboard/connections/conn_pending_001/reject',
      );
    });
  });

  it('shows error message when accept mutation fails', async () => {
    (api.get as any).mockResolvedValue({
      data: { agents: mockAgents, pending_requests: [mockPendingRequest] },
    });
    (api.post as any).mockRejectedValue({
      response: { data: { detail: 'Connection is no longer pending' } },
      message: 'Request failed',
    });
    renderPage();

    await waitFor(() => expect(screen.getByText('Accept')).toBeInTheDocument());
    fireEvent.click(screen.getByText('Accept'));

    const allAcceptButtons = screen.getAllByText('Accept');
    fireEvent.click(allAcceptButtons[allAcceptButtons.length - 1]);

    await waitFor(() => {
      expect(screen.getByText('Connection is no longer pending')).toBeInTheDocument();
    });
  });

  it('shows error message when reject mutation fails', async () => {
    (api.get as any).mockResolvedValue({
      data: { agents: mockAgents, pending_requests: [mockPendingRequest] },
    });
    (api.post as any).mockRejectedValue({
      response: { data: { detail: 'Cannot reject this connection at this time' } },
      message: 'Request failed',
    });
    renderPage();

    await waitFor(() => expect(screen.getByText('Reject')).toBeInTheDocument());
    fireEvent.click(screen.getByText('Reject'));

    const allRejectButtons = screen.getAllByText('Reject');
    fireEvent.click(allRejectButtons[allRejectButtons.length - 1]);

    await waitFor(() => {
      expect(
        screen.getByText('Cannot reject this connection at this time'),
      ).toBeInTheDocument();
    });
  });

  it('shows fallback error when API returns no detail', async () => {
    (api.get as any).mockResolvedValue({
      data: { agents: mockAgents, pending_requests: [mockPendingRequest] },
    });
    (api.post as any).mockRejectedValue(new Error('Network failure'));
    renderPage();

    await waitFor(() => expect(screen.getByText('Accept')).toBeInTheDocument());
    fireEvent.click(screen.getByText('Accept'));

    const allAcceptButtons = screen.getAllByText('Accept');
    fireEvent.click(allAcceptButtons[allAcceptButtons.length - 1]);

    await waitFor(() => {
      expect(screen.getByText('Network failure')).toBeInTheDocument();
    });
  });

  it('closes the dialog when Cancel is clicked', async () => {
    (api.get as any).mockResolvedValue({
      data: { agents: mockAgents, pending_requests: [mockPendingRequest] },
    });
    renderPage();

    await waitFor(() => expect(screen.getByText('Accept')).toBeInTheDocument());
    fireEvent.click(screen.getByText('Accept'));
    expect(screen.getByText('Accept Connection')).toBeInTheDocument();

    fireEvent.click(screen.getByText('Cancel'));
    expect(screen.queryByText('Accept Connection')).not.toBeInTheDocument();
  });

  // ── Part B: Firewall Policy Editing ──────────────────────────

  it('renders policy select dropdowns for each agent', async () => {
    (api.get as any).mockResolvedValue({
      data: { agents: mockAgents, pending_requests: [] },
    });
    renderPage();
    await waitFor(() => {
      const selects = screen.getAllByRole('combobox');
      expect(selects.length).toBe(mockAgents.length);
      expect(selects[0]).toHaveValue('private');
      expect(selects[1]).toHaveValue('public');
    });
  });

  it('calls PATCH firewall endpoint when policy is changed', async () => {
    (api.get as any).mockResolvedValue({
      data: { agents: mockAgents, pending_requests: [] },
    });
    (api.patch as any).mockResolvedValue({
      data: { agent_id: 'agent_001', inbound_policy: 'public' },
    });
    renderPage();

    await waitFor(() => {
      const selects = screen.getAllByRole('combobox');
      expect(selects[0]).toHaveValue('private');
    });

    const selects = screen.getAllByRole('combobox');
    fireEvent.change(selects[0], { target: { value: 'public' } });

    await waitFor(() => {
      expect(api.patch).toHaveBeenCalledWith(
        '/v1/dashboard/agents/agent_001/firewall',
        { inbound_policy: 'public' },
      );
    });
  });

  it('shows saving indicator while firewall mutation is pending', async () => {
    (api.get as any).mockResolvedValue({
      data: { agents: [mockAgent], pending_requests: [] },
    });
    // Return a promise that never resolves so we stay in pending state
    (api.patch as any).mockImplementation(() => new Promise(() => {}));
    renderPage();

    await waitFor(() => {
      const selects = screen.getAllByRole('combobox');
      expect(selects[0]).toHaveValue('private');
    });

    const selects = screen.getAllByRole('combobox');
    fireEvent.change(selects[0], { target: { value: 'public' } });

    await waitFor(() => {
      expect(screen.getByText('Saving...')).toBeInTheDocument();
    });
  });

  it('shows error when firewall patch fails', async () => {
    (api.get as any).mockResolvedValue({
      data: { agents: [mockAgent], pending_requests: [] },
    });
    (api.patch as any).mockRejectedValue({
      response: { data: { detail: 'Invalid policy value' } },
      message: 'Request failed',
    });
    renderPage();

    await waitFor(() => {
      const selects = screen.getAllByRole('combobox');
      expect(selects[0]).toHaveValue('private');
    });

    const selects = screen.getAllByRole('combobox');
    fireEvent.change(selects[0], { target: { value: 'public' } });

    await waitFor(() => {
      expect(screen.getByText('Invalid policy value')).toBeInTheDocument();
    });
  });

  it('reverts dropdown to previous value on firewall patch failure', async () => {
    (api.get as any).mockResolvedValue({
      data: { agents: [mockAgent], pending_requests: [] },
    });
    (api.patch as any).mockRejectedValue(new Error('Server error'));
    renderPage();

    await waitFor(() => {
      const selects = screen.getAllByRole('combobox');
      expect(selects[0]).toHaveValue('private');
    });

    const selects = screen.getAllByRole('combobox');
    fireEvent.change(selects[0], { target: { value: 'public' } });

    await waitFor(() => {
      // After error, the dropdown should revert to the original value
      const selectsAfter = screen.getAllByRole('combobox');
      expect(selectsAfter[0]).toHaveValue('private');
    });
  });
});

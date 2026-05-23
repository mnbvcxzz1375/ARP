import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import ApprovalsPage from '../ApprovalsPage';

vi.mock('../../../api/client', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
  },
}));

import api from '../../../api/client';

const mockPendingApproval = {
  approval_id: 'aprv_pending_001',
  type: 'connection',
  status: 'pending',
  risk_level: 'medium',
  action_kind: 'approve_connection',
  created_at: '2026-05-19T00:00:00Z',
};

const mockApprovals = [
  mockPendingApproval,
  {
    approval_id: 'aprv_accepted_001',
    type: 'task',
    status: 'accepted',
    risk_level: 'high',
    action_kind: 'execute_task',
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
      <ApprovalsPage />
    </QueryClientProvider>,
  );
}

describe('ApprovalsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders error state when query fails', async () => {
    (api.get as any).mockRejectedValue(new Error('Network error'));
    renderPage();
    await waitFor(() => {
      expect(screen.getByText('Failed to load approvals')).toBeInTheDocument();
    });
  });

  it('renders the page title and table', async () => {
    (api.get as any).mockResolvedValue({ data: { approvals: mockApprovals } });
    renderPage();
    await waitFor(() => {
      expect(screen.getByText('Approvals')).toBeInTheDocument();
      expect(screen.getByText('Pending')).toBeInTheDocument();
      expect(screen.getByText('Accepted')).toBeInTheDocument();
    });
  });

  it('shows Accept and Reject buttons for pending approvals only', async () => {
    (api.get as any).mockResolvedValue({ data: { approvals: mockApprovals } });
    renderPage();
    await waitFor(() => {
      expect(screen.getByText('Accept')).toBeInTheDocument();
      expect(screen.getByText('Reject')).toBeInTheDocument();
    });
    expect(screen.getByText('Actions')).toBeInTheDocument();
  });

  it('opens the accept confirm dialog when Accept is clicked', async () => {
    (api.get as any).mockResolvedValue({ data: { approvals: [mockPendingApproval] } });
    renderPage();
    await waitFor(() => expect(screen.getByText('Accept')).toBeInTheDocument());

    fireEvent.click(screen.getByText('Accept'));

    expect(screen.getByText('Accept Approval')).toBeInTheDocument();
    expect(
      screen.getByText('Are you sure you want to accept this approval request?'),
    ).toBeInTheDocument();
  });

  it('opens the reject confirm dialog when Reject is clicked', async () => {
    (api.get as any).mockResolvedValue({ data: { approvals: [mockPendingApproval] } });
    renderPage();
    await waitFor(() => expect(screen.getByText('Reject')).toBeInTheDocument());

    fireEvent.click(screen.getByText('Reject'));

    expect(screen.getByText('Reject Approval')).toBeInTheDocument();
    expect(
      screen.getByText('Are you sure you want to reject this approval request?'),
    ).toBeInTheDocument();
  });

  it('calls the accept API endpoint when confirm is clicked', async () => {
    (api.get as any).mockResolvedValue({ data: { approvals: [mockPendingApproval] } });
    (api.post as any).mockResolvedValue({
      data: { approval_id: 'aprv_pending_001', status: 'accepted' },
    });
    renderPage();

    await waitFor(() => expect(screen.getByText('Accept')).toBeInTheDocument());
    fireEvent.click(screen.getByText('Accept'));

    // The confirm button in the dialog also reads "Accept"
    const allAcceptButtons = screen.getAllByText('Accept');
    // allAcceptButtons[0] is the table row button; last is the dialog confirm button
    fireEvent.click(allAcceptButtons[allAcceptButtons.length - 1]);

    await waitFor(() => {
      expect(api.post).toHaveBeenCalledWith(
        '/v1/dashboard/approvals/aprv_pending_001/accept',
      );
    });
  });

  it('calls the reject API endpoint when confirm is clicked', async () => {
    (api.get as any).mockResolvedValue({ data: { approvals: [mockPendingApproval] } });
    (api.post as any).mockResolvedValue({
      data: { approval_id: 'aprv_pending_001', status: 'rejected' },
    });
    renderPage();

    await waitFor(() => expect(screen.getByText('Reject')).toBeInTheDocument());
    fireEvent.click(screen.getByText('Reject'));

    const allRejectButtons = screen.getAllByText('Reject');
    fireEvent.click(allRejectButtons[allRejectButtons.length - 1]);

    await waitFor(() => {
      expect(api.post).toHaveBeenCalledWith(
        '/v1/dashboard/approvals/aprv_pending_001/reject',
      );
    });
  });

  it('shows error message when accept mutation fails', async () => {
    (api.get as any).mockResolvedValue({ data: { approvals: [mockPendingApproval] } });
    (api.post as any).mockRejectedValue({
      response: { data: { detail: 'Approval is no longer pending' } },
      message: 'Request failed',
    });
    renderPage();

    await waitFor(() => expect(screen.getByText('Accept')).toBeInTheDocument());
    fireEvent.click(screen.getByText('Accept'));

    const allAcceptButtons = screen.getAllByText('Accept');
    fireEvent.click(allAcceptButtons[allAcceptButtons.length - 1]);

    await waitFor(() => {
      expect(screen.getByText('Approval is no longer pending')).toBeInTheDocument();
    });
  });

  it('shows error message when reject mutation fails', async () => {
    (api.get as any).mockResolvedValue({ data: { approvals: [mockPendingApproval] } });
    (api.post as any).mockRejectedValue({
      response: { data: { detail: 'Cannot reject this approval at this time' } },
      message: 'Request failed',
    });
    renderPage();

    await waitFor(() => expect(screen.getByText('Reject')).toBeInTheDocument());
    fireEvent.click(screen.getByText('Reject'));

    const allRejectButtons = screen.getAllByText('Reject');
    fireEvent.click(allRejectButtons[allRejectButtons.length - 1]);

    await waitFor(() => {
      expect(
        screen.getByText('Cannot reject this approval at this time'),
      ).toBeInTheDocument();
    });
  });

  it('shows fallback error when API returns no detail', async () => {
    (api.get as any).mockResolvedValue({ data: { approvals: [mockPendingApproval] } });
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
    (api.get as any).mockResolvedValue({ data: { approvals: [mockPendingApproval] } });
    renderPage();

    await waitFor(() => expect(screen.getByText('Accept')).toBeInTheDocument());
    fireEvent.click(screen.getByText('Accept'));
    expect(screen.getByText('Accept Approval')).toBeInTheDocument();

    fireEvent.click(screen.getByText('Cancel'));
    expect(screen.queryByText('Accept Approval')).not.toBeInTheDocument();
  });
});

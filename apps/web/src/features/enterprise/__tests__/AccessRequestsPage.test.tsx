import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { RouterForTesting } from '../../../test-utils';
import AccessRequestsPage from '../AccessRequestsPage';

// Hoisted mock — factory must not reference top-level variables
vi.mock('../../../api/client', () => ({
  default: { get: vi.fn(), post: vi.fn() },
}));

import api from '../../../api/client';

function renderPage() {
  const qc = new QueryClient({
    defaultOptions: {
      queries: { retry: false, refetchOnWindowFocus: false },
      mutations: { retry: false },
    },
  });
  return render(
    <QueryClientProvider client={qc}>
      <RouterForTesting>
        <AccessRequestsPage />
      </RouterForTesting>
    </QueryClientProvider>,
  );
}

function clickLastButton(label: string) {
  const buttons = screen.getAllByText(label);
  fireEvent.click(buttons[buttons.length - 1]);
}

describe('AccessRequestsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('shows loading state initially', () => {
    (api.get as ReturnType<typeof vi.fn>).mockReturnValue(new Promise(() => {}));
    const { container } = renderPage();
    expect(container.querySelector('.animate-spin')).toBeTruthy();
  });

  it('shows error state when API fails', async () => {
    (api.get as ReturnType<typeof vi.fn>).mockRejectedValue(new Error('Network error'));
    renderPage();
    await waitFor(() => {
      expect(screen.getByText(/failed to load access requests/i)).toBeTruthy();
    });
  });

  it('renders access requests from API', async () => {
    const requests = [
      {
        request_id: 'ar-12345678-1234-5678-1234-567812345678',
        applicant_name: 'Alice',
        applicant_email: 'alice@example.com',
        organization: 'Acme Corp',
        requested_mode: 'personal',
        status: 'pending',
        created_at: '2026-05-24T12:00:00Z',
        reviewed_at: null,
      },
    ];
    (api.get as ReturnType<typeof vi.fn>).mockResolvedValue({ data: { access_requests: requests, total: 1 } });
    renderPage();
    await waitFor(() => {
      expect(screen.getByText('Alice')).toBeTruthy();
      expect(screen.getByText('alice@example.com')).toBeTruthy();
      expect(screen.getByText('personal')).toBeTruthy();
    });
  });

  it('shows approve and reject buttons for pending requests', async () => {
    const requests = [
      {
        request_id: 'ar-12345678-1234-5678-1234-567812345678',
        applicant_name: 'Bob',
        applicant_email: 'bob@example.com',
        organization: null,
        requested_mode: 'enterprise',
        status: 'pending',
        created_at: '2026-05-24T12:00:00Z',
        reviewed_at: null,
      },
    ];
    (api.get as ReturnType<typeof vi.fn>).mockResolvedValue({ data: { access_requests: requests, total: 1 } });
    renderPage();
    await waitFor(() => {
      expect(screen.getAllByText('Approve').length).toBeGreaterThanOrEqual(1);
      expect(screen.getAllByText('Reject').length).toBeGreaterThanOrEqual(1);
    });
  });

  it('hides action buttons for non-pending requests', async () => {
    const requests = [
      {
        request_id: 'ar-12345678-1234-5678-1234-567812345678',
        applicant_name: 'Carol',
        applicant_email: 'carol@example.com',
        organization: null,
        requested_mode: 'personal',
        status: 'approved',
        created_at: '2026-05-24T12:00:00Z',
        reviewed_at: '2026-05-24T13:00:00Z',
      },
    ];
    (api.get as ReturnType<typeof vi.fn>).mockResolvedValue({ data: { access_requests: requests, total: 1 } });
    renderPage();
    await waitFor(() => {
      const badges = screen.getAllByText('Approved');
      expect(badges.length).toBeGreaterThanOrEqual(1);
      expect(screen.queryByRole('button', { name: 'Approve' })).toBeNull();
      expect(screen.queryByRole('button', { name: 'Reject' })).toBeNull();
    });
  });

  it('shows empty state when no requests', async () => {
    (api.get as ReturnType<typeof vi.fn>).mockResolvedValue({ data: { access_requests: [], total: 0 } });
    renderPage();
    await waitFor(() => {
      expect(screen.getByText(/no access requests/i)).toBeTruthy();
    });
  });

  it('opens approve dialog when Approve is clicked', async () => {
    const requests = [
      {
        request_id: 'ar-12345678-1234-5678-1234-567812345678',
        applicant_name: 'Dave',
        applicant_email: 'dave@example.com',
        organization: null,
        requested_mode: 'personal',
        status: 'pending',
        created_at: '2026-05-24T12:00:00Z',
        reviewed_at: null,
      },
    ];
    (api.get as ReturnType<typeof vi.fn>).mockResolvedValue({ data: { access_requests: requests, total: 1 } });
    renderPage();
    await waitFor(() => {
      expect(screen.getByText('Dave')).toBeTruthy();
    });
    const approveButtons = screen.getAllByText('Approve');
    fireEvent.click(approveButtons[0]);
    await waitFor(() => {
      expect(screen.getByText(/approve access request/i)).toBeTruthy();
    });
  });

  it('shows rejection reason textarea when Reject is clicked', async () => {
    const requests = [
      {
        request_id: 'ar-12345678-1234-5678-1234-567812345678',
        applicant_name: 'Eve',
        applicant_email: 'eve@example.com',
        organization: null,
        requested_mode: 'personal',
        status: 'pending',
        created_at: '2026-05-24T12:00:00Z',
        reviewed_at: null,
      },
    ];
    (api.get as ReturnType<typeof vi.fn>).mockResolvedValue({ data: { access_requests: requests, total: 1 } });
    renderPage();
    await waitFor(() => {
      expect(screen.getByText('Eve')).toBeTruthy();
    });
    const rejectButtons = screen.getAllByText('Reject');
    fireEvent.click(rejectButtons[0]);
    await waitFor(() => {
      expect(screen.getByText(/reject access request/i)).toBeTruthy();
      expect(screen.getByPlaceholderText(/reason for rejection/i)).toBeTruthy();
    });
  });

  it('calls approve API when dialog is confirmed', async () => {
    const requestId = 'ar-12345678-1234-5678-1234-567812345678';
    const requests = [
      {
        request_id: requestId,
        applicant_name: 'Frank',
        applicant_email: 'frank@example.com',
        organization: null,
        requested_mode: 'enterprise',
        status: 'pending',
        created_at: '2026-05-24T12:00:00Z',
        reviewed_at: null,
      },
    ];
    (api.get as ReturnType<typeof vi.fn>).mockResolvedValue({ data: { access_requests: requests, total: 1 } });
    (api.post as ReturnType<typeof vi.fn>).mockResolvedValue({
      data: {
        request_id: requestId,
        status: 'approved',
        reviewed_by: 'admin-1',
        user_id: 'u-abcdef12-3456-7890-abcd-ef1234567890',
        api_key: 'ak_testkey1234567890abcdefghij',
      },
    });
    renderPage();
    await waitFor(() => {
      expect(screen.getByText('Frank')).toBeTruthy();
    });
    // Click the Approve button in the table row
    const approveButtons = screen.getAllByText('Approve');
    fireEvent.click(approveButtons[0]);
    // Now the dialog is open — click the confirm button inside the dialog (last Approve button)
    await waitFor(() => {
      expect(screen.getByText(/approve access request/i)).toBeTruthy();
    });
    clickLastButton('Approve');
    await waitFor(() => {
      expect(api.post).toHaveBeenCalledWith(
        `/v1/dashboard/admin/access-requests/${requestId}/approve`,
      );
    });
  });

  it('shows provisioned user_id and api_key after approval', async () => {
    const requestId = 'ar-12345678-1234-5678-1234-567812345678';
    const requests = [
      {
        request_id: requestId,
        applicant_name: 'Grace',
        applicant_email: 'grace@example.com',
        organization: null,
        requested_mode: 'personal',
        status: 'pending',
        created_at: '2026-05-24T12:00:00Z',
        reviewed_at: null,
      },
    ];
    (api.get as ReturnType<typeof vi.fn>).mockResolvedValue({ data: { access_requests: requests, total: 1 } });
    (api.post as ReturnType<typeof vi.fn>).mockResolvedValue({
      data: {
        request_id: requestId,
        status: 'approved',
        reviewed_by: 'admin-1',
        user_id: 'u-abcdef12-3456-7890-abcd-ef1234567890',
        api_key: 'ak_testprovisionedkey1234567890abc',
      },
    });
    renderPage();
    await waitFor(() => {
      expect(screen.getByText('Grace')).toBeTruthy();
    });
    const approveButtons = screen.getAllByText('Approve');
    fireEvent.click(approveButtons[0]);
    await waitFor(() => {
      expect(screen.getByText(/approve access request/i)).toBeTruthy();
    });
    clickLastButton('Approve');
    await waitFor(() => {
      expect(screen.getByText(/user provisioned/i)).toBeTruthy();
      expect(screen.getByText(/ak_testprovisionedkey1234567890abc/)).toBeTruthy();
      expect(screen.getByText(/u-abcdef12-3456-7890-abcd-ef1234567890/)).toBeTruthy();
    });
  });

  it('shows scope_id after enterprise approval', async () => {
    const requestId = 'ar-12345678-1234-5678-1234-567812345678';
    const requests = [
      {
        request_id: requestId,
        applicant_name: 'Hank',
        applicant_email: 'hank@example.com',
        organization: 'Hank Corp',
        requested_mode: 'enterprise',
        status: 'pending',
        created_at: '2026-05-24T12:00:00Z',
        reviewed_at: null,
      },
    ];
    (api.get as ReturnType<typeof vi.fn>).mockResolvedValue({ data: { access_requests: requests, total: 1 } });
    (api.post as ReturnType<typeof vi.fn>).mockResolvedValue({
      data: {
        request_id: requestId,
        status: 'approved',
        reviewed_by: 'admin-1',
        user_id: 'u-abcdef12-3456-7890-abcd-ef1234567890',
        api_key: 'ak_enterprisekey1234567890abcdef',
        scope_id: 'ns-scopeid12-3456-7890-abcd-ef1234567890',
      },
    });
    renderPage();
    await waitFor(() => {
      expect(screen.getByText('Hank')).toBeTruthy();
    });
    const approveButtons = screen.getAllByText('Approve');
    fireEvent.click(approveButtons[0]);
    await waitFor(() => {
      expect(screen.getByText(/approve access request/i)).toBeTruthy();
    });
    clickLastButton('Approve');
    await waitFor(() => {
      expect(screen.getByText(/user provisioned/i)).toBeTruthy();
      expect(screen.getByText(/ns-scopeid12-3456-7890-abcd-ef1234567890/)).toBeTruthy();
    });
  });

  it('blocks empty reject reason client-side', async () => {
    const requestId = 'ar-12345678-1234-5678-1234-567812345678';
    const requests = [
      {
        request_id: requestId,
        applicant_name: 'Ivy',
        applicant_email: 'ivy@example.com',
        organization: null,
        requested_mode: 'personal',
        status: 'pending',
        created_at: '2026-05-24T12:00:00Z',
        reviewed_at: null,
      },
    ];
    (api.get as ReturnType<typeof vi.fn>).mockResolvedValue({ data: { access_requests: requests, total: 1 } });
    renderPage();
    await waitFor(() => {
      expect(screen.getByText('Ivy')).toBeTruthy();
    });
    const rejectButtons = screen.getAllByText('Reject');
    fireEvent.click(rejectButtons[0]);
    await waitFor(() => {
      expect(screen.getByText(/reject access request/i)).toBeTruthy();
    });
    // Confirm with empty reason
    clickLastButton('Reject');
    await waitFor(() => {
      expect(screen.getByText(/rejection reason is required/i)).toBeTruthy();
    });
    // API should not have been called
    expect(api.post).not.toHaveBeenCalled();
  });
});

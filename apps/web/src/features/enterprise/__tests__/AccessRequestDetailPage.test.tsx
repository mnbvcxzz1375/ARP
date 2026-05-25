import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import AccessRequestDetailPage from '../AccessRequestDetailPage';

function mockAxios() {
  return {
    default: {
      get: vi.fn(),
      post: vi.fn(),
      put: vi.fn(),
      delete: vi.fn(),
    },
  };
}

vi.mock('../../../api/client', () => mockAxios());

import api from '../../../api/client';

const mockRequest = {
  request_id: 'req-123',
  applicant_name: 'Jane Doe',
  applicant_email: 'jane@example.com',
  organization: 'Acme Corp',
  requested_mode: 'enterprise',
  use_case: 'Testing',
  terms_acknowledged: true,
  status: 'pending',
  review_notes: null,
  reviewed_by: null,
  reviewed_at: null,
  request_ip: '10.0.0.1',
  created_at: '2025-01-01T00:00:00Z',
};

const mockAuditEntries = {
  audit_logs: [
    {
      audit_id: 'aud-1',
      actor_type: 'system',
      actor_id: 'sys-1',
      action: 'access_request.create',
      resource_type: 'access_request',
      resource_id: 'req-123',
      task_id: null,
      error_code: null,
      request_ip: '10.0.0.1',
      details: { email: 'jane@example.com' },
      created_at: '2025-01-01T00:00:00Z',
    },
    {
      audit_id: 'aud-2',
      actor_type: 'admin',
      actor_id: 'admin-1',
      action: 'access_request.approve',
      resource_type: 'access_request',
      resource_id: 'req-123',
      task_id: null,
      error_code: null,
      request_ip: '10.0.0.2',
      details: null,
      created_at: '2025-01-01T01:00:00Z',
    },
  ],
  total: 2,
  offset: 0,
  limit: 50,
};

function renderPage(requestId = 'req-123') {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={[`/enterprise/access-requests/${requestId}`]}>
        <Routes>
          <Route
            path="/enterprise/access-requests/:requestId"
            element={<AccessRequestDetailPage />}
          />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe('AccessRequestDetailPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders request details', async () => {
    (api.get as any).mockImplementation((url: string) => {
      if (url.includes('/audit-trail')) return Promise.resolve({ data: mockAuditEntries });
      return Promise.resolve({ data: mockRequest });
    });

    renderPage();

    await waitFor(() => {
      expect(screen.getByText('Jane Doe')).toBeInTheDocument();
    });
    expect(screen.getByText('jane@example.com')).toBeInTheDocument();
  });

  it('renders audit trail entries', async () => {
    (api.get as any).mockImplementation((url: string) => {
      if (url.includes('/audit-trail')) return Promise.resolve({ data: mockAuditEntries });
      return Promise.resolve({ data: mockRequest });
    });

    renderPage();

    await waitFor(() => {
      expect(screen.getByText('access_request.create')).toBeInTheDocument();
    });
    expect(screen.getByText('access_request.approve')).toBeInTheDocument();
    expect(screen.getByText('Showing 2 of 2 entries')).toBeInTheDocument();
  });

  it('shows empty audit trail message when no entries', async () => {
    (api.get as any).mockImplementation((url: string) => {
      if (url.includes('/audit-trail'))
        return Promise.resolve({ data: { audit_logs: [], total: 0, offset: 0, limit: 50 } });
      return Promise.resolve({ data: mockRequest });
    });

    renderPage();

    await waitFor(() => {
      expect(screen.getByText(/No audit entries for this request/)).toBeInTheDocument();
    });
  });

  it('shows error state when request fetch fails with 404', async () => {
    (api.get as any).mockImplementation((url: string) => {
      if (url.includes('/audit-trail'))
        return Promise.resolve({ data: { audit_logs: [], total: 0 } });
      const err: any = new Error('Not Found');
      err.response = { status: 404, data: { detail: 'Not found' } };
      return Promise.reject(err);
    });

    renderPage();

    await waitFor(() => {
      expect(screen.getByText(/Access request not found/)).toBeInTheDocument();
    });
  });

  it('shows access denied on 403', async () => {
    (api.get as any).mockImplementation((url: string) => {
      if (url.includes('/audit-trail'))
        return Promise.resolve({ data: { audit_logs: [], total: 0 } });
      const err: any = new Error('Forbidden');
      err.response = { status: 403, data: { detail: 'Forbidden' } };
      return Promise.reject(err);
    });

    renderPage();

    await waitFor(() => {
      expect(screen.getByText(/Access denied/)).toBeInTheDocument();
    });
  });

  it('shows audit trail error when audit fetch fails', async () => {
    (api.get as any).mockImplementation((url: string) => {
      if (url.includes('/audit-trail')) return Promise.reject(new Error('Server error'));
      return Promise.resolve({ data: mockRequest });
    });

    renderPage();

    await waitFor(() => {
      expect(screen.getByText(/Failed to load audit trail/)).toBeInTheDocument();
    });
  });
});

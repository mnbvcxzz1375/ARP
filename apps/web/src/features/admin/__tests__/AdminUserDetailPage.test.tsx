import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Route, Routes } from 'react-router-dom';
import { RouterForTesting } from '../../../test-utils';
import AdminUserDetailPage from '../AdminUserDetailPage';

vi.mock('../../../api/client', () => ({
  default: { get: vi.fn() },
}));

import api from '../../../api/client';

const mockUser = {
  user_id: 'user-001',
  username: 'testuser',
  role: 'admin',
  is_disabled: false,
  agents_count: 5,
  active_api_keys_count: 2,
  tasks_24h: 10,
  failed_tasks_24h: 1,
  active_sessions_count: 3,
  recent_audit_count: 25,
  created_at: '2024-01-01T00:00:00Z',
};

function renderDetail(userId: string) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false, refetchOnWindowFocus: false },
    },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <RouterForTesting initialEntries={[`/admin/users/${userId}`]}>
        <Routes>
          <Route path="/admin/users/:userId" element={<AdminUserDetailPage />} />
        </Routes>
      </RouterForTesting>
    </QueryClientProvider>,
  );
}

describe('AdminUserDetailPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    (api.get as any).mockResolvedValue({ data: mockUser });
  });

  it('renders user detail data', async () => {
    renderDetail('user-001');

    await waitFor(() => {
      const elements = screen.getAllByText('testuser');
      expect(elements.length).toBe(2);
      expect(screen.getByText('admin')).toBeInTheDocument();
    });
    expect(screen.getByText('No')).toBeInTheDocument();
    expect(screen.getByText('5')).toBeInTheDocument();
    expect(screen.getByText('2')).toBeInTheDocument();
    expect(screen.getByText('10')).toBeInTheDocument();
    expect(screen.getByText('1')).toBeInTheDocument();
    expect(screen.getByText('3')).toBeInTheDocument();
    expect(screen.getByText('25')).toBeInTheDocument();
  });

  it('fetches the correct endpoint', async () => {
    renderDetail('user-001');

    await waitFor(() => {
      expect(api.get).toHaveBeenCalledWith('/v1/dashboard/admin/users/user-001');
    });
  });

  it('shows error state on failure', async () => {
    (api.get as any).mockRejectedValue(new Error('Network error'));
    renderDetail('user-001');

    await waitFor(() => {
      expect(screen.getByText('Failed to load user detail')).toBeInTheDocument();
    });
  });

  it('renders back link to users list', async () => {
    renderDetail('user-001');

    await waitFor(() => {
      expect(screen.getByText('Back to Users')).toBeInTheDocument();
    });
    const link = screen.getByText('Back to Users').closest('a');
    expect(link).toHaveAttribute('href', '/admin/users');
  });

  it('shows Yes for disabled user', async () => {
    (api.get as any).mockResolvedValue({ data: { ...mockUser, is_disabled: true } });
    renderDetail('user-001');

    await waitFor(() => {
      expect(screen.getByText('Yes')).toBeInTheDocument();
    });
  });

  it('renders all expected field labels', async () => {
    renderDetail('user-001');

    await waitFor(() => {
      expect(screen.getByText('Active Sessions')).toBeInTheDocument();
      expect(screen.getByText('Recent Audit Events')).toBeInTheDocument();
      expect(screen.getByText('Username')).toBeInTheDocument();
      expect(screen.getByText('Role')).toBeInTheDocument();
    });
  });
});

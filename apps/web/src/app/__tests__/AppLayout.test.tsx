import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { RouterForTesting } from '../../test-utils';
import AppLayout from '../AppLayout';

function renderLayout(authData: { username: string; role: string } | null) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });

  vi.mocked(useAuth).mockReturnValue({
    data: authData,
    isLoading: false,
    isError: !authData,
    error: null,
  } as any);

  return render(
    <QueryClientProvider client={queryClient}>
      <RouterForTesting initialEntries={['/app/overview']}>
        <AppLayout />
      </RouterForTesting>
    </QueryClientProvider>,
  );
}

// Need to mock useAuth
vi.mock('../../hooks/useAuth', () => ({
  useAuth: vi.fn(),
  useLogout: vi.fn(() => ({ mutate: vi.fn() })),
}));

import { useAuth } from '../../hooks/useAuth';

describe('AppLayout (Unified Shell)', () => {
  it('does not show Enterprise nav for regular user', () => {
    renderLayout({ username: 'user1', role: 'user' });
    expect(screen.queryByText('Enterprise')).not.toBeInTheDocument();
  });

  it('shows Enterprise nav for admin', () => {
    renderLayout({ username: 'admin1', role: 'admin' });
    // Admin should see Enterprise button in header or sidebar
    expect(screen.getAllByText('Enterprise').length).toBeGreaterThan(0);
  });

  it('shows Enterprise nav for super_admin', () => {
    renderLayout({ username: 'super1', role: 'super_admin' });
    expect(screen.getAllByText('Enterprise').length).toBeGreaterThan(0);
  });
});
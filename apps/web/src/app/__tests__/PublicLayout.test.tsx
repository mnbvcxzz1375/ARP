import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Routes, Route } from 'react-router-dom';
import { RouterForTesting } from '../../test-utils';
import PublicLayout from '../PublicLayout';

vi.mock('../../hooks/useAuth', () => ({
  useAuth: vi.fn(),
  useLogout: vi.fn(() => ({ mutate: vi.fn() })),
}));

import { useAuth } from '../../hooks/useAuth';

function renderWithAuth(
  authState: { isLoading: boolean; isError: boolean; data: any },
  initialPath = '/request-access',
) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });

  vi.mocked(useAuth).mockReturnValue(authState as any);

  return render(
    <QueryClientProvider client={queryClient}>
      <RouterForTesting initialEntries={[initialPath]}>
        <Routes>
          <Route element={<PublicLayout />}>
            <Route
              path="/request-access"
              element={<div data-testid="request-access-page">Request Access Page</div>}
            />
          </Route>
          <Route path="/app/overview" element={<div data-testid="app-overview">Dashboard</div>} />
          <Route path="/login" element={<div data-testid="login-page">Login</div>} />
        </Routes>
      </RouterForTesting>
    </QueryClientProvider>,
  );
}

describe('PublicLayout', () => {
  it('shows child route (request-access) when unauthenticated (isError=true)', () => {
    renderWithAuth({ isLoading: false, isError: true, data: null });
    expect(screen.getByTestId('request-access-page')).toBeInTheDocument();
    expect(screen.queryByTestId('login-page')).not.toBeInTheDocument();
    expect(screen.queryByTestId('app-overview')).not.toBeInTheDocument();
  });

  it('redirects to /app/overview when authenticated', () => {
    renderWithAuth({
      isLoading: false,
      isError: false,
      data: { user_id: 'u1', username: 'alice', role: 'user' },
    });
    expect(screen.queryByTestId('request-access-page')).not.toBeInTheDocument();
    expect(screen.getByTestId('app-overview')).toBeInTheDocument();
  });

  it('shows loading state while auth is resolving', () => {
    renderWithAuth({ isLoading: true, isError: false, data: null });
    // PublicLayout renders <LoadingState /> while loading — no child route visible
    expect(screen.queryByTestId('request-access-page')).not.toBeInTheDocument();
    expect(screen.queryByTestId('app-overview')).not.toBeInTheDocument();
  });
});

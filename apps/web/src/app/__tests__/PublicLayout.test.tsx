import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Routes, Route } from 'react-router-dom';
import { RouterForTesting } from '../../test-utils';
import PublicLayout from '../PublicLayout';

vi.mock('../../hooks/useAuth', async (importOriginal) => {
  // Keep the real next-parameter validator; only the auth probe is stubbed.
  const actual = await importOriginal<typeof import('../../hooks/useAuth')>();
  return {
    ...actual,
    useAuth: vi.fn(),
    useLogout: vi.fn(() => ({ mutate: vi.fn() })),
  };
});

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
            <Route path="/login" element={<div data-testid="login-page">Login</div>} />
            <Route path="/no-access" element={<div data-testid="no-access-page">No Access</div>} />
          </Route>
          <Route path="/app/overview" element={<div data-testid="app-overview">Dashboard</div>} />
          <Route
            path="/enterprise/relay-nodes"
            element={<div data-testid="relay-nodes-page">Relay Nodes</div>}
          />
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

  it('redirects to the validated next deep link when authenticated', () => {
    renderWithAuth(
      {
        isLoading: false,
        isError: false,
        data: { user_id: 'u1', username: 'alice', role: 'user' },
      },
      `/login?next=${encodeURIComponent('/enterprise/relay-nodes')}`,
    );
    expect(screen.queryByTestId('login-page')).not.toBeInTheDocument();
    expect(screen.queryByTestId('app-overview')).not.toBeInTheDocument();
    expect(screen.getByTestId('relay-nodes-page')).toBeInTheDocument();
  });

  it('keeps the search string of the next deep link on redirect', () => {
    renderWithAuth(
      {
        isLoading: false,
        isError: false,
        data: { user_id: 'u1', username: 'alice', role: 'user' },
      },
      `/login?next=${encodeURIComponent('/enterprise/relay-nodes?region=eu')}`,
    );
    expect(screen.getByTestId('relay-nodes-page')).toBeInTheDocument();
  });

  it('falls back to /app/overview when next is a malicious non-path value', () => {
    renderWithAuth(
      {
        isLoading: false,
        isError: false,
        data: { user_id: 'u1', username: 'alice', role: 'user' },
      },
      `/login?next=${encodeURIComponent('https://evil.com')}`,
    );
    expect(screen.queryByTestId('relay-nodes-page')).not.toBeInTheDocument();
    expect(screen.getByTestId('app-overview')).toBeInTheDocument();
  });

  it('keeps an authenticated session on /no-access instead of bouncing to the console', () => {
    // The auth guards (RequireAuth/RequireAdmin) send an authenticated
    // session that lacks the required permissions to /no-access. If the
    // layout bounced such a session onward to /app/overview, it would slide
    // into a guarded route (or 401 -> /login), re-creating the redirect
    // loop the guards exist to break. e2e/no-access.spec.ts pins the same
    // contract end-to-end.
    renderWithAuth(
      {
        isLoading: false,
        isError: false,
        data: {
          user_id: 'u1',
          username: 'limited_user',
          role: 'user',
          permissions: ['agent:read:own', 'task:read:own'],
        },
      },
      '/no-access',
    );
    expect(screen.getByTestId('no-access-page')).toBeInTheDocument();
    expect(screen.queryByTestId('app-overview')).not.toBeInTheDocument();
  });

  it('renders /no-access for an unauthenticated visitor too', () => {
    renderWithAuth({ isLoading: false, isError: true, data: null }, '/no-access');
    expect(screen.getByTestId('no-access-page')).toBeInTheDocument();
    expect(screen.queryByTestId('app-overview')).not.toBeInTheDocument();
  });

  it('shows loading state while auth is resolving', () => {
    renderWithAuth({ isLoading: true, isError: false, data: null });
    // PublicLayout renders <LoadingState /> while loading, no child route visible
    expect(screen.queryByTestId('request-access-page')).not.toBeInTheDocument();
    expect(screen.queryByTestId('app-overview')).not.toBeInTheDocument();
  });
});

import { describe, it, expect, vi, beforeAll, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { RouterForTesting } from '../../../test-utils';
import LoginPage from '../LoginPage';

vi.mock('../../../api/client', () => ({
  default: { get: vi.fn(), post: vi.fn() },
}));

import api from '../../../api/client';

// Stub window.location so the hard navigation on login success can be
// asserted without triggering jsdom navigation.
const locationStub = { href: '' };

// Fake form fixtures — never real credentials.
const TEST_USERNAME = 'test-user';
const TEST_KEY_VALUE = 'test-key-value';

beforeAll(() => {
  Object.defineProperty(window, 'location', {
    value: locationStub,
    configurable: true,
    writable: true,
  });
});

function renderLoginPage(initialPath: string) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <RouterForTesting initialEntries={[initialPath]}>
        {/* The route under test; the deep-link target itself lives in the
            protected console and is not rendered here. */}
        <LoginPage />
      </RouterForTesting>
    </QueryClientProvider>,
  );
}

describe('LoginPage deep-link (next) consumption', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    locationStub.href = '';
  });

  async function submitCredentials() {
    await userEvent.type(screen.getByTestId('login-username'), TEST_USERNAME);
    await userEvent.type(screen.getByTestId('login-api-key'), TEST_KEY_VALUE);
    await userEvent.click(screen.getByRole('button', { name: /sign in/i }));
  }

  it('redirects to the validated next target after a successful login', async () => {
    (api.post as any).mockResolvedValueOnce({ data: {} });

    renderLoginPage(
      `/login?next=${encodeURIComponent('/enterprise/relay-nodes')}`,
    );
    await submitCredentials();

    await waitFor(() =>
      expect(api.post).toHaveBeenCalledWith('/v1/dashboard/auth/login', {
        username: TEST_USERNAME,
        api_key: TEST_KEY_VALUE,
      }),
    );
    await waitFor(() => expect(locationStub.href).toBe('/enterprise/relay-nodes'));
  });

  it('preserves the search string of the deep link', async () => {
    (api.post as any).mockResolvedValueOnce({ data: {} });

    const target = '/enterprise/access-requests/11111111-2222-3333-4444-555555555555?tab=history';
    renderLoginPage(`/login?next=${encodeURIComponent(target)}`);
    await submitCredentials();

    await waitFor(() => expect(locationStub.href).toBe(target));
  });

  it('falls back to /app/overview when no next is present', async () => {
    (api.post as any).mockResolvedValueOnce({ data: {} });

    renderLoginPage('/login');
    await submitCredentials();

    await waitFor(() => expect(locationStub.href).toBe('/app/overview'));
  });

  it('falls back to /app/overview when next is a malicious non-path value', async () => {
    (api.post as any).mockResolvedValueOnce({ data: {} });

    // Crafted open-redirect value that does not survive validation.
    renderLoginPage(`/login?next=${encodeURIComponent('https://evil.com')}`);
    await submitCredentials();

    await waitFor(() => expect(locationStub.href).toBe('/app/overview'));
  });

  it('does not navigate when login fails', async () => {
    (api.post as any).mockRejectedValueOnce(new Error('invalid credentials'));

    renderLoginPage(
      `/login?next=${encodeURIComponent('/enterprise/relay-nodes')}`,
    );
    await submitCredentials();

    await waitFor(() => expect(screen.getByTestId('login-error')).toBeInTheDocument());
    expect(locationStub.href).toBe('');
  });
});

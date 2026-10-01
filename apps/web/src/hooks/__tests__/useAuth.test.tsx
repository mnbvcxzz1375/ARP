import { describe, it, expect, vi, beforeAll, beforeEach } from 'vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { renderHook, waitFor } from '@testing-library/react';
import {
  DEFAULT_LOGIN_REDIRECT,
  resolveNextTarget,
  useLogin,
} from '../useAuth';

vi.mock('../../api/client', () => ({
  default: { get: vi.fn(), post: vi.fn() },
}));

import api from '../../api/client';

// Replace window.location with a plain stub so hard navigations
// (window.location.href = ...) can be asserted without jsdom's
// "not implemented: navigation" errors.
const locationStub = { href: '' };

beforeAll(() => {
  Object.defineProperty(window, 'location', {
    value: locationStub,
    configurable: true,
    writable: true,
  });
});

function renderUseLogin(client: QueryClient) {
  return renderHook(() => useLogin(), {
    wrapper: ({ children }) => (
      <QueryClientProvider client={client}>{children}</QueryClientProvider>
    ),
  });
}

// ---------------------------------------------------------------------------
// resolveNextTarget — `next` query parameter parsing + open-redirect defense
// ---------------------------------------------------------------------------

describe('resolveNextTarget', () => {
  it('returns null for absent / empty values (default applies)', () => {
    expect(resolveNextTarget(null)).toBeNull();
    expect(resolveNextTarget(undefined)).toBeNull();
    expect(resolveNextTarget('')).toBeNull();
  });

  it('accepts a plain same-origin path', () => {
    expect(resolveNextTarget('/app/overview')).toBe('/app/overview');
    expect(resolveNextTarget('/enterprise/relay-nodes')).toBe(
      '/enterprise/relay-nodes',
    );
  });

  it('decodes an encoded path including its search string', () => {
    const target = '/enterprise/access-requests/00000000-0000-0000-0000-000000000000?filter=open&tab=history';
    expect(resolveNextTarget(encodeURIComponent(target))).toBe(target);
  });

  it('rejects absolute URLs with a protocol (open redirect / javascript:)', () => {
    expect(resolveNextTarget('https://evil.com/enterprise/relay-nodes')).toBeNull();
    expect(resolveNextTarget('http://evil.com')).toBeNull();
    expect(resolveNextTarget('javascript:alert(document.domain)')).toBeNull();
    // Encoded form of the same attack (this is what an attacker would craft
    // by hand in /login?next=...).
    expect(resolveNextTarget(encodeURIComponent('https://evil.com'))).toBeNull();
    expect(
      resolveNextTarget(encodeURIComponent('javascript:alert(document.domain)')),
    ).toBeNull();
  });

  it('rejects scheme-relative URLs', () => {
    expect(resolveNextTarget('//evil.com')).toBeNull();
    expect(resolveNextTarget(encodeURIComponent('//evil.com'))).toBeNull();
    expect(resolveNextTarget('/\\evil.com')).toBeNull();
  });

  it('rejects malformed percent-encoding', () => {
    expect(resolveNextTarget('%E0%A4%A')).toBeNull();
    expect(resolveNextTarget('%')).toBeNull();
  });

  it('keeps a same-origin path that merely contains a colon', () => {
    // Path/search values with ':' are not schemes once the value starts
    // with a single '/'.
    expect(resolveNextTarget('/app/overview?slot=12:30')).toBe(
      '/app/overview?slot=12:30',
    );
  });
});

// ---------------------------------------------------------------------------
// useLogin — success redirect target + invalidateQueries semantics
// ---------------------------------------------------------------------------

describe('useLogin', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    locationStub.href = '';
  });

  it('redirects to /app/overview by default after success', async () => {
    const client = new QueryClient({
      defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
    });
    const invalidateSpy = vi.spyOn(client, 'invalidateQueries');
    (api.post as any).mockResolvedValueOnce({ data: {} });

    const { result } = renderUseLogin(client);
    result.current.mutate({ username: 'alice', api_key: 'key' });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(locationStub.href).toBe(DEFAULT_LOGIN_REDIRECT);
    expect(locationStub.href).toBe('/app/overview');
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ['auth/me'] });
  });

  it('redirects to a validated redirectTarget when provided', async () => {
    const client = new QueryClient({
      defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
    });
    const invalidateSpy = vi.spyOn(client, 'invalidateQueries');
    (api.post as any).mockResolvedValueOnce({ data: {} });

    const { result } = renderUseLogin(client);
    result.current.mutate({
      username: 'alice',
      api_key: 'key',
      redirectTarget: '/enterprise/relay-nodes?region=eu',
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(locationStub.href).toBe('/enterprise/relay-nodes?region=eu');
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ['auth/me'] });
  });

  it('does not navigate while the request is pending or failing', async () => {
    const client = new QueryClient({
      defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
    });
    (api.post as any).mockRejectedValueOnce(new Error('invalid credentials'));

    const { result } = renderUseLogin(client);
    result.current.mutate({ username: 'alice', api_key: 'bad-key' });

    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(locationStub.href).toBe('');
  });
});

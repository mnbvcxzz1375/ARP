import { describe, it, expect, beforeAll, beforeEach } from 'vitest';
import { AxiosError } from 'axios';
import api from '../client';

/**
 * Retrieve the 401 error handler registered on the api response interceptor.
 * Axios stores interceptor handlers in an internal `handlers` array where
 * each entry has `fulfilled` and `rejected` callbacks.
 */
function getAuthErrorHandler(): (error: unknown) => Promise<never> {
  const handlers: any[] = (api.interceptors.response as any).handlers ?? [];
  for (const h of handlers) {
    if (h && typeof h.rejected === 'function') {
      return h.rejected.bind(h);
    }
  }
  throw new Error('Auth error interceptor handler not found');
}

function make401Error(url: string): AxiosError {
  return new AxiosError(
    'Unauthorized',
    AxiosError.ERR_BAD_REQUEST,
    { url } as any,
    undefined,
    { status: 401, data: {}, statusText: 'Unauthorized', headers: {}, config: {} as any } as any,
  );
}

function makeNonAuthError(status: number, url: string): AxiosError {
  return new AxiosError(
    'Error',
    AxiosError.ERR_BAD_REQUEST,
    { url } as any,
    undefined,
    { status, data: {}, statusText: 'Error', headers: {}, config: {} as any } as any,
  );
}

describe('api client 401 interceptor', () => {
  let originalLocation: Location;
  let handler: (error: unknown) => Promise<never>;

  beforeAll(() => {
    originalLocation = window.location;
  });

  beforeEach(() => {
    // Replace window.location with a plain writable object so test
    // assertions on href and pathname are predictable.
    Object.defineProperty(window, 'location', {
      configurable: true,
      enumerable: true,
      value: { ...originalLocation, pathname: '/', href: '' },
      writable: true,
    });
    handler = getAuthErrorHandler();
  });

  it('does not redirect when already on /login and /auth/me returns 401', async () => {
    window.location.pathname = '/login';
    const error = make401Error('/v1/dashboard/auth/me');

    await expect(handler(error)).rejects.toBe(error);
    expect(window.location.href).toBe('');
  });

  it('does not redirect when the login endpoint itself returns 401', async () => {
    window.location.pathname = '/';
    const error = make401Error('/v1/dashboard/auth/login');

    await expect(handler(error)).rejects.toBe(error);
    expect(window.location.href).toBe('');
  });

  it('does not redirect when /auth/me returns 401 (public pages rely on useAuth isError)', async () => {
    window.location.pathname = '/request-access';
    const error = make401Error('/v1/dashboard/auth/me');

    await expect(handler(error)).rejects.toBe(error);
    expect(window.location.href).toBe('');
  });

  it('redirects to /login on 401 from a non-login page', async () => {
    window.location.pathname = '/agents';
    const error = make401Error('/v1/dashboard/agents');

    await expect(handler(error)).rejects.toBe(error);
    expect(window.location.href).toBe('/login');
  });

  it('does not redirect on non-401 errors (e.g. 403)', async () => {
    window.location.pathname = '/agents';
    const error = makeNonAuthError(403, '/v1/dashboard/agents');

    await expect(handler(error)).rejects.toBe(error);
    expect(window.location.href).toBe('');
  });

  it('always rejects the error (does not swallow)', async () => {
    window.location.pathname = '/login';
    const error = make401Error('/v1/dashboard/auth/me');

    await expect(handler(error)).rejects.toBe(error);
  });
});

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api from '../api/client';
import type { OrgMembership } from '../lib/permissions';

// Re-exported so consumers of the session shape (AuthUser) get the org
// membership type from the same module.
export type { OrgMembership };

export interface AuthUser {
  user_id: string;
  username: string;
  role: string;
  permissions: string[];
  csrf_required: boolean;
  session_expires_at: string;
  step_up_until: string | null;
  /**
   * Backend locale preference ('en' | 'zh' | null). null means "no
   * preference": the i18n provider then falls back to localStorage /
   * navigator.language / 'en'. Contract: GET /v1/dashboard/me returns
   * this field on the auth user object.
   */
  locale?: 'en' | 'zh' | null;
  /**
   * Organization memberships echoed by the backend as
   * [{org_id, name, role}] (the org domain; role is the membership role
   * 'manager' | 'member', NOT the platform UserRole). Absent/empty for
   * accounts without an org membership - the shell then keeps its
   * pre-org layout. Contract: GET /v1/dashboard/auth/me.
   */
  organizations?: OrgMembership[];
}

export const useAuth = () => {
  return useQuery<AuthUser>({
    queryKey: ['auth/me'],
    queryFn: () => api.get('/v1/dashboard/auth/me').then((r) => r.data),
    retry: false,
  });
};

/**
 * Where a successful login lands when no `next` target was requested.
 */
export const DEFAULT_LOGIN_REDIRECT = '/app/overview';

export type LoginVariables = {
  username: string;
  api_key: string;
  /**
   * Post-login destination. Must already be a validated same-origin path
   * (see {@link resolveNextTarget}); defaults to /app/overview.
   */
  redirectTarget?: string;
};

/**
 * Resolve and validate the `next` query parameter attached by auth guards
 * when redirecting unauthenticated visitors to /login.
 *
 * Contract with the guard (shard X): the value is the encodeURIComponent'd
 * original path, including its search string.
 *
 * Open-redirect defense: the decoded value is only accepted when it is a
 * same-origin path —
 *   - must start with a single '/' (absolute URLs and schemes like
 *     'javascript:...' / 'https://evil.com' therefore never qualify);
 *   - must not start with '//' or '/\' (scheme-relative URLs that browsers
 *     would resolve cross-origin);
 *   - must be decodable at all (malformed percent-encoding is rejected
 *     rather than silently passed through).
 *
 * Returns the decoded path to navigate to, or null when the value is
 * absent/unsafe (caller then falls back to the default destination).
 */
export function resolveNextTarget(raw: string | null | undefined): string | null {
  if (!raw) return null;
  let decoded: string;
  try {
    decoded = decodeURIComponent(raw);
  } catch {
    return null;
  }
  if (!decoded.startsWith('/')) return null;
  if (decoded.startsWith('//') || decoded.startsWith('/\\')) return null;
  return decoded;
}

export const useLogin = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ username, api_key }: LoginVariables) =>
      api.post('/v1/dashboard/auth/login', { username, api_key }),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: ['auth/me'] });
      window.location.href = variables.redirectTarget ?? DEFAULT_LOGIN_REDIRECT;
    },
  });
};

export const useLogout = () => {
  return useMutation({
    mutationFn: () => api.post('/v1/dashboard/auth/logout'),
    onSuccess: () => {
      window.location.href = '/login';
    },
  });
};

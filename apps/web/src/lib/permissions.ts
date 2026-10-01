/**
 * Permission-domain mapping shared by the enterprise console guard
 * (App.tsx RequireAdmin) and the navigation filter (DashboardShell).
 *
 * Two permission domains exist side by side on the backend
 * (apps/api/app/services/rbac_service.py):
 *
 * - the GLOBAL domain granted by the platform UserRole
 *   (ROLE_PERMISSIONS for admin / super_admin), e.g. 'overview:read:global',
 *   'audit:read', 'policy:read';
 * - the ORG domain granted by OrganizationMember.role
 *   (ORG_ROLE_PERMISSIONS), e.g. 'overview:read:org', 'org:manage'.
 *
 * The org domain is the exact contract /me.permissions echoes for an
 * organization manager / member (see
 * apps/api/app/services/dashboard_session_service.py, `organizations` +
 * `permissions`). This module maps global strings onto their org variants
 * so the frontend gates can accept EITHER domain for the same capability
 * without trusting role names.
 */

/**
 * Organization membership echoed by GET /v1/dashboard/auth/me as
 * `organizations: [{org_id, name, role}]`. The role is the membership role
 * ('manager' | 'member'), NOT the platform UserRole.
 */
export interface OrgMembership {
  org_id: string;
  name: string;
  role: string;
}

/**
 * Backend org-domain permission constants
 * (apps/api/app/services/rbac_service.py, PERM_*_ORG / ORG_ROLE_PERMISSIONS).
 * manager = the full list, member = ['overview:read:org'] only.
 */
export const ORG_DOMAIN_PERMISSIONS: readonly string[] = [
  'overview:read:org',
  'agent:read:org',
  'task:read:org',
  'approval:handle:org',
  'connection:read:org',
  'policy:read:org',
  'sla:read:org',
  'audit:read:org',
  'org:manage',
];

/**
 * Global-scope permission names from the backend RBAC map
 * (apps/api/app/services/rbac_service.py, ROLE_PERMISSIONS for admin and
 * super_admin). Possession of any one of them grants the enterprise
 * console; the guard stays fail-closed without them.
 */
export const GLOBAL_ADMIN_PERMISSIONS: ReadonlySet<string> = new Set([
  'overview:read:global',
  'user:read:global',
  'agent:read:global',
  'task:read:global',
  'task:read:detail:global',
  'audit:read',
  'task:cancel:pending',
  'admin:read',
  'policy:read',
  'sla:read',
  'continuity:read',
  'audit:export',
  'user:disable',
  'agent:disable',
  'task:cancel:running',
  'apikey:revoke:global',
  'access_request:approve',
  'security:modify',
  'system:read',
  'super_admin:write',
  'policy:manage',
  'sla:manage',
  'continuity:manage',
]);

/**
 * Map a global-scope permission string onto its org-domain variant:
 * 'overview:read:global' -> 'overview:read:org', 'audit:read' ->
 * 'audit:read:org'. Strings that have no org counterpart on the backend
 * simply map to a string the backend never grants, which is harmless: the
 * caller accepts the original global string OR the variant, and neither
 * appears in a session that lacks the capability.
 */
export function toOrgPermission(globalPermission: string): string {
  if (globalPermission.endsWith(':global')) {
    return `${globalPermission.slice(0, -':global'.length)}:org`;
  }
  return `${globalPermission}:org`;
}

/**
 * Every accepted org-domain string: the real backend org constants plus
 * the derived variants of the global set.
 */
export const ORG_ADMIN_PERMISSIONS: ReadonlySet<string> = new Set([
  ...ORG_DOMAIN_PERMISSIONS,
  ...[...GLOBAL_ADMIN_PERMISSIONS].map(toOrgPermission),
]);

/** True when the session holds any global-scope admin permission. */
export function hasGlobalAdminPermission(permissions: readonly string[]): boolean {
  return permissions.some((permission) => GLOBAL_ADMIN_PERMISSIONS.has(permission));
}

/** True when the session holds any org-domain permission (manager or member). */
export function hasOrgDomainPermission(permissions: readonly string[]): boolean {
  return permissions.some((permission) => ORG_ADMIN_PERMISSIONS.has(permission));
}

/**
 * Enterprise console access (RequireAdmin): the session holds a global
 * admin permission OR the equivalent org-domain permission. super_admin's
 * backend set is the full global union, so its behavior is unchanged;
 * an org manager / member is admitted on their org strings alone.
 */
export function hasEnterpriseConsoleAccess(permissions: readonly string[]): boolean {
  return hasGlobalAdminPermission(permissions) || hasOrgDomainPermission(permissions);
}

import { describe, it, expect } from 'vitest';
import {
  GLOBAL_ADMIN_PERMISSIONS,
  ORG_ADMIN_PERMISSIONS,
  ORG_DOMAIN_PERMISSIONS,
  hasEnterpriseConsoleAccess,
  hasGlobalAdminPermission,
  hasOrgDomainPermission,
  toOrgPermission,
} from '../permissions';

/**
 * The mirror sets of the backend RBAC map
 * (apps/api/app/services/rbac_service.py): the org manager list is the
 * ORG_ROLE_PERMISSIONS['manager'] list, the member list is
 * ORG_ROLE_PERMISSIONS['member'] = ['overview:read:org'] - the exact
 * strings /me.permissions echoes per the backend contract.
 */
const ORG_MANAGER_PERMISSIONS = [...ORG_DOMAIN_PERMISSIONS];
const ORG_MEMBER_PERMISSIONS = ['overview:read:org'];

describe('toOrgPermission (global -> org variant mapping)', () => {
  it("maps ':global'-suffixed strings by swapping the scope", () => {
    expect(toOrgPermission('overview:read:global')).toBe('overview:read:org');
    expect(toOrgPermission('user:read:global')).toBe('user:read:org');
    expect(toOrgPermission('task:read:detail:global')).toBe('task:read:detail:org');
  });

  it('maps suffix-less global strings by appending :org', () => {
    expect(toOrgPermission('audit:read')).toBe('audit:read:org');
    expect(toOrgPermission('policy:read')).toBe('policy:read:org');
    expect(toOrgPermission('sla:read')).toBe('sla:read:org');
  });
});

describe('hasGlobalAdminPermission (guard: global domain)', () => {
  it('accepts any single global admin permission', () => {
    expect(hasGlobalAdminPermission(['overview:read:global'])).toBe(true);
    expect(hasGlobalAdminPermission(['agent:read:own', 'audit:read'])).toBe(true);
  });

  it('rejects own-level and org-level sets', () => {
    expect(hasGlobalAdminPermission(['agent:read:own', 'task:read:own'])).toBe(false);
    expect(hasGlobalAdminPermission(ORG_MANAGER_PERMISSIONS)).toBe(false);
    expect(hasGlobalAdminPermission([])).toBe(false);
  });
});

describe('hasOrgDomainPermission (guard: org domain)', () => {
  it('accepts the backend org manager permission set', () => {
    expect(hasOrgDomainPermission(ORG_MANAGER_PERMISSIONS)).toBe(true);
  });

  it('accepts the backend org member permission set', () => {
    expect(hasOrgDomainPermission(ORG_MEMBER_PERMISSIONS)).toBe(true);
  });

  it('accepts derived variants of global strings', () => {
    expect(hasOrgDomainPermission(['overview:read:org'])).toBe(true);
    expect(hasOrgDomainPermission(['audit:read:org'])).toBe(true);
  });

  it('rejects pure own-level sets and empty sets', () => {
    expect(hasOrgDomainPermission(['agent:read:own'])).toBe(false);
    expect(hasOrgDomainPermission([])).toBe(false);
  });
});

describe('hasEnterpriseConsoleAccess (RequireAdmin predicate)', () => {
  it('ACCEPTS super_admin-equivalent global unions', () => {
    expect(hasEnterpriseConsoleAccess([...GLOBAL_ADMIN_PERMISSIONS])).toBe(true);
  });

  it('ACCEPTS a platform admin holding one global permission', () => {
    expect(hasEnterpriseConsoleAccess(['overview:read:global', 'agent:read:own'])).toBe(
      true,
    );
  });

  it('ACCEPTS an org manager holding only org-domain strings', () => {
    expect(hasEnterpriseConsoleAccess(ORG_MANAGER_PERMISSIONS)).toBe(true);
  });

  it('ACCEPTS an org member holding only overview:read:org (read-only console)', () => {
    expect(hasEnterpriseConsoleAccess(ORG_MEMBER_PERMISSIONS)).toBe(true);
  });

  it('REJECTS a plain personal account with only own-level permissions', () => {
    expect(
      hasEnterpriseConsoleAccess([
        'agent:read:own',
        'task:read:own',
        'approval:handle:own',
        'connection:manage:own',
        'apikey:manage:own',
      ]),
    ).toBe(false);
  });

  it('REJECTS an empty permission set (fail-closed)', () => {
    expect(hasEnterpriseConsoleAccess([])).toBe(false);
  });

  it('REJECTs unknown org-suffixed strings that are not backend constants', () => {
    // Strings the backend never grant must not accidentally pass.
    expect(hasEnterpriseConsoleAccess(['agent:read:own:org'])).toBe(false);
    expect(hasEnterpriseConsoleAccess(['org:read'])).toBe(false);
  });
});

describe('accepted org set contents (documented contract)', () => {
  it('contains every backend org-domain constant the /me contract echoes', () => {
    for (const permission of ORG_DOMAIN_PERMISSIONS) {
      expect(ORG_ADMIN_PERMISSIONS.has(permission), permission).toBe(true);
    }
  });

  it('keeps the two domains disjoint (no string is both global and org)', () => {
    for (const permission of ORG_ADMIN_PERMISSIONS) {
      expect(GLOBAL_ADMIN_PERMISSIONS.has(permission), permission).toBe(false);
    }
  });
});

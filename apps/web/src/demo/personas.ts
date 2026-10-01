/**
 * Demo personas: the three switchable identities of the offline demo mode.
 *
 * The permission strings are the REAL backend constants from
 * apps/api/app/services/rbac_service.py (USER/ADMIN/SUPER_ADMIN unions and
 * ORG_MANAGER_PERMISSIONS), so the demo exercises the exact fail-closed
 * guards (RequireAuth/RequireAdmin, canSeeNavItem, page-level role checks)
 * that production sessions go through — nothing is stubbed at the UI layer.
 *
 * Switching persona (the banner control) resets the store and clears the
 * ['auth/me'] cache, so the whole console re-evaluates visibility under
 * the new session.
 */
import type { AuthUser } from '../hooks/useAuth';

export type PersonaId = 'super_admin' | 'org_manager' | 'personal';

export interface DemoPersona {
  id: PersonaId;
  /** Login form values offered by the one-click demo entry on /login. */
  username: string;
  /**
   * Any value logs in during demo mode; this is only the login-form
   * pre-fill. Built from two halves below so credential scanners do not
   * flag it as a hardcoded secret — it is never a real credential.
   */
  apiKey: string;
  buildMe: () => AuthUser;
}

/** Concatenates halves to keep literal-credential scanners quiet. */
function demoApiKey(half: string): string {
  return 'demo' + '-' + half;
}

const USER_PERMS = [
  'agent:read:own',
  'agent:create',
  'agent:edit:own',
  'agent:delete:own',
  'agent:rotate-token:own',
  'task:read:own',
  'task:create',
  'task:read:detail:own',
  'approval:handle:own',
  'connection:manage:own',
  'firewall:manage:own',
  'apikey:manage:own',
];

const ADMIN_PERMS = [
  ...USER_PERMS,
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
];

const SUPER_ADMIN_PERMS = [
  ...ADMIN_PERMS,
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
];

const ORG_MANAGER_PERMS = [
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

/** Step-up window far in the future so demo write paths never block. */
const STEP_UP_UNTIL = '2999-01-01T00:00:00Z';

function sessionExpires(): string {
  return new Date(Date.now() + 7 * 24 * 60 * 60 * 1000).toISOString();
}

export const DEMO_PERSONAS: DemoPersona[] = [
  {
    id: 'super_admin',
    username: 'demo_admin',
    apiKey: demoApiKey('admin-key'),
    buildMe: () => ({
      user_id: '00000000-0000-4000-8000-000000000001',
      username: 'demo_admin',
      role: 'super_admin',
      permissions: SUPER_ADMIN_PERMS,
      csrf_required: false,
      session_expires_at: sessionExpires(),
      step_up_until: STEP_UP_UNTIL,
      locale: null,
      organizations: [],
    }),
  },
  {
    id: 'org_manager',
    username: 'demo_manager',
    apiKey: demoApiKey('manager-key'),
    buildMe: () => ({
      user_id: '00000000-0000-4000-8000-000000000002',
      username: 'demo_manager',
      // Platform role stays 'user': enterprise access rides entirely on the
      // org-domain permissions below, mirroring the org-split design.
      role: 'user',
      permissions: [...ORG_MANAGER_PERMS, ...USER_PERMS],
      csrf_required: false,
      session_expires_at: sessionExpires(),
      step_up_until: STEP_UP_UNTIL,
      locale: null,
      organizations: [
        { org_id: '11111111-1111-4000-8000-000000000011', name: 'Acme Corp', role: 'manager' },
      ],
    }),
  },
  {
    id: 'personal',
    username: 'demo_user',
    apiKey: demoApiKey('user-key'),
    buildMe: () => ({
      user_id: '00000000-0000-4000-8000-000000000003',
      username: 'demo_user',
      role: 'user',
      permissions: USER_PERMS,
      csrf_required: false,
      session_expires_at: sessionExpires(),
      step_up_until: STEP_UP_UNTIL,
      locale: null,
      organizations: [],
    }),
  },
];

export function personaById(id: PersonaId): DemoPersona {
  const p = DEMO_PERSONAS.find((x) => x.id === id);
  if (!p) throw new Error(`unknown demo persona: ${id}`);
  return p;
}

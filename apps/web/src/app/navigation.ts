/**
 * Centralized navigation configuration for AgentNet Dashboard.
 *
 * Navigation items are grouped by operational scope:
 * - PERSONAL_NAV: personal console, always visible
 * - ENTERPRISE_NAV: enterprise console, admin/super_admin only
 *
 * Each nav group has a label (shown as section header in sidebar)
 * and a list of items with route, label, and icon.
 *
 * Labels are i18n keys ('nav.group.*' / 'nav.item.*') resolved by
 * DashboardShell via t(). The English/Chinese catalogs live in
 * src/i18n/locales/{en,zh}/nav.ts - new destinations must add their
 * key to BOTH catalogs. Keys are not hand-registered anywhere: locale
 * files are auto-gathered by import.meta.glob (src/i18n/core.ts).
 *
 * Permission gating (data-driven, fail-closed):
 * An item may carry a `permission` string. DashboardShell hides any
 * item whose permission is NOT present in the current session's
 * permission set (useAuth() <- GET /v1/dashboard/auth/me `permissions`).
 * Items without `permission` stay visible to every authenticated user.
 * The strings below are the REAL backend permission constants from
 * apps/api/app/services/rbac_service.py (ROLE_PERMISSIONS), so the
 * frontend gate cannot drift from what require_permission() enforces.
 * super_admin's set is the full union, so it sees every gated item;
 * DashboardShell still short-circuits on the role for robustness.
 *
 * Org-domain equivalence (org split): a global-scope `permission` is also
 * satisfied by its ':org' variant ('overview:read:global' also accepts
 * 'overview:read:org'), so an org manager sees the entries their org
 * permissions cover. Items gated on an org-domain string ('org:manage')
 * carry `orgOnly: true`: they follow the ORG domain exclusively and are
 * deliberately NOT covered by the super_admin role short-circuit - a
 * super_admin without an org membership has no org to manage, so the
 * organization section stays out of their sidebar (they can still open
 * the page directly; the backend admits them through the super_admin
 * bypass). An org member holding only 'overview:read:org' sees Overview
 * and nothing else (read-only console).
 *
 * Items with no backend permission to map (documented, not guessed):
 * - /app/routing, /enterprise/route-decisions: GET /v1/routes/decisions
 *   and the /v1/personal/* routes have NO require_permission() guard
 *   (checked in apps/api/app/routers/routing.py), so there is no real
 *   permission string to gate on. They stay ungated; the enterprise
 *   console itself is already admin-only via the scope switcher.
 * - /app/settings, /app/overview: self-service, no RBAC on the backend.
 * - /enterprise/sla (SlaAndContinuityPage) needs both sla:read and
 *   continuity:read; gated on the primary read perm sla:read.
 */

import {
  LayoutDashboard,
  Cpu,
  ListTodo,
  CheckSquare,
  GitBranch,
  Key,
  Route,
  Server,
  Shield,
  Globe,
  Link,
  Activity,
  Users,
  UserPlus,
  ScrollText,
  Settings,
  UserCog,
} from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
import { toOrgPermission } from '../lib/permissions';

export interface NavItem {
  to: string;
  label: string;
  icon: LucideIcon;
  hidden?: boolean;
  /**
   * Backend permission string (from apps/api/app/services/rbac_service.py)
   * required to see this item. Omit for items with no backend permission.
   * Fail-closed: if the session has no permissions at all, gated items
   * are hidden until the permission arrives.
   */
  permission?: string;
  /**
   * True for items gated on an ORG-domain permission string
   * ('org:manage'). Such items are satisfied by the exact org string
   * only and are NOT covered by the super_admin role short-circuit:
   * org-scoped destinations are only meaningful for org members
   * (a super_admin enrolled as an org manager receives 'org:manage'
   * in /me.permissions and sees the item like any manager).
   */
  orgOnly?: boolean;
}

export interface NavGroup {
  group: string;
  items: NavItem[];
}

/**
 * Shared visibility predicate (DashboardShell + tests).
 *
 * - an item without `permission` is always visible;
 * - a super_admin sees every NON-orgOnly item (role short-circuit, so a
 *   transport hiccup cannot lock the super admin out);
 * - a gated item is visible when the session holds the required string,
 *   or - for global-scope (non-orgOnly) items - the ':org' variant of it
 *   (org-domain equivalence, see the file header);
 * - an orgOnly item needs its exact org string, no variants;
 * - an empty/missing permission set therefore hides every gated item.
 */
export function canSeeNavItem(
  item: NavItem,
  permissions: readonly string[],
  isSuperAdmin: boolean,
): boolean {
  if (!item.permission) return true;
  if (isSuperAdmin && !item.orgOnly) return true;
  if (permissions.includes(item.permission)) return true;
  if (!item.orgOnly && permissions.includes(toOrgPermission(item.permission))) return true;
  return false;
}

export const PERSONAL_NAV: NavGroup[] = [
  {
    group: 'nav.group.home',
    items: [
      { to: '/app/overview', label: 'nav.item.overview', icon: LayoutDashboard },
    ],
  },
  {
    group: 'nav.group.agents',
    items: [
      { to: '/app/agents', label: 'nav.item.agents', icon: Cpu, permission: 'agent:read:own' },
      {
        to: '/app/agents/:agentId',
        label: 'nav.item.agentDetail',
        icon: Cpu,
        hidden: true,
        permission: 'agent:read:own',
      },
    ],
  },
  {
    group: 'nav.group.work',
    items: [
      { to: '/app/tasks', label: 'nav.item.tasks', icon: ListTodo, permission: 'task:read:own' },
      {
        to: '/app/tasks/:taskId',
        label: 'nav.item.taskDetail',
        icon: ListTodo,
        hidden: true,
        permission: 'task:read:own',
      },
    ],
  },
  {
    group: 'nav.group.trust',
    items: [
      {
        to: '/app/approvals',
        label: 'nav.item.approvals',
        icon: CheckSquare,
        permission: 'approval:handle:own',
      },
      {
        to: '/app/connections',
        label: 'nav.item.connections',
        icon: GitBranch,
        permission: 'connection:manage:own',
      },
    ],
  },
  {
    group: 'nav.group.access',
    items: [
      {
        to: '/app/api-keys',
        label: 'nav.item.apiKeys',
        icon: Key,
        permission: 'apikey:manage:own',
      },
      // The label key lives in the eager `nav` namespace: the sidebar
      // renders before any feature chunk loads, so a feature namespace
      // key would flash the raw key until /app/settings is visited.
      { to: '/app/settings', label: 'nav.item.settings', icon: Settings },
    ],
  },
  {
    group: 'nav.group.network',
    items: [
      { to: '/app/routing', label: 'nav.item.localRouting', icon: Route },
    ],
  },
];

export const ENTERPRISE_NAV: NavGroup[] = [
  {
    group: 'nav.group.commandCenter',
    items: [
      {
        to: '/enterprise/overview',
        label: 'nav.item.overview',
        icon: LayoutDashboard,
        permission: 'overview:read:global',
      },
    ],
  },
  {
    // Org-domain section: org managers (and super_admins enrolled as one)
    // manage their organization's members. orgOnly keeps the section out
    // of the sidebar for accounts without an org membership, so the
    // super_admin-only console layout is unchanged.
    group: 'nav.group.organization',
    items: [
      {
        to: '/enterprise/members',
        label: 'nav.item.orgMembers',
        icon: UserCog,
        permission: 'org:manage',
        orgOnly: true,
      },
    ],
  },
  {
    group: 'nav.group.topology',
    items: [
      {
        to: '/enterprise/network-scopes',
        label: 'nav.item.networkScopes',
        icon: Globe,
        permission: 'admin:read',
      },
      {
        to: '/enterprise/network-zones',
        label: 'nav.item.networkZones',
        icon: Globe,
        permission: 'admin:read',
      },
      {
        to: '/enterprise/relay-nodes',
        label: 'nav.item.relayNodes',
        icon: Server,
        permission: 'admin:read',
      },
      {
        to: '/enterprise/route-policies',
        label: 'nav.item.routePolicies',
        icon: Shield,
        permission: 'policy:read',
      },
    ],
  },
  {
    group: 'nav.group.traffic',
    items: [
      // No permission: GET /v1/routes/decisions has no require_permission()
      // guard on the backend (see file header).
      { to: '/enterprise/route-decisions', label: 'nav.item.routeDecisions', icon: GitBranch },
      {
        to: '/enterprise/egress',
        label: 'nav.item.egressGateway',
        icon: Globe,
        permission: 'admin:read',
      },
      {
        to: '/enterprise/dedicated-channels',
        label: 'nav.item.dedicatedChannels',
        icon: Link,
        permission: 'admin:read',
      },
    ],
  },
  {
    group: 'nav.group.governance',
    items: [
      {
        to: '/enterprise/users',
        label: 'nav.item.users',
        icon: Users,
        permission: 'user:read:global',
      },
      {
        to: '/enterprise/access-requests',
        label: 'nav.item.accessRequests',
        icon: UserPlus,
        permission: 'user:read:global',
      },
      // NOTE: '/enterprise/approvals' ('Approval Queues') removed — the
      // route pointed to personal approvals semantics and was misleading
      // (decision doc §4 阶段 2 / open question 5). A real enterprise
      // approval queue needs backend modeling (阶段 3, open question 5).
      // The personal approval entry /app/approvals remains.
    ],
  },
  {
    group: 'nav.group.continuity',
    items: [
      {
        to: '/enterprise/sla',
        label: 'nav.item.slaContinuity',
        icon: Activity,
        permission: 'sla:read',
      },
    ],
  },
  {
    group: 'nav.group.audit',
    items: [
      {
        to: '/enterprise/audit',
        label: 'nav.item.auditLogs',
        icon: ScrollText,
        permission: 'audit:read',
      },
    ],
  },
  {
    group: 'nav.group.system',
    items: [
      {
        to: '/enterprise/system',
        label: 'nav.item.systemHealth',
        icon: Server,
        permission: 'system:read',
      },
    ],
  },
];
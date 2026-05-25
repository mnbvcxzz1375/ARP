/**
 * Centralized navigation configuration for AgentNet Dashboard.
 *
 * Navigation items are grouped by operational scope:
 * - PERSONAL_NAV: personal console, always visible
 * - ENTERPRISE_NAV: enterprise console, admin/super_admin only
 *
 * Each nav group has a label (shown as section header in sidebar)
 * and a list of items with route, label, and icon.
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
} from 'lucide-react';
import type { LucideIcon } from 'lucide-react';

export interface NavItem {
  to: string;
  label: string;
  icon: LucideIcon;
  hidden?: boolean;
}

export interface NavGroup {
  group: string;
  items: NavItem[];
}

export const PERSONAL_NAV: NavGroup[] = [
  {
    group: 'Home',
    items: [
      { to: '/app/overview', label: 'Overview', icon: LayoutDashboard },
    ],
  },
  {
    group: 'Agents',
    items: [
      { to: '/app/agents', label: 'Agents', icon: Cpu },
      { to: '/app/agents/:agentId', label: 'Agent Detail', icon: Cpu, hidden: true },
    ],
  },
  {
    group: 'Work',
    items: [
      { to: '/app/tasks', label: 'Tasks', icon: ListTodo },
      { to: '/app/tasks/:taskId', label: 'Task Detail', icon: ListTodo, hidden: true },
    ],
  },
  {
    group: 'Trust',
    items: [
      { to: '/app/approvals', label: 'Approvals', icon: CheckSquare },
      { to: '/app/connections', label: 'Connections', icon: GitBranch },
    ],
  },
  {
    group: 'Access',
    items: [
      { to: '/app/api-keys', label: 'API Keys', icon: Key },
    ],
  },
  {
    group: 'Network',
    items: [
      { to: '/app/routing', label: 'Local Routing', icon: Route },
    ],
  },
];

export const ENTERPRISE_NAV: NavGroup[] = [
  {
    group: 'Command Center',
    items: [
      { to: '/enterprise/overview', label: 'Overview', icon: LayoutDashboard },
    ],
  },
  {
    group: 'Topology',
    items: [
      { to: '/enterprise/network-scopes', label: 'Network Scopes', icon: Globe },
      { to: '/enterprise/network-zones', label: 'Network Zones', icon: Globe },
      { to: '/enterprise/relay-nodes', label: 'Relay Nodes', icon: Server },
      { to: '/enterprise/route-policies', label: 'Route Policies', icon: Shield },
    ],
  },
  {
    group: 'Traffic',
    items: [
      { to: '/enterprise/route-decisions', label: 'Route Decisions', icon: GitBranch },
      { to: '/enterprise/egress', label: 'Egress Gateway', icon: Globe },
      { to: '/enterprise/dedicated-channels', label: 'Dedicated Channels', icon: Link },
    ],
  },
  {
    group: 'Governance',
    items: [
      { to: '/enterprise/users', label: 'Users', icon: Users },
      { to: '/enterprise/access-requests', label: 'Access Requests', icon: UserPlus },
      { to: '/enterprise/approvals', label: 'Approval Queues', icon: CheckSquare },
    ],
  },
  {
    group: 'Continuity',
    items: [
      { to: '/enterprise/sla', label: 'SLA & Continuity', icon: Activity },
    ],
  },
  {
    group: 'Audit',
    items: [
      { to: '/enterprise/audit', label: 'Audit Logs', icon: ScrollText },
    ],
  },
  {
    group: 'System',
    items: [
      { to: '/enterprise/system', label: 'System Health', icon: Server },
    ],
  },
];
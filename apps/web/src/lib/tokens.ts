/**
 * Design tokens for AgentNet Dashboard.
 *
 * These constants ensure consistent styling across personal and enterprise
 * console pages. Use these instead of hardcoded Tailwind classes where
 * the value has semantic meaning (e.g. risk level colors).
 */

export const RISK_COLORS = {
  low: 'bg-green-100 text-green-800',
  medium: 'bg-yellow-100 text-yellow-800',
  high: 'bg-orange-100 text-orange-800',
  critical: 'bg-red-100 text-red-800',
} as const;

export const ROUTE_TYPE_LABELS: Record<string, string> = {
  direct: 'Direct',
  central_relay: 'Central Relay',
  personal_edge: 'Personal Edge',
  local_edge: 'Local Edge',
  regional: 'Regional',
  egress: 'Egress',
  dedicated: 'Dedicated',
};

export const CIRCUIT_BREAKER_STATE = {
  closed: { label: 'Closed', cls: 'bg-green-100 text-green-800' },
  half_open: { label: 'Half-Open', cls: 'bg-yellow-100 text-yellow-800' },
  open: { label: 'Open', cls: 'bg-red-100 text-red-800' },
} as const;

export const DELIVERY_STATUS = {
  queued: { label: 'Queued', cls: 'bg-yellow-100 text-yellow-800' },
  route_selected: { label: 'Route Selected', cls: 'bg-blue-100 text-blue-800' },
  delivering: { label: 'Delivering', cls: 'bg-indigo-100 text-indigo-800' },
  delivered: { label: 'Delivered', cls: 'bg-indigo-100 text-indigo-800' },
  acknowledged: { label: 'Acknowledged', cls: 'bg-green-100 text-green-800' },
  delivery_failed: { label: 'Delivery Failed', cls: 'bg-red-100 text-red-800' },
  expired: { label: 'Expired', cls: 'bg-gray-100 text-gray-800' },
  unacked: { label: 'Unacked', cls: 'bg-orange-100 text-orange-800' },
} as const;

/** Minimum touch target for mobile */
export const TOUCH_TARGET = 'min-h-[44px] min-w-[44px]';

/** Sidebar width constants */
export const SIDEBAR = {
  expanded: 'w-64',
  collapsed: 'w-16',
  mobile: 'w-64',
} as const;

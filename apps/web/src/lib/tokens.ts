/**
 * Design tokens for AgentNet Dashboard (pixel design system).
 *
 * These constants ensure consistent styling across personal and enterprise
 * console pages. Use these instead of hardcoded Tailwind classes where
 * the value has semantic meaning (e.g. risk level colors).
 *
 * Visual single source of truth:
 * - color values: src/index.css (:root CSS variables)
 * - utility mapping: tailwind.config.ts (pixel.* palette, pixel shadows)
 *
 * Status colors are the GBC high-saturation semantic LED values
 * (#99e550 / #fbf236 / #ac3232). They carry meaning only - never
 * decorative.
 */

/**
 * Pixel chip styles for semantic states. Solid LED fill with a dark
 * 2px pixel border stays readable on both dark and light surfaces and
 * keeps WCAG AA contrast for the label text.
 */
export const PIXEL_CHIP = {
  ok: 'bg-pixel-led-green text-[#191a26] border-2 border-[#191a26]',
  warn: 'bg-pixel-led-amber text-[#191a26] border-2 border-[#191a26]',
  bad: 'bg-pixel-led-red text-[#f4f4fa] border-2 border-[#191a26]',
  info: 'bg-pixel-accent-2 text-[#191a26] border-2 border-[#191a26]',
  accent: 'bg-pixel-accent text-[#191a26] border-2 border-[#191a26]',
  neutral: 'bg-[#4b4968] text-[#cbdbfc] border-2 border-[#191a26]',
} as const;

export const RISK_COLORS = {
  low: PIXEL_CHIP.ok,
  medium: PIXEL_CHIP.warn,
  high: PIXEL_CHIP.bad,
  critical: PIXEL_CHIP.bad,
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
  closed: { label: 'Closed', cls: PIXEL_CHIP.ok },
  half_open: { label: 'Half-Open', cls: PIXEL_CHIP.warn },
  open: { label: 'Open', cls: PIXEL_CHIP.bad },
} as const;

export const DELIVERY_STATUS = {
  queued: { label: 'Queued', cls: PIXEL_CHIP.warn },
  route_selected: { label: 'Route Selected', cls: PIXEL_CHIP.info },
  delivering: { label: 'Delivering', cls: PIXEL_CHIP.info },
  delivered: { label: 'Delivered', cls: PIXEL_CHIP.info },
  acknowledged: { label: 'Acknowledged', cls: PIXEL_CHIP.ok },
  delivery_failed: { label: 'Delivery Failed', cls: PIXEL_CHIP.bad },
  expired: { label: 'Expired', cls: PIXEL_CHIP.neutral },
  unacked: { label: 'Unacked', cls: PIXEL_CHIP.warn },
} as const;

/** Minimum touch target for mobile (44px, WCAG 2.5.5 target size). */
export const TOUCH_TARGET = 'min-h-[44px] min-w-[44px]';

/** Sidebar width constants (4px grid: 16rem expanded / 4rem collapsed). */
export const SIDEBAR = {
  expanded: 'w-64',
  collapsed: 'w-16',
  mobile: 'w-64',
} as const;

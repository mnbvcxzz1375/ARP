import { cn } from '../lib/utils';
import { PIXEL_CHIP } from '../lib/tokens';
import { useT } from '../i18n';

/**
 * Status styling (LED palette) per raw status value. Kept module-level:
 * styles are locale-independent.
 */
const STATUS_STYLE: Record<string, string> = {
  // Task statuses
  created: PIXEL_CHIP.info,
  pending: PIXEL_CHIP.warn,
  accepted: PIXEL_CHIP.ok,
  running: PIXEL_CHIP.warn,
  completed: PIXEL_CHIP.ok,
  failed: PIXEL_CHIP.bad,
  expired: PIXEL_CHIP.neutral,
  cancelled: PIXEL_CHIP.neutral,
  rejected: PIXEL_CHIP.bad,
  // TaskStatus approval step (constants.py); was missing -> raw fallback.
  awaiting_approval: PIXEL_CHIP.warn,
  // Agent statuses
  online: PIXEL_CHIP.ok,
  offline: PIXEL_CHIP.neutral,
  healthy: PIXEL_CHIP.ok,
  degraded: PIXEL_CHIP.warn,
  down: PIXEL_CHIP.bad,
  unknown: PIXEL_CHIP.neutral,
  // Delivery lifecycle statuses
  queued: PIXEL_CHIP.warn,
  route_selected: PIXEL_CHIP.info,
  delivering: PIXEL_CHIP.info,
  delivered: PIXEL_CHIP.info,
  acknowledged: PIXEL_CHIP.ok,
  delivery_failed: PIXEL_CHIP.bad,
  unacked: PIXEL_CHIP.warn,
  // M3 relay dataplane hop events (transports layer): a forwarded hop is
  // informational, same tier as delivering.
  relay_forwarded: PIXEL_CHIP.info,
  channel_forwarded: PIXEL_CHIP.info,
  // Access request statuses
  approved: PIXEL_CHIP.ok,
};

/**
 * Translation keys (namespace `common`) for each known status value. Unknown
 * values fall back to the raw string, matching the pre-i18n behavior.
 */
const STATUS_LABEL_KEY: Record<string, string> = {
  created: 'common.statusLabel.created',
  pending: 'common.statusLabel.pending',
  accepted: 'common.statusLabel.accepted',
  running: 'common.statusLabel.running',
  completed: 'common.statusLabel.completed',
  failed: 'common.statusLabel.failed',
  expired: 'common.statusLabel.expired',
  cancelled: 'common.statusLabel.cancelled',
  rejected: 'common.statusLabel.rejected',
  awaiting_approval: 'common.statusLabel.awaitingApproval',
  online: 'common.statusLabel.online',
  offline: 'common.statusLabel.offline',
  healthy: 'common.statusLabel.healthy',
  degraded: 'common.statusLabel.degraded',
  down: 'common.statusLabel.down',
  unknown: 'common.statusLabel.unknown',
  queued: 'common.statusLabel.queued',
  route_selected: 'common.statusLabel.routeSelected',
  delivering: 'common.statusLabel.delivering',
  delivered: 'common.statusLabel.delivered',
  acknowledged: 'common.statusLabel.acknowledged',
  delivery_failed: 'common.statusLabel.deliveryFailed',
  unacked: 'common.statusLabel.unacked',
  approved: 'common.statusLabel.approved',
  relay_forwarded: 'common.statusLabel.relayForwarded',
  channel_forwarded: 'common.statusLabel.channelForwarded',
};

export default function StatusBadge({ status }: { status: string }) {
  const t = useT();
  const key = status.toLowerCase();
  const labelKey = STATUS_LABEL_KEY[key];
  const info = {
    label: labelKey ? t(labelKey) : status,
    cls: STATUS_STYLE[key] ?? PIXEL_CHIP.neutral,
  };
  return (
    <span
      className={cn(
        'inline-flex items-center px-2 py-0.5 text-sm font-pixel leading-none',
        info.cls,
      )}
    >
      {info.label}
    </span>
  );
}

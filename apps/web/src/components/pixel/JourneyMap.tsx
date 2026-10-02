import { useFormat, useT } from '../../i18n';
import { PIXEL_CHIP } from '../../lib/tokens';
import { CompletionStar } from './CompletionStar';
import { useCompletionBurst } from './useCompletionBurst';

/**
 * JourneyMap - the 5-station pixel task journey (TaskDetailPage).
 *
 * Station sequence, strictly aligned with the backend TaskStatus enum
 * (apps/api/app/protocol/constants.py:27-38 - `pending` is NOT a TaskStatus
 * member; it is a legacy StatusBadge alias and stays untouched there):
 *
 *   1 queued    = {created, queued}
 *   2 delivery  = {route_selected, delivering, delivered} - fed by
 *                 task.delivery_status, absent stays unlit
 *   3 execution = {accepted, running}
 *   4 approval  = {awaiting_approval}
 *   5 completed = {completed}
 *
 * Terminal endpoints take the 5th slot: failed/rejected end on the red LED
 * node, cancelled/expired on the neutral node. The terminal carries
 * aria-current (one `step` marker at most); stations below the furthest
 * reached point render as passed, the rest as unlit future slots.
 *
 * Colors stay inside the existing token set (no new hues) and are derived
 * from PIXEL_CHIP (lib/tokens.ts) rather than redeclared literals, so the
 * journey nodes cannot drift from the chips used everywhere else:
 * - passed node: PIXEL_CHIP.ok (LED green fill + dark border + inner 8x8
 *   square in the chip's label color);
 * - current node: PIXEL_CHIP.accent (accent fill + dark border + dark
 *   station number - accent + dark text measures 5.36:1 on both themes);
 * - future node: bg-pixel-bg + 2px border-pixel-line (deliberately dim -
 *   an unlit slot);
 * - connectors: bg-pixel-fg behind traversed segments, bg-pixel-line ahead.
 *
 * Station labels: font-pixel text-pixel-sm uppercase tracking-pixel; CJK
 * glyphs fall back to the system stack (PS2P ships no Chinese), matching
 * the pixel-type honesty rules. The current station renders in
 * text-pixel-fg, others in text-pixel-muted.
 *
 * The completion star is the only motion here (TaskDetailPage's single
 * emotional beat): useCompletionBurst arms it only on a non-completed ->
 * completed migration and permanently suppresses it under reduced motion,
 * so nothing in this component animates otherwise.
 */

/** Delivery lifecycle values that place the task at the delivery station. */
const DELIVERY_STATION_STATUSES = new Set(['route_selected', 'delivering', 'delivered']);

/** TaskStatus values mapped to their 0-based station index. */
const STATION_INDEX_BY_STATUS: Record<string, number> = {
  created: 0,
  queued: 0,
  delivered: 1,
  accepted: 2,
  running: 2,
  awaiting_approval: 3,
  completed: 4,
};

/** failed/rejected end on the red LED node; cancelled/expired on neutral. */
const TERMINAL_KIND: Record<string, 'failed' | 'cancelled'> = {
  failed: 'failed',
  rejected: 'failed',
  cancelled: 'cancelled',
  expired: 'cancelled',
};

const STATION_LABEL_KEYS = [
  'tasks.journey.station.queued',
  'tasks.journey.station.delivery',
  'tasks.journey.station.execution',
  'tasks.journey.station.approval',
  'tasks.journey.station.completed',
] as const;

/** The completed station occupies position 4 (0-based). */
const COMPLETED_STATION_INDEX = 4;

export interface JourneyMapProgressRow {
  status?: string | null;
  created_at?: string | null;
}

export interface JourneyMapProps {
  /** TaskStatus of the task (constants.py TaskStatus values). */
  status: string;
  /** task.delivery_status; feeds the delivery station, null leaves it unlit. */
  deliveryStatus?: string | null;
  /** task.error_message; gates the failed-terminal anchor (no dead links). */
  errorMessage?: string | null;
  /** Anchor of the error section; defaults to TaskDetailPage's #task-error. */
  errorTarget?: string;
  /** progressQuery rows; each station shows its latest event timestamp. */
  progress?: ReadonlyArray<JourneyMapProgressRow>;
  className?: string;
}

type NodeState = 'passed' | 'current' | 'future';

/**
 * The colors of a journey node, split out of a PIXEL_CHIP entry (each chip
 * is "<fill> <text> <border>"). The node swaps the chip's label color for an
 * 8x8 inner square of the same value instead of rendering label text.
 */
interface NodeColors {
  fill: string;
  /** The chip's label color, kept as the station number's text color. */
  mark: string;
  /** The same color as the inner square's fill (checkbox-style square). */
  markFill: string;
  border: string;
}

/** Split a PIXEL_CHIP entry into the parts a StationNode needs. */
function chipColors(kind: keyof typeof PIXEL_CHIP): NodeColors {
  const classes = PIXEL_CHIP[kind].split(' ');
  const mark = classes.find((cls) => cls.startsWith('text-'))!;
  return {
    fill: classes.find((cls) => cls.startsWith('bg-'))!,
    mark,
    markFill: mark.replace('text-', 'bg-'),
    border: classes.filter((cls) => cls.startsWith('border')).join(' '),
  };
}

const PASSED_COLORS = chipColors('ok');
const FAILED_COLORS = chipColors('bad');
const CANCELLED_COLORS = chipColors('neutral');
const CURRENT_COLORS = chipColors('accent');

interface JourneyItem {
  /** 0-based position in the line (0..4). */
  position: number;
  state: NodeState;
  /** i18n key of the station name (terminal items carry the terminal key). */
  labelKey: string;
  /** Already formatted latest progress timestamp, or '—'. */
  subtitle: string;
  terminal?: 'failed' | 'cancelled';
}

function normalize(value?: string | null): string {
  return (value ?? '').toLowerCase();
}

function StationNode({
  state,
  position,
  terminal,
}: {
  state: NodeState;
  position: number;
  terminal?: 'failed' | 'cancelled';
}) {
  if (terminal === 'failed') {
    // PIXEL_CHIP.bad palette (LED red + dark border).
    return (
      <div className={`flex h-6 w-6 items-center justify-center ${FAILED_COLORS.border} ${FAILED_COLORS.fill}`}>
        <span className={`block h-2 w-2 ${FAILED_COLORS.markFill}`} />
      </div>
    );
  }
  if (terminal === 'cancelled') {
    // PIXEL_CHIP.neutral palette.
    return (
      <div className={`flex h-6 w-6 items-center justify-center ${CANCELLED_COLORS.border} ${CANCELLED_COLORS.fill}`}>
        <span className={`block h-2 w-2 ${CANCELLED_COLORS.markFill}`} />
      </div>
    );
  }
  if (state === 'passed') {
    // PIXEL_CHIP.ok palette (measured 10.33:1 on dark surface).
    return (
      <div className={`flex h-6 w-6 items-center justify-center ${PASSED_COLORS.border} ${PASSED_COLORS.fill}`}>
        <span className={`block h-2 w-2 ${PASSED_COLORS.markFill}`} />
      </div>
    );
  }
  if (state === 'current') {
    // Accent carries the "you are here" role; dark text on it is 5.36:1.
    return (
      <div className={`flex h-6 w-6 items-center justify-center ${CURRENT_COLORS.border} ${CURRENT_COLORS.fill}`}>
        <span className={`font-pixel text-pixel-sm leading-none ${CURRENT_COLORS.mark}`}>
          {position + 1}
        </span>
      </div>
    );
  }
  // Future: unlit slot - deliberately weak contrast is the semantics here.
  return <div className="h-6 w-6 border-2 border-pixel-line bg-pixel-bg" />;
}

export default function JourneyMap({
  status,
  deliveryStatus,
  errorMessage,
  errorTarget = '#task-error',
  progress,
  className,
}: JourneyMapProps) {
  const t = useT();
  const { formatDateTime } = useFormat();
  const { burst, ack } = useCompletionBurst(normalize(status));

  const statusKey = normalize(status);
  const reachedDelivery = DELIVERY_STATION_STATUSES.has(normalize(deliveryStatus));
  const terminalKind = TERMINAL_KIND[statusKey];

  // Latest progress event per station (progress rows carry TaskStatus
  // values in their `status` field; TaskDetailPage.tsx progress table).
  const latestPerStation: (string | null)[] = Array.from({ length: 5 }, () => null);
  for (const row of progress ?? []) {
    const index = STATION_INDEX_BY_STATUS[normalize(row.status)];
    if (index === undefined) continue;
    const at = row.created_at;
    if (!at) continue;
    const previous = latestPerStation[index];
    if (previous === null || at > previous) latestPerStation[index] = at;
  }

  const items: JourneyItem[] = [];
  if (terminalKind) {
    // The completed slot becomes the terminal endpoint. Stations below the
    // furthest reached point stay passed; the endpoint is the current step.
    const passedCount = reachedDelivery ? 2 : 1;
    for (let i = 0; i < COMPLETED_STATION_INDEX; i += 1) {
      items.push({
        position: i,
        state: i < passedCount ? 'passed' : 'future',
        labelKey: STATION_LABEL_KEYS[i],
        subtitle: latestPerStation[i] ? formatDateTime(latestPerStation[i] as string) : '—',
      });
    }
    items.push({
      position: COMPLETED_STATION_INDEX,
      state: 'current',
      labelKey:
        terminalKind === 'failed'
          ? 'tasks.journey.terminal.failed'
          : 'tasks.journey.terminal.cancelled',
      subtitle: '—',
      terminal: terminalKind,
    });
  } else {
    const statusIndex = STATION_INDEX_BY_STATUS[statusKey];
    const currentIndex = Math.max(
      statusIndex === undefined ? -1 : statusIndex,
      reachedDelivery ? 1 : -1,
    );
    for (let i = 0; i <= COMPLETED_STATION_INDEX; i += 1) {
      items.push({
        position: i,
        state:
          currentIndex === -1
            ? 'future'
            : i < currentIndex
              ? 'passed'
              : i === currentIndex
                ? 'current'
                : 'future',
        labelKey: STATION_LABEL_KEYS[i],
        subtitle: latestPerStation[i] ? formatDateTime(latestPerStation[i] as string) : '—',
      });
    }
  }

  return (
    <ol
      role="list"
      aria-label={t('tasks.section.journey')}
      className={`flex flex-col md:flex-row ${className ?? ''}`}
    >
      {items.map((item, index) => {
        const isCurrent = item.state === 'current';
        const isLast = index === items.length - 1;
        // The segment leaving a node is traversed only when that station is
        // itself passed; everything ahead of the current step stays unlit.
        const connectorClass = item.state === 'passed' ? 'bg-pixel-fg' : 'bg-pixel-line';
        return (
          <li
            key={item.position}
            aria-current={isCurrent ? 'step' : undefined}
            className="relative flex items-start gap-3 pb-6 last:pb-0 md:block md:flex-1 md:pb-0"
          >
            {!isLast && (
              <>
                {/* Vertical connector (mobile, below the 24px node). */}
                <span
                  aria-hidden="true"
                  className={`absolute bottom-0 left-[11px] top-[28px] w-[2px] md:hidden ${connectorClass}`}
                />
                {/* Horizontal connector (md+, beside the 24px node). */}
                <span
                  aria-hidden="true"
                  className={`absolute left-[26px] right-0 top-[11px] hidden h-[2px] md:block ${connectorClass}`}
                />
              </>
            )}
            <div className="relative shrink-0">
              <StationNode state={item.state} position={item.position} terminal={item.terminal} />
              {item.position === COMPLETED_STATION_INDEX &&
                !item.terminal &&
                burst &&
                // Decorative one-shot beat; the hook suppresses it entirely
                // under reduced motion so it never mounts then.
                (
                  <span className="pointer-events-none absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2">
                    <CompletionStar burst={burst} onDone={ack} />
                  </span>
                )}
            </div>
            <div className="min-w-0 md:mt-2">
              <div
                className={`font-pixel text-pixel-sm uppercase tracking-pixel ${
                  isCurrent ? 'text-pixel-fg' : 'text-pixel-muted'
                }`}
              >
                {t(item.labelKey)}
              </div>
              {item.terminal === 'failed' ? (
                // The error section renders only when an error message
                // exists (conditional rendering), so the anchor is emitted
                // only then; otherwise a plain-text hint - no dead links.
                errorMessage ? (
                  <a
                    href={errorTarget}
                    className="font-mono text-xs text-pixel-accent-2 underline decoration-2 underline-offset-2 hover:brightness-110"
                  >
                    {t('tasks.journey.terminal.failedHint')}
                  </a>
                ) : (
                  <div className="font-mono text-xs text-pixel-muted">
                    {t('tasks.journey.terminal.failedHint')}
                  </div>
                )
              ) : (
                <div className="font-mono text-xs text-pixel-muted">{item.subtitle}</div>
              )}
            </div>
          </li>
        );
      })}
    </ol>
  );
}

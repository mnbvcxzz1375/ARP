import { useT } from '../../i18n';
import { PIXEL_CHIP } from '../../lib/tokens';
import StationMaster from './StationMaster';
import AgentAvatar from './AgentAvatar';
import './relay-scene.css';

/**
 * RelayScene - the overview hero's pixel illustration plus its status
 * summary line.
 *
 * Layout (fixed 4px-grid segment widths, the panel is `flex-col sm:flex-row`
 * around it):
 * - agent segments 40px each: a read-only AgentAvatar (size 28) standing on
 *   a muted pedestal with a 2px --pixel-bg edge. The right agent is
 *   `hidden sm:block`; the scene keeps `min-w-0` + `flex-wrap` so it can
 *   never push the panel past its grid column.
 * - tower segment 96px: three stacked body layers alternating
 *   --pixel-muted / --pixel-raised with 2px --pixel-bg edges and a 4px-per-side
 *   inset staircase, an --pixel-fg mast with a decorative --pixel-accent top
 *   lamp, and --pixel-bg window squares. The StationMaster sprite (32px,
 *   pose="idle") stands inside the tower's lower half - read-only
 *   consumption; the tower art is sibling markup, so it renders with or
 *   without the sprite.
 * - package segment 48px: an --pixel-fg parcel with a 2px --pixel-bg edge
 *   and --pixel-line sealing tape, resting on a 2px --pixel-line track.
 *
 * All fills are theme-following tokens (no new colors, no hardcoded hex):
 * fg/surface 11.39:1 dark / 14.04:1 light, muted/surface 6.84:1 / 6.46:1,
 * bg/fg 12.39:1 / 11.39:1, bg/muted 7.44:1 / 5.24:1 - all pass AA.
 *
 * Motion contract (the scene's only animation, triggered by a REAL state
 * change - never auto-loop): OverviewPage adds `.is-live` to this root when
 * the `dashboard/overview` query returns a changed data reference, and
 * removes it again on `animationend`. The parcel then runs once along the
 * agent A -> tower -> right-side polyline (1200ms, steps(8) hard pixel
 * displacement). The end keyframe equals the natural rest position, so the
 * parcel "sits beside the tower" before, after and instead of the run.
 * relay-scene.css carries its own `prefers-reduced-motion: reduce` and
 * `(max-width: 767px)` blocks: reduced motion and mobile show the static
 * terminal state no matter what class the host adds.
 *
 * Summary line: `font-display text-pixel-base` (PS2P holds no CJK glyphs,
 * so Chinese honestly falls back to the configured CJK stack). Branches:
 * failed tasks first (inline PIXEL_CHIP.bad chip, the existing LED-red AA
 * precedent), then "no agent on duty", then the nominal reading. The
 * nominal branch is plain text-pixel-fg - no new decorative color.
 */
export interface RelaySceneProps {
  onlineAgents: number;
  failedTasks: number;
  /** Merged onto the scene root; the host toggles `is-live` from outside. */
  className?: string;
}

/** Self-contained scanline texture (alpha 0.12 <= 0.15), same approach as
 *  EmptyState's scene containers: no dependency on index.css utility
 *  classes or another item's CSS landing order. */
const SCENE_TEXTURE =
  'bg-[repeating-linear-gradient(0deg,rgba(0,0,0,0.12)_0_1px,rgba(0,0,0,0)_1px_2px)]';

/** Stable seeds for the two illustrative agent sprites (deterministic
 *  avatars; the overview payload carries counts, not identities). */
const AGENT_A_SEED = 'overview-agent-a';
const AGENT_B_SEED = 'overview-agent-b';

function AgentSegment({ seed, name, hidden }: { seed: string; name: string; hidden?: boolean }) {
  return (
    <div
      className={
        'flex w-[40px] flex-col items-center justify-end' + (hidden ? ' hidden sm:flex' : '')
      }
    >
      <AgentAvatar seed={seed} size={28} name={name} />
      {/* Pedestal: muted fill with the 2px bg edge (7.44:1 / 5.24:1). */}
      <div className="mt-[2px] h-[8px] w-[36px] border-2 border-pixel-bg bg-pixel-muted" />
    </div>
  );
}

function TowerSegment() {
  return (
    <div className="relative flex w-[96px] flex-col items-center justify-end">
      {/* Mast + top lamp (decorative accent, non-text). */}
      <div className="h-[3px] w-[6px] bg-pixel-accent" />
      <div className="h-[8px] w-[2px] bg-pixel-fg" />
      {/* Top layer (muted) + mid layer (raised): 4px-per-side inset staircase,
          2px bg edges, bg window squares at the edges the mascot leaves open. */}
      <div className="flex h-[12px] w-[80px] items-center justify-between border-2 border-pixel-bg bg-pixel-muted px-[10px]">
        <span className="block h-[4px] w-[4px] bg-pixel-bg" />
        <span className="block h-[4px] w-[4px] bg-pixel-bg" />
      </div>
      <div className="flex h-[12px] w-[88px] items-center justify-between border-2 border-pixel-bg bg-pixel-raised px-[8px]">
        <span className="block h-[4px] w-[4px] bg-pixel-bg" />
        <span className="block h-[4px] w-[4px] bg-pixel-bg" />
      </div>
      {/* Bottom layer (muted). */}
      <div className="h-[16px] w-[96px] border-2 border-pixel-bg bg-pixel-muted" />
      {/*
        StationMaster embedded in the tower (read-only consumption,
        size=32 pose="idle": static terminal frame, no timers, no hover).
        Absolutely placed in the tower's lower half; sibling - not child -
        markup, so the tower renders with or without it.
      */}
      <StationMaster size={32} pose="idle" className="absolute bottom-0 left-[32px] z-10" />
    </div>
  );
}

function Parcel() {
  return (
    <div
      aria-hidden="true"
      className="relay-scene__package absolute bottom-[8px] left-[140px] z-20 h-[16px] w-[20px] border-2 border-pixel-bg bg-pixel-fg"
    >
      {/* Sealing tape (line color on the fg parcel, decorative). */}
      <div className="absolute left-[8px] top-0 h-full w-[2px] bg-pixel-line" />
      <div className="absolute top-[6px] h-[2px] w-full bg-pixel-line" />
    </div>
  );
}

export default function RelayScene({ onlineAgents, failedTasks, className }: RelaySceneProps) {
  const t = useT();

  const rootClass = ['relay-scene flex flex-col gap-6 sm:flex-row sm:items-center', className]
    .filter(Boolean)
    .join(' ');

  const summary = failedTasks > 0 ? (
    <>
      {/* Inline count chip on the existing LED-red AA palette (tokens.ts). */}
      <span
        className={`inline-flex items-center px-2 py-0.5 leading-none font-pixel text-pixel-sm ${PIXEL_CHIP.bad}`}
      >
        {failedTasks}
      </span>{' '}
      {t('overview.summary.failed', { count: failedTasks })}
    </>
  ) : onlineAgents === 0 ? (
    t('overview.summary.idle')
  ) : (
    t('overview.summary.nominal', { count: onlineAgents })
  );

  return (
    <div className={rootClass}>
      <div
        className={
          'relative flex min-w-0 flex-wrap items-end justify-start ' + SCENE_TEXTURE
        }
      >
        <AgentSegment seed={AGENT_A_SEED} name={t('overview.hero.agentA')} />
        <TowerSegment />
        {/* Layout spacer for the 48px parcel slot; the parcel itself is
            absolutely positioned relative to this scene container. */}
        <div className="w-[48px]" aria-hidden="true" />
        <AgentSegment seed={AGENT_B_SEED} name={t('overview.hero.agentB')} hidden />
        {/* The 2px line track under the parcel's resting slot. */}
        <div
          aria-hidden="true"
          className="absolute bottom-[6px] left-[44px] right-0 h-[2px] bg-pixel-line"
        />
        <Parcel />
      </div>
      {/* Summary: PS2P has no CJK glyphs - Chinese falls through to the
          configured CJK fallback stack, never faked as pixel text. */}
      <p className="text-pixel-fg font-display text-pixel-base">{summary}</p>
    </div>
  );
}

import './feedback.css';

/**
 * One-shot pixel star burst shown when a task migrates to `completed`.
 *
 * Driven by `useCompletionBurst` (see useCompletionBurst.ts): the parent
 * mounts this component only while `burst` is true, and `onDone` is wired to
 * `ack()` so the star unmounts after the animation. The hook also owns the
 * reduced-motion suppression, so under reduced motion this component is
 * never mounted at all (feedback.css carries a display:none fallback as a
 * second layer).
 *
 * The star is a transient, purely decorative emphasis on an already-readable
 * status (the journey map station is marked completed regardless), so it is
 * aria-hidden rather than role="img".
 *
 * Geometry: 21x21 pixel-star sparkle (axis-aligned square unioned with a
 * 45-degree diamond), fill var(--pixel-accent) with a 2px var(--pixel-bg)
 * hard edge - measured 4.93:1 on dark surface panels (the light-theme 2.85:1
 * is the same non-text decorative condition as the existing nav active
 * state). Outermost path points sit at 1/19 so the centered 2px stroke
 * lands exactly on the 0..20 viewBox edge.
 */
export interface CompletionStarProps {
  /** True while the burst is armed; renders nothing when false. */
  burst: boolean;
  /** Called when the pop animation ends (parent ack()/unmount). */
  onDone?: () => void;
}

const STAR_PATH =
  'M10,1 L14,5 L15,5 L15,6 L19,10 L15,14 L15,15 L14,15 L10,19 L6,15 L5,15 L5,14 L1,10 L5,6 L5,5 L6,5 Z';

export function CompletionStar({ burst, onDone }: CompletionStarProps) {
  if (!burst) return null;
  return (
    <svg
      viewBox="0 0 21 21"
      shapeRendering="crispEdges"
      aria-hidden="true"
      className="completion-star"
      onAnimationEnd={onDone}
    >
      <path
        d={STAR_PATH}
        fill="var(--pixel-accent)"
        stroke="var(--pixel-bg)"
        strokeWidth={2}
      />
    </svg>
  );
}

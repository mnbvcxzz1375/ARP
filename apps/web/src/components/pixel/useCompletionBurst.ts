import { useCallback, useEffect, useRef, useState } from 'react';
import { usePreferences } from '../../hooks/usePreferences';

/**
 * One-shot burst flag driving the task-completion star animation.
 *
 * Semantics: the internal ref tracks the previous status. The flag flips to
 * true ONLY on a non-completed -> completed migration; staying on
 * `completed` never re-arms it (a re-render or refetch must not replay the
 * burst). `ack()` resets the flag so the star unmounts.
 *
 * Reduced motion (rule 2b): this hook is not itself a timer, so the guard
 * lives in the return value - when the OS media query or the manual
 * preference asks for reduced motion, the hook permanently returns
 * `burst: false`, so the star is never even mounted (the CSS-level
 * `animation-duration: 0ms` kill would otherwise leave a static visible
 * star behind, because star-pop uses `fill-mode: both`).
 *
 * A 2200ms fallback ack timer (also guarded) covers the case where the CSS
 * animation is killed mid-flight and `onAnimationEnd` never fires: the star
 * then cannot linger as a natural-state static node.
 */

function systemPrefersReducedMotion(): boolean {
  if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') return false;
  return window.matchMedia('(prefers-reduced-motion: reduce)').matches;
}

export interface CompletionBurstResult {
  /** True only between a non-completed -> completed migration and `ack()`. */
  burst: boolean;
  /** Reset the burst (unmount the star). Idempotent. */
  ack: () => void;
}

export function useCompletionBurst(status: string): CompletionBurstResult {
  const { data: preferences } = usePreferences();
  const reducedMotion =
    preferences?.reducedMotion === true || systemPrefersReducedMotion();

  const previousStatus = useRef<string>(status);
  const [burst, setBurst] = useState(false);
  const fallbackTimer = useRef<number | null>(null);

  const clearFallback = useCallback(() => {
    if (fallbackTimer.current !== null) {
      window.clearTimeout(fallbackTimer.current);
      fallbackTimer.current = null;
    }
  }, []);

  const ack = useCallback(() => {
    setBurst(false);
    clearFallback();
  }, [clearFallback]);

  useEffect(() => {
    const previous = previousStatus.current;
    previousStatus.current = status;
    // Permanent suppression: never arm, even on a completed migration.
    if (reducedMotion) return;
    if (previous !== 'completed' && status === 'completed') {
      setBurst(true);
      clearFallback();
      fallbackTimer.current = window.setTimeout(ack, 2200);
    }
  }, [status, reducedMotion, ack, clearFallback]);

  // Clear the fallback timer if the consumer unmounts before ack().
  useEffect(() => () => clearFallback(), [clearFallback]);

  return { burst, ack };
}

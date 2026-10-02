import { useEffect, useState } from 'react';
import { useT } from '../../i18n';
import { usePreferences } from '../../hooks/usePreferences';
import './mascot.css';
import { getAvatarSprite } from '../../lib/avatar';

/** Console mascot. The legacy wave pose triggers one short greeting hop.
 * OS and stored reduced-motion preferences keep it static; no idle timers.
 */
export type StationMasterPose = 'idle' | 'wave';

export interface StationMasterProps {
  /** Sprite size in px. */
  size?: 32 | 64;
  /** 'wave' (default) reacts to hover/focus; 'idle' is static/read-only. */
  pose?: StationMasterPose;
  className?: string;
}

function readMediaReducedMotion(): boolean {
  if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') return false;
  return window.matchMedia('(prefers-reduced-motion: reduce)').matches;
}

/**
 * Combined reduced-motion gate: the OS media query OR the stored backend
 * preference (usePreferences.ts:38, null = follow the OS hint). Either
 * signal wins - the sprite goes static.
 */
function useReducedMotion(): boolean {
  const [mediaReduced, setMediaReduced] = useState(readMediaReducedMotion);
  const { data: preferences } = usePreferences();

  useEffect(() => {
    if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') return;
    const mql = window.matchMedia('(prefers-reduced-motion: reduce)');
    setMediaReduced(mql.matches);
    const onChange = (event: MediaQueryListEvent) => setMediaReduced(event.matches);
    if (typeof mql.addEventListener === 'function') {
      mql.addEventListener('change', onChange);
      return () => mql.removeEventListener('change', onChange);
    }
    if (typeof mql.addListener === 'function') {
      mql.addListener(onChange);
      return () => mql.removeListener(onChange);
    }
    return undefined;
  }, []);

  return mediaReduced || preferences?.reducedMotion === true;
}

export default function StationMaster({ size = 32, pose = 'wave', className }: StationMasterProps) {
  const t = useT();
  const reduced = useReducedMotion();
  const [waving, setWaving] = useState(false);
  const sprite = getAvatarSprite('agentnet-station-master');
  const interactive = pose === 'wave' && !reduced;
  const handleActivate = () => {
    if (interactive && document.visibilityState !== 'hidden') setWaving(true);
  };
  const handleDeactivate = () => setWaving(false);
  const composed = ['station-master', interactive && waving ? 'is-waving' : '', className].filter(Boolean);

  return (
    <svg
      className={composed.join(' ')}
      width={size}
      height={size}
      viewBox={size === 32 ? sprite.portraitViewBox : sprite.viewBox}
      shapeRendering="crispEdges"
      role="img"
      aria-label={t('shell.mascot.alt')}
      tabIndex={interactive ? 0 : undefined}
      onPointerEnter={handleActivate}
      onPointerLeave={handleDeactivate}
      onFocus={handleActivate}
      onBlur={handleDeactivate}
    >
      <image href={sprite.src} width={sprite.width} height={sprite.height} aria-hidden="true" />
    </svg>
  );
}

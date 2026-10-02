import { useEffect, useState } from 'react';
import { usePreferences } from '../../hooks/usePreferences';
import type { StagePoint } from './ArchipelagoStage';

/**
 * MessagePacket - the 16x16 task parcel that runs along a TASK edge.
 *
 * Art: the RelayScene parcel recipe - an --pixel-fg body with a 2px
 * --pixel-bg edge and --pixel-line sealing tape - redrawn as a 16x16 SVG
 * rect sprite (integer coordinates, crispEdges, theme-following variables,
 * stage-phase code art, not a bitmap sprite).
 *
 * Motion contract (tightened RelayScene `is-live` contract):
 * - the parcel runs ONCE along its edge (sender center -> target center)
 *   with hard steps(8) displacement, one iteration, no timer, no loop;
 * - the run starts only when the host raises `active` (the stage's isLive,
 *   which the host raises ONLY on a real change inside the tasks FIRST
 *   page - offset=0, limit=50: a new task_id or a delivery-status change;
 *   the 15s poll tick and the initial load never raise it);
 * - `animationend` bubbles up from this svg to the stage root, whose
 *   handler clears the flag for the host (onLiveEnd);
 * - the END keyframe is the natural rest position (the parcel sits at the
 *   target node), so the resting frame, the terminal frame and every
 *   disabled state show the same static picture with no jump;
 * - reduced motion: the OS media query OR the stored backend preference
 *   (usePreferences) - EITHER signal wins and the parcel goes fully
 *   static (double gate, the StationMaster rule; the JS side never adds
 *   .is-running and archipelago.css's own media blocks kill the animation
 *   as a belt).
 *
 * Scope honesty: a packet exists per drawable TASK edge, never on a pending
 * edge (a connection request is not a message delivery), and a run only
 * reflects a change inside the newest 50-row page - it is NOT a live view
 * of all network traffic.
 */

function readMediaReducedMotion(): boolean {
  if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') return false;
  return window.matchMedia('(prefers-reduced-motion: reduce)').matches;
}

/**
 * Combined reduced-motion gate (media query OR stored preference). Local
 * copy of StationMaster's hook - StationMaster.tsx keeps its own private
 * version (read-only reuse), so this file duplicates the ~20 lines rather
 * than touching it.
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

/** Custom-property style: the run offsets (from - to) feed the shared
 *  keyframes block in archipelago.css. */
interface PacketStyle {
  left: number;
  top: number;
  '--packet-dx': string;
  '--packet-dy': string;
}

export interface MessagePacketProps {
  /** Sender node center (run start). */
  from: StagePoint;
  /** Target node center (rest position). */
  to: StagePoint;
  /** Raised by the host on a real first-page tasks change. */
  active?: boolean;
  className?: string;
}

export default function MessagePacket({ from, to, active = false, className }: MessagePacketProps) {
  const reduced = useReducedMotion();
  const running = active && !reduced;

  const composed = ['archipelago-packet'];
  if (running) composed.push('is-running');
  if (className) composed.push(className);

  const style: PacketStyle = {
    // Rest position: sitting at the target node center (16x16 sprite).
    left: to.x - 8,
    top: to.y - 8,
    // Run offsets relative to that rest slot, in the same design space.
    '--packet-dx': `${from.x - to.x}px`,
    '--packet-dy': `${from.y - to.y}px`,
  };

  return (
    <svg
      className={composed.join(' ')}
      width={16}
      height={16}
      viewBox="0 0 16 16"
      shapeRendering="crispEdges"
      aria-hidden="true"
      style={style}
    >
      {/* Parcel body: fg fill + 2px bg edge (RelayScene recipe). */}
      <rect
        x={1}
        y={1}
        width={14}
        height={14}
        fill="var(--pixel-fg)"
        stroke="var(--pixel-bg)"
        strokeWidth={2}
      />
      {/* Sealing tape: pixel-line cross bands (decorative). */}
      <rect x={7} y={1} width={2} height={14} fill="var(--pixel-line)" />
      <rect x={1} y={7} width={14} height={2} fill="var(--pixel-line)" />
    </svg>
  );
}

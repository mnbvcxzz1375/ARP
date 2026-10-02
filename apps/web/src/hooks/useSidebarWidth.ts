import { useCallback, useEffect, useState } from 'react';

/**
 * Draggable console sidebar width (DashboardShell).
 *
 * The width drives the shell grid's `--shell-sidebar-w` custom property;
 * collapsed mode is a fixed icon rail and does not use this value. The
 * width persists in localStorage (client-side shell layout, like the
 * collapsed state); the server-side preferences whitelist deliberately
 * stays closed to shell chrome.
 *
 * Pointer: the handle captures the pointer, so drag continues even when
 * the cursor leaves the strip. The sidebar is flush with the viewport's
 * left edge, so width == pointer clientX; clamp() keeps it sane.
 * Keyboard: role=separator + ArrowLeft/ArrowRight (see the handle in
 * DashboardShell) call adjustWidth.
 */

const STORAGE_KEY = 'agentnet.sidebarWidth';

/** Narrowest useful width: labels stay readable below the default. */
export const SIDEBAR_MIN = 168;
/** Widest: beyond this the main column loses too much room. */
export const SIDEBAR_MAX = 448;
/** Keyboard nudge per keypress (px). */
export const SIDEBAR_KEYBOARD_STEP = 16;

function clamp(value: number): number {
  return Math.min(SIDEBAR_MAX, Math.max(SIDEBAR_MIN, Math.round(value)));
}

function readStored(fallback: number): number {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw == null) return fallback;
    const parsed = Number(raw);
    return Number.isFinite(parsed) && parsed > 0 ? clamp(parsed) : fallback;
  } catch {
    return fallback;
  }
}

export interface SidebarWidth {
  width: number;
  dragging: boolean;
  setWidth: (next: number) => void;
  adjustWidth: (delta: number) => void;
  onPointerDown: (e: React.PointerEvent<HTMLDivElement>) => void;
  onPointerMove: (e: React.PointerEvent<HTMLDivElement>) => void;
  onPointerUp: (e: React.PointerEvent<HTMLDivElement>) => void;
}

export function useSidebarWidth(defaultWidth: number): SidebarWidth {
  const [width, setWidthState] = useState<number>(() => readStored(defaultWidth));
  const [dragging, setDragging] = useState(false);

  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, String(width));
    } catch {
      // Private mode / disabled storage: width stays session-scoped.
    }
  }, [width]);

  const setWidth = useCallback((next: number) => setWidthState(clamp(next)), []);

  const adjustWidth = useCallback(
    (delta: number) => setWidthState((current) => clamp(current + delta)),
    [],
  );

  const onPointerDown = useCallback((e: React.PointerEvent<HTMLDivElement>) => {
    // Primary button only; mid/right click would fight context menus.
    if (e.button !== 0) return;
    e.preventDefault();
    e.currentTarget.setPointerCapture(e.pointerId);
    setDragging(true);
  }, []);

  const onPointerMove = useCallback(
    (e: React.PointerEvent<HTMLDivElement>) => {
      if (!dragging) return;
      e.preventDefault();
      setWidth(e.clientX);
    },
    [dragging, setWidth],
  );

  const onPointerUp = useCallback(
    (e: React.PointerEvent<HTMLDivElement>) => {
      if (!dragging) return;
      e.currentTarget.releasePointerCapture(e.pointerId);
      setDragging(false);
    },
    [dragging],
  );

  return { width, dragging, setWidth, adjustWidth, onPointerDown, onPointerMove, onPointerUp };
}

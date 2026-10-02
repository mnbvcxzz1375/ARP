import { describe, it, expect, beforeEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import {
  SIDEBAR_MAX,
  SIDEBAR_MIN,
  SIDEBAR_KEYBOARD_STEP,
  useSidebarWidth,
} from '../useSidebarWidth';

const STORAGE_KEY = 'agentnet.sidebarWidth';

/** Minimal pointer-event stand-in: the hook only reads button, pointerId,
 * clientX, currentTarget and preventDefault (jsdom has no PointerEvent). */
function pointer(
  overrides: Partial<{ button: number; pointerId: number; clientX: number }>,
  element: HTMLDivElement,
) {
  return {
    button: 0,
    pointerId: 7,
    clientX: 0,
    currentTarget: element,
    preventDefault: () => undefined,
    ...overrides,
  } as never;
}

function fakeElement(): HTMLDivElement {
  return {
    setPointerCapture: () => undefined,
    releasePointerCapture: () => undefined,
  } as unknown as HTMLDivElement;
}

describe('useSidebarWidth', () => {
  beforeEach(() => {
    localStorage.removeItem(STORAGE_KEY);
  });

  it('falls back to the per-variant default when nothing is stored', () => {
    const { result } = renderHook(() => useSidebarWidth(256));
    expect(result.current.width).toBe(256);
  });

  it('restores a persisted width, clamped into range', () => {
    localStorage.setItem(STORAGE_KEY, '320');
    const { result } = renderHook(() => useSidebarWidth(256));
    expect(result.current.width).toBe(320);

    // Out-of-range garbage clamps instead of letting the layout break.
    localStorage.setItem(STORAGE_KEY, '99999');
    const stored = renderHook(() => useSidebarWidth(256));
    expect(stored.result.current.width).toBe(SIDEBAR_MAX);

    localStorage.setItem(STORAGE_KEY, 'not-a-number');
    const junk = renderHook(() => useSidebarWidth(168));
    expect(junk.result.current.width).toBe(168);
  });

  it('persists every width change to localStorage', () => {
    const { result } = renderHook(() => useSidebarWidth(256));
    act(() => result.current.setWidth(200));
    expect(result.current.width).toBe(200);
    expect(localStorage.getItem(STORAGE_KEY)).toBe('200');
  });

  it('clamps pointer-driven widths and keyboard nudges', () => {
    const { result } = renderHook(() => useSidebarWidth(256));

    act(() => result.current.setWidth(10));
    expect(result.current.width).toBe(SIDEBAR_MIN);

    act(() => result.current.setWidth(99999));
    expect(result.current.width).toBe(SIDEBAR_MAX);

    act(() => result.current.adjustWidth(SIDEBAR_KEYBOARD_STEP));
    expect(result.current.width).toBe(SIDEBAR_MAX);

    act(() => result.current.adjustWidth(-SIDEBAR_KEYBOARD_STEP * 20));
    expect(result.current.width).toBe(SIDEBAR_MIN);
  });

  it('drags via pointer capture and ends on pointerup', () => {
    const { result } = renderHook(() => useSidebarWidth(200));
    const element = fakeElement();

    act(() => result.current.onPointerDown(pointer({ clientX: 200 }, element)));
    expect(result.current.dragging).toBe(true);

    act(() => result.current.onPointerMove(pointer({ clientX: 260 }, element)));
    expect(result.current.width).toBe(260);

    act(() => result.current.onPointerUp(pointer({ clientX: 260 }, element)));
    expect(result.current.dragging).toBe(false);
    expect(localStorage.getItem(STORAGE_KEY)).toBe('260');
  });

  it('ignores non-primary-button pointerdown', () => {
    const { result } = renderHook(() => useSidebarWidth(200));
    const element = fakeElement();

    act(() => result.current.onPointerDown(pointer({ button: 2 }, element)));
    expect(result.current.dragging).toBe(false);
    expect(result.current.width).toBe(200);
  });
});

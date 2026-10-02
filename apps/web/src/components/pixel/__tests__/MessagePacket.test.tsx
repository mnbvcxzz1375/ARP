import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, cleanup, act } from '@testing-library/react';
import MessagePacket from '../MessagePacket';
import { setLocale } from '../../../i18n/core';

// The packet reads the stored backend preference (usePreferences.ts);
// mocking the hook keeps the unit tests network-free.
let mockPrefReducedMotion: boolean | null = null;
vi.mock('../../../hooks/usePreferences', () => ({
  usePreferences: () => ({ data: { reducedMotion: mockPrefReducedMotion } }),
}));

/**
 * Unit-level checks for the task parcel. What jsdom can verify:
 * - the reduced-motion DOUBLE gate (media query OR stored backend
 *   preference - either signal wins and the parcel goes fully static,
 *   i.e. never gets the .is-running class the JS side would add);
 * - the run only starts while the host raises `active`;
 * - the resting position is the target node center and the run offsets
 *   feed the shared CSS keyframes via custom properties.
 *
 * What is NOT covered here (documented gaps):
 * - the actual keyframe animation lives in archipelago.css; jsdom does not
 *   run CSS animations, so "static" is asserted as the absence of the
 *   JS-side .is-running class plus the css-side media blocks being out of
 *   reach here (the CSS file itself is the belt, reviewed separately);
 * - animationend bubbling is exercised through the stage/host level.
 */

/** jsdom has no matchMedia; install a fake with a controllable flag and
 *  REAL change listeners so the mid-run flip is dispatchable. */
let mediaReduced = false;
let changeListeners: Array<(event: { matches: boolean }) => void> = [];
function installMatchMedia() {
  changeListeners = [];
  Object.defineProperty(window, 'matchMedia', {
    configurable: true,
    writable: true,
    value: (query: string) => ({
      matches: query.includes('prefers-reduced-motion') ? mediaReduced : false,
      media: query,
      onchange: null,
      addEventListener: (_type: string, listener: (event: { matches: boolean }) => void) => {
        changeListeners.push(listener);
      },
      removeEventListener: (_type: string, listener: (event: { matches: boolean }) => void) => {
        changeListeners = changeListeners.filter((l) => l !== listener);
      },
      addListener: (listener: (event: { matches: boolean }) => void) => {
        changeListeners.push(listener);
      },
      removeListener: (listener: (event: { matches: boolean }) => void) => {
        changeListeners = changeListeners.filter((l) => l !== listener);
      },
      dispatchEvent: vi.fn(),
    }),
  });
}

/** Simulate the OS flipping the media query while the packet is mounted. */
function flipMediaQuery(reduced: boolean) {
  mediaReduced = reduced;
  act(() => {
    for (const listener of [...changeListeners]) listener({ matches: reduced });
  });
}

/** SVG elements expose `className` as SVGAnimatedString, not a string. */
function cls(svg: Element): string {
  return svg.getAttribute('class') ?? '';
}

const FROM = { x: 240, y: 94 };
const TO = { x: 672, y: 108 };

beforeEach(() => {
  mediaReduced = false;
  mockPrefReducedMotion = null;
  installMatchMedia();
  setLocale('en');
});

afterEach(() => {
  setLocale('en');
  cleanup();
});

describe('MessagePacket', () => {
  it('rests at the target node center and publishes the run offsets as custom properties', () => {
    const { container } = render(<MessagePacket from={FROM} to={TO} />);
    const svg = container.querySelector('svg')!;
    // 16x16 sprite centered on the target center.
    expect(svg.getAttribute('width')).toBe('16');
    expect(svg.getAttribute('height')).toBe('16');
    expect(svg.style.left).toBe('664px'); // to.x - 8
    expect(svg.style.top).toBe('100px'); // to.y - 8
    expect(svg.style.getPropertyValue('--packet-dx')).toBe('-432px');
    expect(svg.style.getPropertyValue('--packet-dy')).toBe('-14px');
  });

  it('runs (is-running) only while the host raises active and motion is allowed', () => {
    const { container, rerender } = render(<MessagePacket from={FROM} to={TO} active />);
    expect(cls(container.querySelector('svg')!)).toContain('is-running');

    rerender(<MessagePacket from={FROM} to={TO} active={false} />);
    expect(cls(container.querySelector('svg')!)).not.toContain('is-running');
  });

  it('stays fully static under the reduced-motion media query (gate 1)', () => {
    mediaReduced = true;
    const { container } = render(<MessagePacket from={FROM} to={TO} active />);
    expect(cls(container.querySelector('svg')!)).not.toContain('is-running');
  });

  it('stays fully static when the stored backend preference requests reduced motion (gate 2)', () => {
    mockPrefReducedMotion = true;
    const { container } = render(<MessagePacket from={FROM} to={TO} active />);
    expect(cls(container.querySelector('svg')!)).not.toContain('is-running');
  });

  it('drops the run when the media query flips to reduce while active', () => {
    const { container } = render(<MessagePacket from={FROM} to={TO} active />);
    expect(cls(container.querySelector('svg')!)).toContain('is-running');

    flipMediaQuery(true);
    expect(cls(container.querySelector('svg')!)).not.toContain('is-running');

    // And it resumes when the query clears again while still active.
    flipMediaQuery(false);
    expect(cls(container.querySelector('svg')!)).toContain('is-running');
  });

  it('paints the parcel recipe from theme tokens (fg body, bg edge, line tape)', () => {
    const { container } = render(<MessagePacket from={FROM} to={TO} />);
    const svg = container.querySelector('svg')!;
    expect(svg.getAttribute('aria-hidden')).toBe('true');
    const body = svg.querySelector('rect[x="1"][y="1"]')!;
    expect(body.getAttribute('fill')).toBe('var(--pixel-fg)');
    expect(body.getAttribute('stroke')).toBe('var(--pixel-bg)');
    expect(body.getAttribute('stroke-width')).toBe('2');
    expect(svg.querySelector('rect[x="7"][y="1"]')!.getAttribute('fill')).toBe(
      'var(--pixel-line)',
    );
    expect(svg.querySelector('rect[x="1"][y="7"]')!.getAttribute('fill')).toBe(
      'var(--pixel-line)',
    );
  });
});

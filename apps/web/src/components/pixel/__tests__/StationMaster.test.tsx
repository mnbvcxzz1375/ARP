import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, act, cleanup } from '@testing-library/react';
import StationMaster from '../StationMaster';
import { setLocale } from '../../../i18n/core';
import { RouterForTesting } from '../../../test-utils';
import DashboardShell from '../../../app/DashboardShell';
import { PERSONAL_NAV } from '../../../app/navigation';

// The mascot reads the stored backend preference (usePreferences.ts:38);
// mocking the hook keeps the unit tests network-free.
let mockPrefReducedMotion: boolean | null = null;
vi.mock('../../../hooks/usePreferences', () => ({
  usePreferences: () => ({ data: { reducedMotion: mockPrefReducedMotion } }),
}));

vi.mock('../../../hooks/useAuth', () => ({
  useAuth: vi.fn(() => ({
    data: {
      user_id: 'u1',
      username: 'tester',
      role: 'user',
      permissions: ['agent:read:own'],
      organizations: [],
    },
  })),
  useLogout: vi.fn(() => ({ mutate: vi.fn() })),
}));

vi.mock('../../../hooks/useTheme', () => ({
  useTheme: () => ({ theme: 'dark', toggleTheme: vi.fn() }),
}));

/** jsdom has no matchMedia; install the fake the spec's acceptance runs. */
let mediaReduced = false;
function installMatchMedia() {
  Object.defineProperty(window, 'matchMedia', {
    configurable: true,
    writable: true,
    value: (query: string) => ({
      matches: query.includes('prefers-reduced-motion') ? mediaReduced : false,
      media: query,
      onchange: null,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      addListener: vi.fn(),
      removeListener: vi.fn(),
      dispatchEvent: vi.fn(),
    }),
  });
}

/** SVG elements expose `className` as SVGAnimatedString, not a string. */
function cls(svg: Element): string {
  return svg.getAttribute('class') ?? '';
}

beforeEach(() => {
  mediaReduced = false;
  mockPrefReducedMotion = null;
  installMatchMedia();
  setLocale('en');
});

afterEach(() => {
  setLocale('en');
  vi.useRealTimers();
  cleanup();
});

describe('StationMaster', () => {
  it('renders as role=img with the i18n label (en) and no aria-hidden', () => {
    render(<StationMaster size={32} />);
    const svg = screen.getByRole('img');
    expect(svg).toHaveAttribute('aria-label', 'Station Master');
    // role=img and aria-hidden are mutually exclusive; the label must win.
    expect(svg).not.toHaveAttribute('aria-hidden');
  });

  it('renders the zh label under the zh locale', () => {
    setLocale('zh');
    render(<StationMaster size={32} />);
    const label = screen.getByRole('img').getAttribute('aria-label');
    // Code points U+5C0F U+7AD9 U+957F = 'xiao zhan zhang', asserted as hex
    // so this file stays pure ASCII (the zh string lives in
    // i18n/locales/zh/shell.ts).
    expect(label ? [...label].map((c) => c.codePointAt(0)!.toString(16)) : []).toEqual([
      '5c0f',
      '7ad9',
      '957f',
    ]);
  });

  it('renders pixel-identical markup across repeated renders at the same size', () => {
    const { container: first } = render(<StationMaster size={64} pose="idle" />);
    const firstHtml = first.querySelector('svg')!.outerHTML;
    cleanup();
    const { container: second } = render(<StationMaster size={64} pose="idle" />);
    expect(second.querySelector('svg')!.outerHTML).toBe(firstHtml);
  });

  it('uses the shared original robot artwork at the requested size', () => {
    render(<StationMaster size={64} />);
    const sprite = screen.getByRole('img');
    expect(sprite).toHaveAttribute('width', '64');
    expect(sprite).toHaveAttribute('height', '64');
    expect(sprite.querySelector('image')?.getAttribute('href')).toMatch(/robot-.*\.png$/);
  });

  it('waves on pointer enter and stops on pointer leave', () => {
    render(<StationMaster />);
    const svg = screen.getByRole('img');
    fireEvent.pointerEnter(svg);
    expect(cls(svg)).toContain('is-waving');
    fireEvent.pointerLeave(svg);
    expect(cls(svg)).not.toContain('is-waving');
  });

  it('waves on focus and stops on blur', () => {
    render(<StationMaster />);
    const svg = screen.getByRole('img');
    fireEvent.focus(svg);
    expect(cls(svg)).toContain('is-waving');
    fireEvent.blur(svg);
    expect(cls(svg)).not.toContain('is-waving');
  });

  it('does not schedule idle animation timers on hover', () => {
    vi.useFakeTimers();
    render(<StationMaster />);
    fireEvent.pointerEnter(screen.getByRole('img'));
    expect(vi.getTimerCount()).toBe(0);
  });

  it('returns to its resting pose when the pointer leaves', () => {
    vi.useFakeTimers();
    render(<StationMaster />);
    const svg = screen.getByRole('img');
    fireEvent.pointerEnter(svg);
    fireEvent.pointerLeave(svg);
    act(() => {
      vi.advanceTimersByTime(7000);
    });
    expect(cls(svg)).not.toContain('is-waving');
    expect(cls(svg)).not.toContain('is-blinking');
  });

  it('stays fully static under the reduced-motion media query', () => {
    mediaReduced = true;
    vi.useFakeTimers();
    render(<StationMaster />);
    const svg = screen.getByRole('img');
    fireEvent.pointerEnter(svg);
    fireEvent.focus(svg);
    expect(cls(svg)).not.toContain('is-waving');
    expect(cls(svg)).not.toContain('is-blinking');
    act(() => {
      vi.advanceTimersByTime(7000);
    });
    expect(cls(svg)).not.toContain('is-blinking');
  });

  it('stays fully static when the stored preference requests reduced motion', () => {
    mockPrefReducedMotion = true;
    vi.useFakeTimers();
    render(<StationMaster />);
    const svg = screen.getByRole('img');
    fireEvent.pointerEnter(svg);
    expect(cls(svg)).not.toContain('is-waving');
    expect(cls(svg)).not.toContain('is-blinking');
    act(() => {
      vi.advanceTimersByTime(7000);
    });
    expect(cls(svg)).not.toContain('is-blinking');
  });

  it('never interacts in idle pose (read-only consumers)', () => {
    vi.useFakeTimers();
    render(<StationMaster size={64} pose="idle" />);
    const svg = screen.getByRole('img');
    fireEvent.pointerEnter(svg);
    fireEvent.focus(svg);
    expect(cls(svg)).not.toContain('is-waving');
    expect(cls(svg)).not.toContain('is-blinking');
  });

  it('skips the blink while the document is hidden', () => {
    Object.defineProperty(document, 'visibilityState', {
      configurable: true,
      get: () => 'hidden',
    });
    try {
      vi.useFakeTimers();
      render(<StationMaster />);
      const svg = screen.getByRole('img');
      fireEvent.pointerEnter(svg);
      expect(cls(svg)).not.toContain('is-waving');
      expect(cls(svg)).not.toContain('is-blinking');
      act(() => {
        vi.advanceTimersByTime(7000);
      });
      expect(cls(svg)).not.toContain('is-blinking');
    } finally {
      // Restore the prototype-backed getter.
      delete (document as { visibilityState?: string }).visibilityState;
    }
  });

  it('mounts in the expanded sidebar footer without adding a 4th chromatic', () => {
    const { container } = render(
      <RouterForTesting>
        <DashboardShell navGroups={PERSONAL_NAV} scope="personal" />
      </RouterForTesting>,
    );

    // Desktop sidebar footer only: the collapsed variant and the closed
    // mobile drawer render nothing.
    expect(container.querySelectorAll('.station-master')).toHaveLength(1);
    expect(container.querySelector('.station-master')!).toHaveAttribute(
      'aria-label',
      'Station Master',
    );
    // Existing chromatic spans stay at 2 in the closed-drawer DOM
    // (desktop scope header + mobile top bar); the spec forbids a 4th.
    expect(container.querySelectorAll('.chromatic')).toHaveLength(2);

    // Open the mobile drawer: its mascot row (above the controls row) and
    // its chromatic span appear - still no new chromatic beyond the
    // existing 3 source locations.
    fireEvent.click(screen.getByLabelText('Open navigation'));
    expect(container.querySelectorAll('.station-master')).toHaveLength(2);
    expect(container.querySelectorAll('.chromatic')).toHaveLength(3);
  });
});

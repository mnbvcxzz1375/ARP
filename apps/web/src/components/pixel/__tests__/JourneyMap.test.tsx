import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, act, cleanup } from '@testing-library/react';
import JourneyMap from '../JourneyMap';
import { setLocale } from '../../../i18n/core';

// useCompletionBurst reads the stored backend preference (usePreferences);
// mocking the hook keeps these unit tests network-free.
let mockPrefReducedMotion: boolean | null = null;
vi.mock('../../../hooks/usePreferences', () => ({
  usePreferences: () => ({ data: { reducedMotion: mockPrefReducedMotion } }),
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

const STATION_LABELS = ['Queued', 'Delivery', 'Execution', 'Approval', 'Completed'];

interface Case {
  status: string;
  /** Expected current position (0..4) or a terminal label. */
  current: number | 'Failed' | 'Cancelled';
}

/** All 11 TaskStatus members (constants.py:27-38). */
const ALL_STATUSES: Case[] = [
  { status: 'created', current: 0 },
  { status: 'queued', current: 0 },
  { status: 'delivered', current: 1 },
  { status: 'accepted', current: 2 },
  { status: 'running', current: 2 },
  { status: 'awaiting_approval', current: 3 },
  { status: 'completed', current: 4 },
  { status: 'failed', current: 'Failed' },
  { status: 'rejected', current: 'Failed' },
  { status: 'cancelled', current: 'Cancelled' },
  { status: 'expired', current: 'Cancelled' },
];

function currentLabel(container: HTMLElement): string {
  const step = container.querySelector('[aria-current="step"]');
  if (!step) throw new Error('no aria-current="step" marker found');
  // The station number span is also font-pixel, so scope to the label block.
  return step.querySelector('.min-w-0 .font-pixel')!.textContent ?? '';
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

describe('JourneyMap', () => {
  it('renders an ordered list with exactly five stations', () => {
    const { container } = render(<JourneyMap status="created" />);
    const list = screen.getByRole('list');
    expect(list.tagName).toBe('OL');
    expect(list.getAttribute('aria-label')).toBe('Journey');
    expect(container.querySelectorAll('li')).toHaveLength(5);
  });

  it.each(ALL_STATUSES.map((c) => [c.status, c.current] as const))(
    'places status "%s" on exactly one current step (aria-current unique)',
    (status, current) => {
      const { container } = render(<JourneyMap status={status} />);
      const steps = container.querySelectorAll('[aria-current="step"]');
      expect(steps).toHaveLength(1);
      const expected = typeof current === 'number' ? STATION_LABELS[current] : current;
      expect(currentLabel(container)).toBe(expected);
    },
  );

  it.each([
    ['created', 0],
    ['queued', 0],
    ['delivered', 1],
    ['accepted', 2],
    ['running', 2],
    ['awaiting_approval', 3],
    ['completed', 4],
  ] as const)('paints passed/current/future nodes for status "%s"', (status, current) => {
    const { container } = render(<JourneyMap status={status} />);
    const passed = container.querySelectorAll('.bg-pixel-led-green');
    const future = container.querySelectorAll('.bg-pixel-bg');
    expect(passed).toHaveLength(current);
    expect(future).toHaveLength(4 - current);
    // Every node keeps the 2px hard edge.
    for (const node of [...passed, ...future]) {
      expect(node.className).toContain('border-2');
    }
  });

  it('numbers the current node and styles it with the accent fill', () => {
    const { container } = render(<JourneyMap status="awaiting_approval" />);
    const current = container.querySelector('[aria-current="step"]')!;
    const node = current.querySelector('div.bg-pixel-accent')!;
    expect(node.className).toContain('border-[#191a26]');
    expect(node.textContent).toBe('4'); // 1-based station number
  });

  it('marks every passed node with the checkbox-style inner square', () => {
    const { container } = render(<JourneyMap status="completed" />);
    const passed = container.querySelectorAll('.bg-pixel-led-green');
    expect(passed).toHaveLength(4);
    for (const node of passed) {
      const inner = node.querySelector('span')!;
      expect(inner.className).toContain('h-2');
      expect(inner.className).toContain('w-2');
      expect(inner.className).toContain('bg-[#191a26]');
    }
  });

  it.each([
    ['failed', 'bg-pixel-led-red'],
    ['rejected', 'bg-pixel-led-red'],
    ['cancelled', 'bg-[#4b4968]'],
    ['expired', 'bg-[#4b4968]'],
  ] as const)('renders the terminal node for "%s" with %s', (status, nodeClass) => {
    const { container } = render(<JourneyMap status={status} />);
    const current = container.querySelector('[aria-current="step"]')!;
    // Attribute selector: the token contains brackets needing no escaping.
    const node = current.querySelector(`div[class~="${nodeClass}"]`);
    expect(node).not.toBeNull();
    expect(node!.className).toContain('border-2');
    expect(node!.className).toContain('border-[#191a26]');
    // Stations 1-4 stay regular stations; the terminal takes slot 5.
    expect(container.querySelectorAll('li')).toHaveLength(5);
  });

  it('keeps stations below the delivery point passed on terminal statuses', () => {
    // No delivery status: only the queue station was traversed.
    const { container } = render(<JourneyMap status="failed" />);
    expect(container.querySelectorAll('.bg-pixel-led-green')).toHaveLength(1);
    expect(container.querySelectorAll('.bg-pixel-bg')).toHaveLength(3);
    // Delivery reached before the failure: queue + delivery passed.
    const { container: withDelivery } = render(
      <JourneyMap status="failed" deliveryStatus="route_selected" />,
    );
    expect(withDelivery.querySelectorAll('.bg-pixel-led-green')).toHaveLength(2);
    expect(withDelivery.querySelectorAll('.bg-pixel-bg')).toHaveLength(2);
  });

  it('feeds the delivery station from delivery_status', () => {
    const { container } = render(<JourneyMap status="queued" deliveryStatus="delivering" />);
    // Queue passed, delivery current (index 1).
    expect(container.querySelectorAll('.bg-pixel-led-green')).toHaveLength(1);
    expect(currentLabel(container)).toBe('Delivery');
  });

  it('renders the failed terminal hint as plain text without an error message', () => {
    const { container } = render(<JourneyMap status="failed" />);
    expect(screen.getByText('See the error details below')).toBeInTheDocument();
    // No dead anchor: the error section only exists when error_message does.
    expect(container.querySelector('a')).toBeNull();
  });

  it('anchors the failed terminal hint to #task-error when an error message exists', () => {
    render(<JourneyMap status="failed" errorMessage="boom" />);
    const link = screen.getByRole('link', { name: 'See the error details below' });
    expect(link).toHaveAttribute('href', '#task-error');
  });

  it('honors a custom errorTarget anchor', () => {
    render(<JourneyMap status="rejected" errorMessage="boom" errorTarget="#elsewhere" />);
    expect(screen.getByRole('link')).toHaveAttribute('href', '#elsewhere');
  });

  it('shows the latest progress event time per station and "—" otherwise', () => {
    const progress = [
      { status: 'queued', created_at: '2024-03-01T08:00:00Z' },
      { status: 'running', created_at: '2024-03-01T08:02:00Z' },
      { status: 'running', created_at: '2024-03-01T08:05:00Z' },
    ];
    const { container } = render(
      <JourneyMap status="completed" progress={progress} />,
    );
    const items = [...container.querySelectorAll('li')];
    // Station 1 (queued) shows the queued event; station 3 (execution) the
    // latest running event; untouched stations show the dash.
    expect(items[0].textContent).toContain('2024');
    expect(items[2].textContent).toContain('5:00');
    expect(items[1].textContent).toContain('—');
    expect(items[3].textContent).toContain('—');
  });

  it('renders the zh station label under the zh locale', () => {
    setLocale('zh');
    const { container } = render(<JourneyMap status="created" />);
    // Code points U+6392 U+961F = 'pai dui'; asserted as hex so this file
    // stays pure ASCII (the zh string lives in i18n/locales/zh/tasks.ts).
    const label = currentLabel(container);
    expect(label ? [...label].map((c) => c.codePointAt(0)!.toString(16)) : []).toEqual([
      '6392',
      '961f',
    ]);
  });

  it('does not crash on an unknown status and marks no current step', () => {
    const { container } = render(<JourneyMap status="something_unknown" />);
    expect(container.querySelectorAll('[aria-current="step"]')).toHaveLength(0);
    expect(container.querySelectorAll('li')).toHaveLength(5);
  });

  // ---------------------------------------------------------------------------
  // Completion star (consumed read-only; lifecycle owned by the burst hook)
  // ---------------------------------------------------------------------------

  it('mounts the star on the completed node after a migration and unmounts on animation end', () => {
    const { container, rerender } = render(<JourneyMap status="running" />);
    expect(container.querySelector('.completion-star')).toBeNull();
    rerender(<JourneyMap status="completed" />);
    const star = container.querySelector('.completion-star');
    expect(star).not.toBeNull();
    // The star rides the completed station node (slot 5).
    expect(star!.closest('li')!.querySelector('.bg-pixel-accent')).not.toBeNull();
    fireEvent.animationEnd(star!);
    expect(container.querySelector('.completion-star')).toBeNull();
  });

  it('does not re-arm while the task stays completed', () => {
    const { container, rerender } = render(<JourneyMap status="running" />);
    rerender(<JourneyMap status="completed" />);
    fireEvent.animationEnd(container.querySelector('.completion-star')!);
    rerender(<JourneyMap status="completed" />);
    rerender(<JourneyMap status="completed" />);
    expect(container.querySelector('.completion-star')).toBeNull();
  });

  it('never mounts the star under the reduced-motion media query', () => {
    mediaReduced = true;
    const { container, rerender } = render(<JourneyMap status="running" />);
    rerender(<JourneyMap status="completed" />);
    expect(container.querySelector('.completion-star')).toBeNull();
  });

  it('never mounts the star when the stored preference requests reduced motion', () => {
    mockPrefReducedMotion = true;
    const { container, rerender } = render(<JourneyMap status="running" />);
    rerender(<JourneyMap status="completed" />);
    expect(container.querySelector('.completion-star')).toBeNull();
  });

  it('unmounts the star via the fallback ack timer if the animation never ends', () => {
    vi.useFakeTimers();
    const { container, rerender } = render(<JourneyMap status="running" />);
    rerender(<JourneyMap status="completed" />);
    expect(container.querySelector('.completion-star')).not.toBeNull();
    // act(): ack's setBurst re-render flushes inside the faked timer tick.
    act(() => {
      vi.advanceTimersByTime(2200);
    });
    expect(container.querySelector('.completion-star')).toBeNull();
  });

  // ---------------------------------------------------------------------------
  // Layout contract
  // ---------------------------------------------------------------------------

  it('uses the vertical mobile layout and the horizontal md+ layout', () => {
    const { container } = render(<JourneyMap status="queued" />);
    const list = container.querySelector('ol')!;
    // Mobile: vertical column; md+: horizontal row of equal-flex stations.
    // (jsdom cannot lay out real boxes, so this asserts the responsive
    // class contract; the 375px overflow check runs in e2e.)
    expect(list.className).toContain('flex-col');
    expect(list.className).toContain('md:flex-row');
    for (const li of [...container.querySelectorAll('li')]) {
      expect(li.className).toContain('md:flex-1');
    }
  });

  it('renders no 2px connector behind the last station', () => {
    const { container } = render(<JourneyMap status="queued" />);
    const items = [...container.querySelectorAll('li')];
    const last = items[items.length - 1];
    // Connectors are aria-hidden spans absolutely positioned inside each li.
    expect(last.querySelectorAll('span[aria-hidden="true"]')).toHaveLength(0);
    expect(items[0].querySelectorAll('span[aria-hidden="true"]')).toHaveLength(2);
  });
});

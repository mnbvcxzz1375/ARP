import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { useState } from 'react';
import type React from 'react';
import { render, screen, fireEvent, cleanup } from '@testing-library/react';
import ArchipelagoStage, {
  STAGE_SLOTS,
  LIGHTHOUSE_ANCHOR,
  MAX_ISLANDS,
} from '../ArchipelagoStage';
import type { ArchipelagoMapAgent, ArchipelagoMapEdge } from '../ArchipelagoStage';
import { setLocale } from '../../../i18n/core';
import { ISLAND_NODE_CENTER_OFFSET } from '../IslandNode';

// MessagePacket reads the stored backend preference (usePreferences.ts);
// mocking the hook keeps the stage tests network-free.
let mockPrefReducedMotion: boolean | null = null;
vi.mock('../../../hooks/usePreferences', () => ({
  usePreferences: () => ({ data: { reducedMotion: mockPrefReducedMotion } }),
}));

/** jsdom has no matchMedia; install a fake with a controllable flag so the
 *  packets' reduced-motion gate stays deterministic. */
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

/**
 * Unit-level checks for the archipelago stage. What jsdom can verify:
 * - the roving tabindex (selected island - or the first when nothing is
 *   selected - is the only tab entry point);
 * - arrow-key roving navigation to the geometrically nearest slot,
 *   including the lighthouse origin when nothing is selected, and the
 *   no-candidate no-op;
 * - the refocus of the newly selected island's button after an arrow move;
 * - the no-connections hint: it renders only with islands but no drawable
 *   route, and its "open list mode" button re-enables pointer events
 *   (pointer-events-auto on top of the container's pointer-events-none,
 *   since `pointer-events` is an INHERITED property) and fires onViewList;
 * - packets exist per drawable TASK edge only (never a pending edge).
 *
 * What is NOT covered here (documented gaps):
 * - jsdom does not compute inherited CSS `pointer-events`, so hit-test
 *   reachability is asserted as the presence of the pointer-events-auto
 *   class on the button inside the pointer-events-none container (the
 *   CSS-inheritance argument itself is a static, non-runtime property);
 * - the ResizeObserver scale (jsdom has no layout; the guard returns early);
 * - the packet keyframe animation (archipelago.css; see MessagePacket.test);
 * - visual pixel-art precision (sighted review).
 */

const AGENTS: ArchipelagoMapAgent[] = [
  { agent_id: 'a1', agent_number: 'AN-01', name: 'Atlas', status: 'online' },
  { agent_id: 'a2', agent_number: 'AN-02', name: 'Beacon', status: 'offline' },
  { agent_id: 'a3', agent_number: 'AN-03', name: 'Cinder', status: 'online' },
];

const TASK_EDGE: ArchipelagoMapEdge = { kind: 'task', from: 'a1', to: 'a2', taskId: 't1' };
const PENDING_EDGE: ArchipelagoMapEdge = {
  kind: 'pending',
  from: 'a2',
  to: 'a3',
  requesterNumber: 'AN-02',
  connectionId: 'c1',
};

/** The island buttons in slotted order (S1..S3). */
function islandButtons(container: HTMLElement): HTMLButtonElement[] {
  return Array.from(container.querySelectorAll<HTMLButtonElement>('button[aria-pressed]'));
}

/**
 * Stateful host: feeds the selection back as the prop, exactly like
 * OverviewPage does (`handleSelect` -> setSelectedId). Arrow keys then
 * navigate from the CURRENT selection, not a stale one.
 */
function HostStage({
  initialSelectedId = 'a1',
  ...props
}: {
  initialSelectedId?: string | null;
} & Omit<React.ComponentProps<typeof ArchipelagoStage>, 'selectedId' | 'onSelect'>) {
  const [selectedId, setSelectedId] = useState<string | null>(initialSelectedId);
  return <ArchipelagoStage {...props} selectedId={selectedId} onSelect={setSelectedId} />;
}

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

describe('ArchipelagoStage', () => {
  it('animates only the changed route and dims unrelated routes in focus mode', () => {
    const edges = [TASK_EDGE, {kind:'task' as const,from:'a2',to:'a3',taskId:'t2'}];
    const { container } = render(<ArchipelagoStage visibleAgents={AGENTS} edges={edges}
      focusId="a1" animatedRoutes={['a1:a2']} />);
    expect(container.querySelectorAll('.archipelago-packet.is-running')).toHaveLength(1);
    expect(container.querySelector('[data-route="a2:a3"]')).toHaveAttribute('data-focused','false');
    expect(container.querySelector('[data-route="a1:a2"]')).toHaveAttribute('data-focused','true');
  });
  it('can stop the decorative sea while keeping island selection available', () => {
    const onSelect = vi.fn();
    const { container, rerender } = render(
      <ArchipelagoStage visibleAgents={AGENTS} reducedMotion onSelect={onSelect} />,
    );
    expect(screen.getByRole('region')).toHaveAttribute('data-reduced-motion', 'true');
    fireEvent.click(islandButtons(container)[1]);
    expect(onSelect).toHaveBeenCalledWith('a2');
    rerender(<ArchipelagoStage visibleAgents={AGENTS} reducedMotion={false} />);
    expect(screen.getByRole('region')).toHaveAttribute('data-reduced-motion', 'false');
  });

  it('renders the design space and slots the first MAX_ISLANDS agents', () => {
    const { container } = render(<ArchipelagoStage visibleAgents={AGENTS} />);
    const stage = container.querySelector('.archipelago-stage') as HTMLElement;
    expect(stage).toBeTruthy();
    expect(STAGE_SLOTS).toHaveLength(MAX_ISLANDS);
    expect(LIGHTHOUSE_ANCHOR).toEqual({ x: 480, y: 346 });
    // Three agents -> three island buttons, one per slot.
    expect(islandButtons(container)).toHaveLength(3);
  });

  it('keeps a map entry reachable when the selected agent belongs to a different list page', () => {
    const { container } = render(
      <ArchipelagoStage visibleAgents={AGENTS} selectedId="agent-outside-the-map" />,
    );
    const buttons = islandButtons(container);
    expect(buttons.filter((button) => button.tabIndex === 0)).toHaveLength(1);
    expect(buttons[0].tabIndex).toBe(0);
  });

  it('keeps only the selected island in the tab order; the first one when nothing is selected', () => {
    const { container, rerender } = render(
      <ArchipelagoStage visibleAgents={AGENTS} selectedId={null} />,
    );
    const [b1, b2, b3] = islandButtons(container);
    expect(b1!.tabIndex).toBe(0);
    expect(b2!.tabIndex).toBe(-1);
    expect(b3!.tabIndex).toBe(-1);

    rerender(<ArchipelagoStage visibleAgents={AGENTS} selectedId="a2" />);
    const [r1, r2, r3] = islandButtons(container);
    expect(r1!.tabIndex).toBe(-1);
    expect(r2!.tabIndex).toBe(0);
    expect(r3!.tabIndex).toBe(-1);
  });

  it('moves the selection to the geometrically nearest slot on arrow keys', () => {
    const { container } = render(<HostStage visibleAgents={AGENTS} initialSelectedId="a1" />);
    // Track the host-level selection (HostStage feeds it back as the prop).
    const selectedIds = () =>
      islandButtons(container)
        .map((b) => (b.getAttribute('aria-pressed') === 'true' ? '1' : '0'))
        .join('');
    const region = () => screen.getByRole('region');

    // ArrowRight from S1 (240,94): S2 (672,108) is the nearest rightward
    // slot (S3 leans the other way and is excluded by the dx<0 guard).
    fireEvent.keyDown(region(), { key: 'ArrowRight' });
    expect(selectedIds()).toBe('010');

    // ArrowLeft from S2 (672,108): back to S1.
    fireEvent.keyDown(region(), { key: 'ArrowLeft' });
    expect(selectedIds()).toBe('100');

    // ArrowDown from S1 (240,94): both S2 and S3 lie below; the weighted
    // nearest is S3 (154,296): primary dy=202 beats S2's dy=14 even though
    // S2 is closer in pure Euclidean terms.
    fireEvent.keyDown(region(), { key: 'ArrowDown' });
    expect(selectedIds()).toBe('001');
  });

  it('originates from the lighthouse anchor when nothing is selected', () => {
    const onSelect = vi.fn();
    render(<ArchipelagoStage visibleAgents={AGENTS} selectedId={null} onSelect={onSelect} />);
    const region = screen.getByRole('region');
    // ArrowUp from the lighthouse (480,346): all three slots sit above it;
    // the weighted-nearest one is S2 (dy=-238, dx=+192) -> agent a2.
    fireEvent.keyDown(region, { key: 'ArrowUp' });
    expect(onSelect).toHaveBeenCalledTimes(1);
    expect(onSelect).toHaveBeenLastCalledWith('a2');
  });

  it('ignores a direction with no candidate slot', () => {
    const onSelect = vi.fn();
    render(<ArchipelagoStage visibleAgents={AGENTS} selectedId="a1" onSelect={onSelect} />);
    const region = screen.getByRole('region');
    // S1 is the top-most slot: no island lies above it.
    fireEvent.keyDown(region, { key: 'ArrowUp' });
    expect(onSelect).not.toHaveBeenCalled();
    // Non-arrow keys never navigate.
    fireEvent.keyDown(region, { key: 'Enter' });
    expect(onSelect).not.toHaveBeenCalled();
  });

  it('refocuses the newly selected island button after an arrow move', () => {
    const onSelect = vi.fn();
    const { container, rerender } = render(
      <ArchipelagoStage visibleAgents={AGENTS} selectedId="a1" onSelect={onSelect} />,
    );
    const region = screen.getByRole('region');
    fireEvent.keyDown(region, { key: 'ArrowRight' });
    expect(onSelect).toHaveBeenLastCalledWith('a2');

    // The host applies the new selection (OverviewPage does the same).
    rerender(<ArchipelagoStage visibleAgents={AGENTS} selectedId="a2" onSelect={onSelect} />);

    const selected = container.querySelector('button[aria-pressed="true"]')!;
    expect(selected).toBe(document.activeElement);
    // ...and the roving tab order followed the selection.
    const [, rerendered2] = islandButtons(container);
    expect(rerendered2!.tabIndex).toBe(0);
  });

  it('renders the no-connections hint with a pointer-reachable list entry', () => {
    const onViewList = vi.fn();
    const { container, rerender } = render(
      <ArchipelagoStage
        visibleAgents={AGENTS}
        edges={[]}
        selectedId="a1"
        onViewList={onViewList}
      />,
    );

    // Islands in view but no drawable route -> role=status hint.
    const hint = screen.getByRole('status');
    expect(hint.className).toContain('pointer-events-none');
    expect(screen.getByText('No routes between the visible islands yet.')).toBeInTheDocument();

    // The entry button opts back into pointer events: the container is
    // pointer-events-none and `pointer-events` is INHERITED, so without
    // pointer-events-auto the button could not be clicked or hovered.
    const button = screen.getByRole('button', { name: 'Open list mode' });
    expect(button.className).toContain('pointer-events-auto');
    fireEvent.click(button);
    expect(onViewList).toHaveBeenCalledTimes(1);

    // With a drawable route the hint disappears.
    rerender(
      <ArchipelagoStage
        visibleAgents={AGENTS}
        edges={[TASK_EDGE]}
        selectedId="a1"
        onViewList={onViewList}
      />,
    );
    expect(screen.queryByRole('status')).toBeNull();
    void container;
  });

  it('runs packets along TASK edges only, never a pending edge', () => {
    const { container } = render(
      <ArchipelagoStage visibleAgents={AGENTS} edges={[TASK_EDGE, PENDING_EDGE]} isLive />,
    );
    const packets = container.querySelectorAll('.archipelago-packet');
    expect(packets).toHaveLength(1);
    // Rest position sits at the target node center (16x16 sprite).
    const packet = packets[0]! as SVGElement;
    const toCenter = {
      x: STAGE_SLOTS[1]!.x,
      y: STAGE_SLOTS[1]!.y - ISLAND_NODE_CENTER_OFFSET,
    };
    expect(packet.style.left).toBe(`${toCenter.x - 8}px`);
    expect(packet.style.top).toBe(`${toCenter.y - 8}px`);
    // isLive raised and motion allowed -> running class present.
    expect(packet.getAttribute('class')).toContain('is-running');
  });

  it('renders no island hint when the roster is empty (the page owns the empty state)', () => {
    render(<ArchipelagoStage visibleAgents={[]} edges={[]} onViewList={() => {}} />);
    // No islands -> no no-connections hint (that state belongs to the page's
    // EmptyState, not the stage) and no list entry.
    expect(screen.queryByRole('status')).toBeNull();
    expect(screen.queryByRole('button')).toBeNull();
  });
});

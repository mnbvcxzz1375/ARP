import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import { render, cleanup } from '@testing-library/react';
import ConnectionLayer, { filterDrawableEdges } from '../ConnectionLayer';
import type { ArchipelagoMapEdge } from '../ArchipelagoStage';
import { setLocale } from '../../../i18n/core';

/**
 * Unit-level checks for the connection layer. What jsdom can verify:
 * - filterDrawableEdges: the BOTH-endpoints rule, the no-target rule,
 *   per-(kind,from,to) dedupe and stable order (the component's own
 *   contract guard on top of the data hook's);
 * - rendering follows the filter exactly: one <line> pair + one label per
 *   drawable edge, nothing for filtered ones;
 * - the two kinds differ by line STYLE (dashed vs solid), never by hue;
 * - the layer is aria-hidden / role=presentation (the semantics travel in
 *   the node labels and tooltips, not here).
 *
 * What is NOT covered here (documented gaps):
 * - the hover tooltip is carried by an SVG <title> inside an aria-hidden
 *   layer; the joined display names are asserted through the layer's own
 *   nameOf fallbacks instead of pointer hover (sighted interaction);
 * - visual stroke rendering (sighted review).
 */

const AGENTS = [
  { agent_id: 'a1', agent_number: 'AN-01', name: 'Atlas', status: 'online' },
  { agent_id: 'a2', agent_number: 'AN-02', name: 'Beacon', status: 'offline' },
  { agent_id: 'a3', agent_number: 'AN-03', name: 'Cinder', status: 'online' },
];

const POINTS = new Map([
  ['a1', { x: 240, y: 94 }],
  ['a2', { x: 672, y: 108 }],
  ['a3', { x: 154, y: 296 }],
]);

const TASK_EDGE: ArchipelagoMapEdge = { kind: 'task', from: 'a1', to: 'a2', taskId: 't1' };
const PENDING_EDGE: ArchipelagoMapEdge = {
  kind: 'pending',
  from: 'a2',
  to: 'a3',
  requesterNumber: 'AN-02',
  connectionId: 'c1',
};

beforeEach(() => {
  setLocale('en');
});

afterEach(() => {
  setLocale('en');
  cleanup();
});

describe('filterDrawableEdges', () => {
  it('keeps an edge whose BOTH endpoints are slotted visible', () => {
    const drawable = filterDrawableEdges([TASK_EDGE, PENDING_EDGE], POINTS);
    expect(drawable).toEqual([TASK_EDGE, PENDING_EDGE]);
  });

  it('never draws a pre-revision edge without a target (no half line)', () => {
    const noTarget: ArchipelagoMapEdge = {
      kind: 'pending',
      from: 'a1',
      to: null,
      requesterNumber: 'AN-01',
    };
    expect(filterDrawableEdges([noTarget], POINTS)).toEqual([]);
  });

  it('drops an edge whose from-endpoint is not slotted (half-visible)', () => {
    const stranger: ArchipelagoMapEdge = {
      kind: 'task',
      from: 'aX',
      to: 'a1',
      taskId: 't2',
    };
    expect(filterDrawableEdges([stranger], POINTS)).toEqual([]);
  });

  it('drops an edge whose to-endpoint is not slotted (half-visible)', () => {
    const stranger: ArchipelagoMapEdge = {
      kind: 'task',
      from: 'a1',
      to: 'aX',
      taskId: 't2',
    };
    expect(filterDrawableEdges([stranger], POINTS)).toEqual([]);
  });

  it('dedupes identical (kind, from, to) pairs but keeps distinct pairs', () => {
    const duplicate: ArchipelagoMapEdge = { kind: 'task', from: 'a1', to: 'a2', taskId: 't3' };
    const drawable = filterDrawableEdges([TASK_EDGE, duplicate, PENDING_EDGE], POINTS);
    // Same pair deduped (the first occurrence wins); the pending pair stays.
    expect(drawable).toEqual([TASK_EDGE, PENDING_EDGE]);
  });

  it('keeps the stable input order (stage packet run + list rely on it)', () => {
    const drawable = filterDrawableEdges([PENDING_EDGE, TASK_EDGE], POINTS);
    expect(drawable.map((e) => e.kind)).toEqual(['pending', 'task']);
  });

  it('skips falsy edge entries defensively', () => {
    const drawable = filterDrawableEdges(
      [undefined as unknown as ArchipelagoMapEdge, TASK_EDGE],
      POINTS,
    );
    expect(drawable).toEqual([TASK_EDGE]);
  });
});

describe('ConnectionLayer rendering', () => {
  it('draws exactly the drawable edges and hides the layer from assistive tech', () => {
    const { container } = render(
      <ConnectionLayer edges={[TASK_EDGE, PENDING_EDGE]} points={POINTS} roster={AGENTS} />,
    );
    const layer = container.querySelector('.archipelago-connections')!;
    expect(layer.getAttribute('aria-hidden')).toBe('true');
    expect(layer.getAttribute('role')).toBe('presentation');

    // Two drawable edges -> two visible lines + two hit lines + two labels.
    expect(layer.querySelectorAll('svg > g > line').length).toBe(4);
    expect(layer.querySelectorAll('.archipelago-connections__label').length).toBe(2);
  });

  it('draws nothing for edges filtered by the both-endpoints rule', () => {
    const halfVisible: ArchipelagoMapEdge = { kind: 'task', from: 'a1', to: 'aX', taskId: 't9' };
    const { container } = render(
      <ConnectionLayer edges={[halfVisible]} points={POINTS} roster={AGENTS} />,
    );
    const layer = container.querySelector('.archipelago-connections')!;
    expect(layer.querySelectorAll('svg > g > line').length).toBe(0);
    expect(layer.querySelectorAll('.archipelago-connections__label').length).toBe(0);
  });

  it('separates the two kinds by LINE STYLE (dashed vs solid), not by hue', () => {
    const { container } = render(
      <ConnectionLayer edges={[TASK_EDGE, PENDING_EDGE]} points={POINTS} roster={AGENTS} />,
    );
    const groups = Array.from(
      container.querySelectorAll<HTMLDivElement>('svg > g'),
    ) as unknown as HTMLDivElement[];
    // Task edge first (g key order = drawable order): solid (no dasharray).
    const taskLine = groups[0]!.querySelector('line')!;
    expect(taskLine.getAttribute('stroke-dasharray')).toBeNull();
    // Pending edge: dashed 6 4, accent stroke.
    const pendingLine = groups[1]!.querySelector('line')!;
    expect(pendingLine.getAttribute('stroke-dasharray')).toBe('6 4');
  });

  it('carries the endpoint names in the hover tooltip through the roster join', () => {
    const { container } = render(
      <ConnectionLayer edges={[TASK_EDGE]} points={POINTS} roster={AGENTS} />,
    );
    const title = container.querySelector('.archipelago-connections__hit title')!;
    // Roster name join (Atlas / Beacon), never raw ids.
    expect(title.textContent).toContain('Atlas');
    expect(title.textContent).toContain('Beacon');
  });

  it('falls back to the requester number, then the raw id, for unknown names', () => {
    const { container } = render(
      <ConnectionLayer edges={[PENDING_EDGE]} points={POINTS} roster={[]} />,
    );
    const title = container.querySelector('.archipelago-connections__hit title')!;
    expect(title.textContent).toContain('AN-02');
    expect(title.textContent).toContain('a3');
  });
});

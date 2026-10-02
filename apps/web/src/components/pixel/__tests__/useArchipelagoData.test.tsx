import type { ReactNode } from 'react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import {
  MAP_CAPACITY,
  useArchipelagoData,
  type ArchipelagoAgent,
  type ArchipelagoPendingRequest,
  type ArchipelagoStatusChange,
  type ArchipelagoTask,
} from '../../../features/overview/useArchipelagoData';

/**
 * Unit coverage for the archipelago data-binding layer. The design's test
 * plan calls for: join / truncation / offset-vs-page parameter
 * distinction / pending edges with an EXTERNAL and an INTERNAL requester.
 * Plus the two pending-contract branches (with and without to_agent_id).
 *
 * The pixel components that consume this hook (ArchipelagoStage /
 * IslandNode / ConnectionLayer / MessagePacket / DetailDrawer) are owned
 * by other implementation slices; those component-level tests live with
 * their components and are not reproduced here.
 */

// The hook talks to the transport only; mock it so no network or demo
// store is involved (same pattern as ConnectionsPage.test.tsx).
vi.mock('../../../api/client', () => ({
  default: {
    get: vi.fn(),
  },
}));

import api from '../../../api/client';

const getMock = api.get as unknown as ReturnType<typeof vi.fn>;

type TasksResponse = {
  tasks: ArchipelagoTask[];
  total: number;
  offset: number;
  limit: number;
};

function agent(id: string, number: string, name = id): ArchipelagoAgent {
  return {
    agent_id: id,
    agent_number: number,
    name,
    runtime: 'python-sdk',
    status: 'online',
    inbound_policy: 'public',
    discoverable: true,
    capabilities: [],
    created_at: '2026-10-01T00:00:00Z',
    updated_at: '2026-10-01T00:00:00Z',
  };
}

/** Seven agents in deliberately shuffled number order. */
const shuffledAgents: ArchipelagoAgent[] = [
  agent('a-3', 'AN-GLOBAL-0000000003-03', 'Charlie'),
  agent('a-1', 'AN-GLOBAL-0000000001-01', 'Alpha'),
  agent('a-5', 'AN-GLOBAL-0000000005-05', 'Echo'),
  agent('a-2', 'AN-GLOBAL-0000000002-02', 'Bravo'),
  agent('a-4', 'AN-GLOBAL-0000000004-04', 'Delta'),
  agent('a-6', 'AN-GLOBAL-0000000006-06', 'Foxtrot'),
  agent('a-7', 'AN-GLOBAL-0000000007-07', 'Golf'),
];

const internalPending: ArchipelagoPendingRequest = {
  connection_id: 'c-1',
  // agent_number is the REQUESTER's number (production contract).
  agent_number: 'AN-GLOBAL-0000000002-02',
  requester_agent: 'a-2',
  to_agent_id: 'a-4',
  requested_policy: 'unknown',
  created_at: '2026-10-01T00:00:00Z',
};

const externalPending: ArchipelagoPendingRequest = {
  connection_id: 'c-2',
  // A requester owned by ANOTHER user: its id never appears in the
  // caller's agent list, which is the production norm.
  agent_number: 'AN-GLOBAL-EXT00000000-99',
  requester_agent: 'a-external',
  to_agent_id: 'a-1',
  requested_policy: 'unknown',
  created_at: '2026-10-01T00:00:00Z',
};

function tasksPayload(tasks: ArchipelagoTask[]): TasksResponse {
  return { tasks, total: tasks.length, offset: 0, limit: 50 };
}

function task(
  id: string,
  sender: string,
  target: string,
  delivery = 'delivered',
): ArchipelagoTask {
  return {
    task_id: id,
    status: 'delivered',
    sender_agent: sender,
    target_agent: target,
    created_at: '2026-10-01T00:00:00Z',
    updated_at: '2026-10-01T00:00:00Z',
    delivery_status: delivery,
  };
}

function renderArchipelago(
  args: Parameters<typeof useArchipelagoData>[0],
  tasksResponse: TasksResponse = tasksPayload([]),
) {
  getMock.mockReset();
  getMock.mockResolvedValue({ data: tasksResponse });
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
  return renderHook(() => useArchipelagoData(args), { wrapper });
}

beforeEach(() => {
  getMock.mockReset();
});

afterEach(() => {
  vi.clearAllMocks();
});

describe('useArchipelagoData - visibleAgents', () => {
  it('de-duplicates by agent_id, sorts by agent_number and caps at MAP_CAPACITY', async () => {
    const { result } = renderArchipelago({ agents: shuffledAgents });
    await waitFor(() => expect(result.current.firstPageTasks).toBeDefined());

    expect(result.current.sortedAgents).toHaveLength(7);
    expect(result.current.visibleAgents).toHaveLength(MAP_CAPACITY);
    // Dictionary order, stable: a-1..a-6 visible, a-7 cut.
    expect(result.current.visibleAgents.map((a) => a.agent_id)).toEqual([
      'a-1',
      'a-2',
      'a-3',
      'a-4',
      'a-5',
      'a-6',
    ]);
  });

  it('de-duplicates identical agent_id rows', async () => {
    const duplicated = [shuffledAgents[1], { ...shuffledAgents[1] }, shuffledAgents[0]];
    const { result } = renderArchipelago({ agents: duplicated });
    await waitFor(() => expect(result.current.firstPageTasks).toBeDefined());
    expect(result.current.sortedAgents).toHaveLength(2);
  });
});

describe('useArchipelagoData - tasks feed', () => {
  it('queries the first page with offset/limit (NOT the agents endpoint page/page_size)', async () => {
    renderArchipelago({ agents: [] });
    await waitFor(() => expect(getMock).toHaveBeenCalled());
    expect(getMock).toHaveBeenCalledWith('/v1/dashboard/tasks', {
      params: { offset: 0, limit: 50 },
    });
    // The hook must never drive the tasks endpoint with page/page_size.
    const call = getMock.mock.calls[0];
    expect(call[0]).toBe('/v1/dashboard/tasks');
    expect((call[1] as { params: Record<string, unknown> }).params).not.toHaveProperty('page');
    expect((call[1] as { params: Record<string, unknown> }).params).not.toHaveProperty('page_size');
  });

  it('passes the raw first page through as firstPageTasks', async () => {
    const page = tasksPayload([
      task('t-1', 'a-1', 'a-2'),
      task('t-2', 'a-3', 'a-4', 'delivering'),
    ]);
    const { result } = renderArchipelago({ agents: [] }, page);
    await waitFor(() => expect(result.current.firstPageTasks).toBeDefined());
    expect(result.current.firstPageTasks).toHaveLength(2);
    expect(result.current.firstPageTasks?.[1].delivery_status).toBe('delivering');
  });

  it('exposes isTasksError when the feed fails (degrade, not crash)', async () => {
    getMock.mockReset();
    getMock.mockRejectedValue(new Error('403'));
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    const wrapper = ({ children }: { children: ReactNode }) => (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    );
    const { result } = renderHook(() => useArchipelagoData({}), { wrapper });
    await waitFor(() => expect(result.current.isTasksError).toBe(true));
    expect(result.current.firstPageTasks).toBeUndefined();
  });
});

describe('useArchipelagoData - edges', () => {
  it('uses full authoritative route counts even when the sampled task page is empty', async () => {
    const { result } = renderArchipelago({agents:shuffledAgents,aggregateOnly:true,
      traffic:{agents:[],routes:[{from:'a-1',to:'a-2',running:61,queued:0,awaiting_approval:0,failed_24h:0,revision:'v1'}],failure_window_hours:24,generated_at:'now'}});
    await waitFor(()=>expect(result.current.firstPageTasks).toBeDefined());
    expect(result.current.edges[0]?.workload?.running).toBe(61);
  });
  it('joins task sender->target by agent_id (UUID endpoints)', async () => {
    const page = tasksPayload([task('t-1', 'a-1', 'a-2'), task('t-2', 'a-3', 'a-4')]);
    const { result } = renderArchipelago({ agents: shuffledAgents }, page);
    await waitFor(() => expect(result.current.firstPageTasks).toBeDefined());
    const taskEdges = result.current.edges.filter((e) => e.kind === 'task');
    expect(taskEdges).toEqual([
      { kind: 'task', from: 'a-1', to: 'a-2', taskId: 't-1' },
      { kind: 'task', from: 'a-3', to: 'a-4', taskId: 't-2' },
    ]);
  });

  it('drops task edges whose endpoints are beyond the map capacity', async () => {
    // a-7 exists in the agent list but is past the 6-slot cut.
    const page = tasksPayload([task('t-1', 'a-1', 'a-7')]);
    const { result } = renderArchipelago({ agents: shuffledAgents }, page);
    await waitFor(() => expect(result.current.firstPageTasks).toBeDefined());
    expect(result.current.edges).toHaveLength(0);
  });

  it('skips self-tasks (sender === target) instead of drawing a zero-length stub', async () => {
    const page = tasksPayload([task('t-1', 'a-1', 'a-1')]);
    const { result } = renderArchipelago({ agents: shuffledAgents }, page);
    await waitFor(() => expect(result.current.firstPageTasks).toBeDefined());
    expect(result.current.edges).toHaveLength(0);
  });

  it('drops a task edge whose counterpart endpoint belongs to another user', async () => {
    // Production tasks can name a sender/target outside the caller's own
    // agents: the join must not half-draw it; the detail panel shows the
    // raw id instead (no identity is guessed here).
    const page = tasksPayload([task('t-1', 'a-1', 'someone-elses-agent')]);
    const { result } = renderArchipelago({ agents: shuffledAgents }, page);
    await waitFor(() => expect(result.current.firstPageTasks).toBeDefined());
    expect(result.current.edges).toHaveLength(0);
  });

  it('draws the pending edge when BOTH endpoints are the user\'s own agents (rare self-connect path)', async () => {
    const { result } = renderArchipelago({
      agents: shuffledAgents,
      pendingRequests: [internalPending],
    });
    await waitFor(() => expect(result.current.firstPageTasks).toBeDefined());
    expect(result.current.edges).toHaveLength(1);
    expect(result.current.edges[0]).toEqual({
      kind: 'pending',
      from: 'a-2',
      to: 'a-4',
      requesterNumber: 'AN-GLOBAL-0000000002-02',
      connectionId: 'c-1',
    });
  });

  it('never draws a pending edge whose requester is an external user\'s agent (the production norm)', async () => {
    const { result } = renderArchipelago({
      agents: shuffledAgents,
      pendingRequests: [externalPending],
    });
    await waitFor(() => expect(result.current.firstPageTasks).toBeDefined());
    // The request stays a list/detail concern, not a map edge: dropping it
    // here is the permission semantics, not a lost feature.
    expect(result.current.edges).toHaveLength(0);
  });

  it('never invents a target when to_agent_id is absent (pre-revision contract)', async () => {
    const legacy: ArchipelagoPendingRequest = {
      connection_id: 'c-legacy',
      agent_number: 'AN-GLOBAL-0000000002-02',
      requester_agent: 'a-2',
      // no to_agent_id at all - the pre-revision payload
      requested_policy: 'unknown',
      created_at: '2026-10-01T00:00:00Z',
    };
    const { result } = renderArchipelago({
      agents: shuffledAgents,
      pendingRequests: [legacy],
    });
    await waitFor(() => expect(result.current.firstPageTasks).toBeDefined());
    expect(result.current.edges).toHaveLength(0);
  });

  it('keeps a self-connect pending edge out of the task-edge kind', async () => {
    const page = tasksPayload([task('t-9', 'a-2', 'a-4')]);
    const { result } = renderArchipelago(
      { agents: shuffledAgents, pendingRequests: [internalPending] },
      page,
    );
    await waitFor(() => expect(result.current.firstPageTasks).toBeDefined());
    const kinds = result.current.edges.map((e) => e.kind);
    expect(kinds).toContain('task');
    expect(kinds).toContain('pending');
  });
});

describe('useArchipelagoData - recentActivity', () => {
  it('normalizes the narrow audit feed, newest first, capped at 3', async () => {
    const changes = [
      { action: 'ws.connected', resource_id: 'a-2', created_at: '2026-10-01T03:00:00Z' },
      { action: 'ws.disconnected', resource_id: 'a-1', created_at: '2026-10-01T02:00:00Z' },
      { action: 'ws.connected', resource_id: 'a-4', created_at: '2026-10-01T01:00:00Z' },
      { action: 'ws.disconnected', resource_id: 'a-5', created_at: '2026-10-01T00:00:00Z' },
    ];
    const { result } = renderArchipelago({
      agents: shuffledAgents,
      recentChanges: changes,
    });
    await waitFor(() => expect(result.current.firstPageTasks).toBeDefined());
    expect(result.current.recentActivity).toHaveLength(3);
    expect(result.current.recentActivity.map((a) => a.action)).toEqual([
      'ws.connected',
      'ws.disconnected',
      'ws.connected',
    ]);
  });

  it('renders an empty activity list when the feed is empty or malformed', async () => {
    const { result } = renderArchipelago({
      agents: shuffledAgents,
      recentChanges: [
        null,
        { action: 42 } as unknown as ArchipelagoStatusChange,
      ] as ReadonlyArray<ArchipelagoStatusChange | null>,
    });
    await waitFor(() => expect(result.current.firstPageTasks).toBeDefined());
    expect(result.current.recentActivity).toEqual([]);
  });
});

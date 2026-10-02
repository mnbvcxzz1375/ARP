import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { RouterForTesting } from '../../../test-utils';
import ArchipelagoList from '../ArchipelagoList';
import type {
  ArchipelagoAgent,
  ArchipelagoPendingConnection,
} from '../AgentDetailPanel';

const agents: ArchipelagoAgent[] = [
  {
    agent_id: 'a1000001-0000-4000-8000-000000000001',
    agent_number: 'AN-01AA-BB01-01',
    name: 'Atlas Worker',
    runtime: 'python-sdk',
    status: 'online',
    inbound_policy: 'public',
    discoverable: true,
    capabilities: ['summarize'],
    created_at: '2026-09-30T10:00:00Z',
  },
  {
    agent_id: 'a1000001-0000-4000-8000-000000000002',
    agent_number: 'AN-02AA-BB02-02',
    name: 'Beacon Relay Bot',
    runtime: 'node-sdk',
    status: 'offline',
    inbound_policy: 'contacts_only',
    discoverable: false,
    capabilities: ['notify'],
    created_at: '2026-09-29T10:00:00Z',
  },
];

const pendingExternal: ArchipelagoPendingConnection[] = [
  {
    connection_id: 'c1000001-0000-4000-8000-000000000001',
    agent_number: 'AN-09AA-BB09-09',
    requester_agent: 'a1000001-0000-4000-8000-000000000009',
    to_agent_id: agents[1].agent_id,
    requested_policy: 'unknown',
    created_at: '2026-10-01T06:00:00Z',
  },
];

function renderList(props: Partial<React.ComponentProps<typeof ArchipelagoList>> = {}) {
  const onSelect = vi.fn();
  render(
    <RouterForTesting>
      <ArchipelagoList agents={agents} onSelect={onSelect} {...props} />
    </RouterForTesting>,
  );
  return { onSelect };
}

describe('ArchipelagoList', () => {
  it('renders one row per agent with name, number and a status chip', () => {
    renderList();
    expect(screen.getByText('Atlas Worker')).toBeInTheDocument();
    expect(screen.getByText('AN-01AA-BB01-01')).toBeInTheDocument();
    expect(screen.getByText('Beacon Relay Bot')).toBeInTheDocument();
    expect(screen.getByText('AN-02AA-BB02-02')).toBeInTheDocument();
    // Status is a text-labeled chip for both states (not color-only).
    expect(screen.getByText('Online')).toBeInTheDocument();
    expect(screen.getByText('Offline')).toBeInTheDocument();
  });

  it('selects a row and exposes the selection via aria-pressed', async () => {
    const user = userEvent.setup();
    const { onSelect } = renderList({ selectedId: agents[0].agent_id });
    const row = screen.getByRole('button', { name: /Atlas Worker/ });
    expect(row).toHaveAttribute('aria-pressed', 'true');
    // Accent solid block is the selected state (same pattern as nav).
    expect(row.className).toContain('bg-pixel-accent');

    const other = screen.getByRole('button', { name: /Beacon Relay Bot/ });
    expect(other).toHaveAttribute('aria-pressed', 'false');
    await user.click(other);
    expect(onSelect).toHaveBeenCalledWith(agents[1].agent_id);
  });

  it('links every row at the agent page', () => {
    renderList();
    expect(screen.getAllByRole('link', { name: /View agent page: / }).length).toBe(2);
    const link = screen.getAllByRole('link', { name: /View agent page: / })[0];
    expect(link).toHaveAttribute('href', `/app/agents/${agents[0].agent_id}`);
  });

  it('renders the empty state when no agent is visible', () => {
    render(
      <RouterForTesting>
        <ArchipelagoList agents={[]} />
      </RouterForTesting>,
    );
    expect(screen.getByText('No agents visible to this account.')).toBeInTheDocument();
  });

  // Pending branch A (contract revision landed): requester number joined
  // to a real target name through to_agent_id.
  it('renders pending requests with a resolved target name', () => {
    renderList({ pendingRequests: pendingExternal });
    expect(screen.getByText('AN-09AA-BB09-09')).toBeInTheDocument();
    // The arrow span and the target name span sit side by side in the
    // pending row; assert the pair via the pending row's own text.
    const pendingRow = screen.getByText('AN-09AA-BB09-09').closest('li');
    expect(pendingRow?.textContent).toContain('→');
    expect(pendingRow?.textContent).toContain('Beacon Relay Bot');
  });

  // Pending branch B (revision not landed): the target gap is stated,
  // never guessed — and the note explains why requests live in the list.
  it('states the target gap when to_agent_id is absent', () => {
    renderList({
      pendingRequests: [
        {
          connection_id: 'c1',
          agent_number: 'AN-09AA-BB09-09',
          requester_agent: 'a1000001-0000-4000-8000-000000000009',
          to_agent_id: null,
          created_at: '2026-10-01T06:00:00Z',
        },
      ],
    });
    expect(screen.getByText('target not exposed by the API')).toBeInTheDocument();
    expect(screen.getByText(/listed here rather than drawn on the map/)).toBeInTheDocument();
  });

  it('degrades an unresolvable target to its short id', () => {
    renderList({
      pendingRequests: [
        {
          connection_id: 'c2',
          agent_number: 'AN-09AA-BB09-09',
          requester_agent: 'a1000001-0000-4000-8000-000000000009',
          to_agent_id: 'b7000001-0000-4000-8000-000000000007',
          created_at: '2026-10-01T06:00:00Z',
        },
      ],
    });
    expect(screen.getByText('b7000001')).toBeInTheDocument();
  });
});

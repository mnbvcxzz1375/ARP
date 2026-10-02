import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { RouterForTesting } from '../../../test-utils';
import AgentDetailPanel, {
  type ArchipelagoAgent,
  type DetailTaskRow,
  type ArchipelagoPendingConnection,
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
    capabilities: ['summarize', 'shell.safe'],
    created_at: '2026-09-30T10:00:00Z',
  },
];

const agent = agents[0];

// The page pre-joins task endpoint names; the panel only renders them.
const tasks: DetailTaskRow[] = [
  {
    task_id: 't1000001-0000-4000-8000-000000000001',
    status: 'delivered',
    delivery_status: 'delivered',
    created_at: '2026-10-01T09:00:00Z',
    sender_name: 'Atlas Worker',
    target_name: 'Foreign Agent A',
  },
  {
    task_id: 't1000001-0000-4000-8000-000000000002',
    status: 'running',
    delivery_status: 'delivering',
    created_at: '2026-10-01T08:00:00Z',
    sender_name: 'Beacon Relay Bot',
    target_name: 'Atlas Worker',
  },
];

const pendingForAgent: ArchipelagoPendingConnection[] = [
  {
    connection_id: 'c1000001-0000-4000-8000-000000000001',
    agent_number: 'AN-03AA-BB03-03',
    requester_agent: 'a1000001-0000-4000-8000-000000000003',
    to_agent_id: agent.agent_id,
    requested_policy: 'unknown',
    created_at: '2026-10-01T06:00:00Z',
  },
];

function renderPanel(props: Partial<React.ComponentProps<typeof AgentDetailPanel>> = {}) {
  return render(
    <RouterForTesting>
      <AgentDetailPanel agent={agent} tasks={tasks} {...props} />
    </RouterForTesting>,
  );
}

describe('AgentDetailPanel', () => {
  it('prompts for a selection when no agent is selected', () => {
    render(
      <RouterForTesting>
        <AgentDetailPanel agent={null} />
      </RouterForTesting>,
    );
    expect(screen.getByText('Select an island to inspect its agent.')).toBeInTheDocument();
  });

  it('renders the identity fields of the selected agent', () => {
    renderPanel();
    // Name appears in the identity header and in the joined task rows.
    expect(screen.getAllByText('Atlas Worker').length).toBeGreaterThan(0);
    expect(screen.getByText('AN-01AA-BB01-01')).toBeInTheDocument();
    expect(screen.getByText('python-sdk')).toBeInTheDocument();
    expect(screen.getByText('public')).toBeInTheDocument();
    expect(screen.getByText('Yes')).toBeInTheDocument();
    expect(screen.getByText('summarize')).toBeInTheDocument();
    expect(screen.getByText('shell.safe')).toBeInTheDocument();
    // Online = a text-labeled chip, not a color-only dot.
    expect(screen.getByText('Online')).toBeInTheDocument();
  });

  it('links the agent page entry', () => {
    renderPanel();
    expect(screen.getByRole('link', { name: 'View agent page' })).toHaveAttribute(
      'href',
      `/app/agents/${agent.agent_id}`,
    );
  });

  it('renders the pre-joined task rows with a chip and names', () => {
    renderPanel();
    // One "View task" link per row, pointing at the task detail page.
    const links = screen.getAllByRole('link', { name: 'View task' });
    expect(links.length).toBe(2);
    expect(links[0]).toHaveAttribute(
      'href',
      '/app/tasks/t1000001-0000-4000-8000-000000000001',
    );
    expect(screen.getByText('Foreign Agent A')).toBeInTheDocument();
    expect(screen.getByText('Beacon Relay Bot')).toBeInTheDocument();
    // Delivery status renders as a text-labeled chip.
    expect(screen.getByText('Delivered')).toBeInTheDocument();
    expect(screen.getByText('Delivering')).toBeInTheDocument();
  });

  it('renders an em dash for a missing joined name instead of inventing one', () => {
    renderPanel({
      tasks: [
        {
          task_id: 't1',
          status: 'pending',
          delivery_status: 'queued',
          created_at: '2026-10-01T09:00:00Z',
          sender_name: null,
          target_name: '',
        },
      ],
    });
    expect(screen.getAllByText('—').length).toBe(2);
  });

  // Progress is a stated GAP (list API has no progress field) — the panel
  // must say so rather than render a faked percentage.
  it('states the progress gap instead of a percentage', () => {
    renderPanel();
    expect(
      screen.getByText(
        'Progress is only available on the task detail page; the list API does not return it.',
      ),
    ).toBeInTheDocument();
  });

  it('renders the pending request as requester number → this agent', () => {
    renderPanel({ pendingRequests: pendingForAgent });
    expect(screen.getByText('AN-03AA-BB03-03')).toBeInTheDocument();
    expect(screen.getByText('→ Atlas Worker')).toBeInTheDocument();
  });

  // The pending list is pre-filtered by the page on to_agent_id; an empty
  // list may also mean the pre-revision payload hides the target, so the
  // empty copy must stay honest about both possibilities.
  it('states both possibilities in the pending empty copy', () => {
    renderPanel({ pendingRequests: [] });
    expect(screen.getByText(/not exposed by the connections API/)).toBeInTheDocument();
  });

  it('hides the header for drawer composition', () => {
    const { container } = renderPanel({ showHeader: false });
    // No PanelHeader h2 (the drawer supplies its own title bar).
    expect(container.querySelector('h2')).toBeNull();
  });
});

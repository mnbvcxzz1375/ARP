import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Route, Routes } from 'react-router-dom';
import { RouterForTesting } from '../../../test-utils';
import AdminAgentDetailPage from '../AdminAgentDetailPage';

vi.mock('../../../api/client', () => ({
  default: { get: vi.fn() },
}));

import api from '../../../api/client';

const mockAgent = {
  agent_id: 'agent-001',
  agent_number: 'AN-000001',
  owner_username: 'alice',
  name: 'Admin Test Agent',
  runtime: 'node',
  status: 'online',
  inbound_policy: 'public',
  discoverable: false,
  capabilities: ['webhook', 'database'],
  token_metadata: {
    prefix: 'agt_xyz99',
    created_at: '2024-02-01T08:00:00Z',
    rotated_at: '2024-05-01T08:00:00Z',
  },
  created_at: '2024-02-01T08:00:00Z',
  updated_at: '2024-06-15T12:00:00Z',
  tasks_24h: 42,
  failed_tasks_24h: 3,
};

function renderDetail(agentId: string) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false, refetchOnWindowFocus: false },
    },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <RouterForTesting initialEntries={[`/admin/agents/${agentId}`]}>
        <Routes>
          <Route path="/admin/agents/:agentId" element={<AdminAgentDetailPage />} />
        </Routes>
      </RouterForTesting>
    </QueryClientProvider>,
  );
}

describe('AdminAgentDetailPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    (api.get as any).mockResolvedValue({ data: mockAgent });
  });

  it('renders agent detail data including owner', async () => {
    renderDetail('agent-001');

    await waitFor(() => {
      const elements = screen.getAllByText('Admin Test Agent');
      expect(elements.length).toBe(2);
    });

    expect(screen.getByText('alice')).toBeInTheDocument();
    expect(screen.getByText('AN-000001')).toBeInTheDocument();
    expect(screen.getByText('node')).toBeInTheDocument();
    expect(screen.getByText('Online')).toBeInTheDocument();
    expect(screen.getByText('public')).toBeInTheDocument();
    expect(screen.getByText('No')).toBeInTheDocument();
  });

  it('fetches the correct endpoint', async () => {
    renderDetail('agent-001');

    await waitFor(() => {
      expect(api.get).toHaveBeenCalledWith('/v1/dashboard/admin/agents/agent-001');
    });
  });

  it('shows error state on failure', async () => {
    (api.get as any).mockRejectedValue(new Error('Network error'));
    renderDetail('agent-001');

    await waitFor(() => {
      expect(screen.getByText('Failed to load agent detail')).toBeInTheDocument();
    });
  });

  it('renders back link to admin agents list', async () => {
    renderDetail('agent-001');

    await waitFor(() => {
      expect(screen.getByText('Back to Agents')).toBeInTheDocument();
    });
    const link = screen.getByText('Back to Agents').closest('a');
    expect(link).toHaveAttribute('href', '/admin/agents');
  });

  it('renders capabilities', async () => {
    renderDetail('agent-001');

    await waitFor(() => {
      expect(screen.getByText('webhook')).toBeInTheDocument();
      expect(screen.getByText('database')).toBeInTheDocument();
    });
  });

  it('renders token metadata without raw token', async () => {
    renderDetail('agent-001');

    await waitFor(() => {
      expect(screen.getByText('agt_xyz99')).toBeInTheDocument();
      expect(screen.queryByText(/agt_xyz99[A-Za-z0-9]{20,}/)).not.toBeInTheDocument();
    });
  });

  it('renders task statistics', async () => {
    renderDetail('agent-001');

    await waitFor(() => {
      expect(screen.getByText('42')).toBeInTheDocument();
      expect(screen.getByText('3')).toBeInTheDocument();
    });
  });

  it('shows rotated date when token was rotated', async () => {
    renderDetail('agent-001');

    await waitFor(() => {
      expect(screen.getByText('agt_xyz99')).toBeInTheDocument();
    });
    expect(screen.queryByText('Never')).not.toBeInTheDocument();
  });
});

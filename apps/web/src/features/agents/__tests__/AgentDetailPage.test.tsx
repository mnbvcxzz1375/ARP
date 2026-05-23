import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Route, Routes } from 'react-router-dom';
import { RouterForTesting } from '../../../test-utils';
import AgentDetailPage from '../AgentDetailPage';

vi.mock('../../../api/client', () => ({
  default: { get: vi.fn() },
}));

import api from '../../../api/client';

const mockAgent = {
  agent_id: 'agent-001',
  agent_number: 'AN-000001',
  name: 'Test Agent',
  runtime: 'python',
  status: 'online',
  inbound_policy: 'contacts_only',
  discoverable: true,
  capabilities: ['chat', 'code'],
  token_metadata: {
    prefix: 'agt_abc12',
    created_at: '2024-01-15T10:30:00Z',
    rotated_at: null,
  },
  created_at: '2024-01-15T10:00:00Z',
  updated_at: '2024-06-01T12:00:00Z',
};

function renderDetail(agentId: string) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false, refetchOnWindowFocus: false },
    },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <RouterForTesting initialEntries={[`/app/agents/${agentId}`]}>
        <Routes>
          <Route path="/app/agents/:agentId" element={<AgentDetailPage />} />
        </Routes>
      </RouterForTesting>
    </QueryClientProvider>,
  );
}

describe('AgentDetailPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    (api.get as any).mockResolvedValue({ data: mockAgent });
  });

  it('renders agent detail data', async () => {
    renderDetail('agent-001');

    await waitFor(() => {
      const elements = screen.getAllByText('Test Agent');
      expect(elements.length).toBe(2);
    });

    expect(screen.getByText('AN-000001')).toBeInTheDocument();
    expect(screen.getByText('python')).toBeInTheDocument();
    expect(screen.getByText('Online')).toBeInTheDocument();
    expect(screen.getByText('contacts_only')).toBeInTheDocument();
    expect(screen.getByText('Yes')).toBeInTheDocument();
    expect(screen.getByText('chat')).toBeInTheDocument();
    expect(screen.getByText('code')).toBeInTheDocument();
    expect(screen.getByText('agt_abc12')).toBeInTheDocument();
  });

  it('fetches the correct endpoint', async () => {
    renderDetail('agent-001');

    await waitFor(() => {
      expect(api.get).toHaveBeenCalledWith('/v1/dashboard/agents/agent-001');
    });
  });

  it('shows error state on failure', async () => {
    (api.get as any).mockRejectedValue(new Error('Network error'));
    renderDetail('agent-001');

    await waitFor(() => {
      expect(screen.getByText('Failed to load agent detail')).toBeInTheDocument();
    });
  });

  it('renders back link to agents list', async () => {
    renderDetail('agent-001');

    await waitFor(() => {
      expect(screen.getByText('Back to Agents')).toBeInTheDocument();
    });
    const link = screen.getByText('Back to Agents').closest('a');
    expect(link).toHaveAttribute('href', '/app/agents');
  });

  it('shows "Never" for never-rotated token', async () => {
    renderDetail('agent-001');

    await waitFor(() => {
      expect(screen.getByText('Never')).toBeInTheDocument();
    });
  });

  it('shows capabilities section', async () => {
    renderDetail('agent-001');

    await waitFor(() => {
      expect(screen.getByText('Capabilities')).toBeInTheDocument();
    });
  });

  it('renders discoverable field', async () => {
    renderDetail('agent-001');

    await waitFor(() => {
      expect(screen.getByText('Discoverable')).toBeInTheDocument();
      expect(screen.getByText('Yes')).toBeInTheDocument();
    });
  });

  it('shows loading state initially', () => {
    (api.get as any).mockImplementation(() => new Promise(() => {}));
    renderDetail('agent-001');
    expect(document.querySelector('.animate-spin')).toBeInTheDocument();
  });
});

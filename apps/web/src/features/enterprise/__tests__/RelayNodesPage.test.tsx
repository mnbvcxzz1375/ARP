import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import RelayNodesPage from '../RelayNodesPage';

vi.mock('../../../api/client', () => ({
  default: { get: vi.fn(), post: vi.fn(), put: vi.fn(), patch: vi.fn(), delete: vi.fn() },
}));

import api from '../../../api/client';

function renderPage() {
  const qc = new QueryClient({
    defaultOptions: {
      queries: { retry: false, refetchOnWindowFocus: false },
      mutations: { retry: false },
    },
  });
  return render(<QueryClientProvider client={qc}><RelayNodesPage /></QueryClientProvider>);
}

// Mirrors RelayNodeResponse (apps/api/app/schemas/routing.py): id / node_name
// / node_type / status / current_load / queue_depth / avg_latency_ms /
// success_rate / capabilities / max_capacity / region / zone /
// last_heartbeat_at / extra_metadata / enabled. The API exposes register +
// heartbeat only — there is no update or delete endpoint for relay nodes.
const mockNodes = [
  {
    id: 'rn-1',
    node_name: 'Central Relay A',
    node_type: 'central',
    status: 'healthy',
    current_load: 45,
    queue_depth: 3,
    avg_latency_ms: 12,
    success_rate: 98,
    region: 'us-east',
    zone: 'zone-1',
    enabled: true,
    last_heartbeat_at: '2026-05-24T12:00:00Z',
  },
  {
    id: 'rn-2',
    node_name: 'Edge Node B',
    node_type: 'edge',
    status: 'degraded',
    current_load: 80,
    queue_depth: 10,
    avg_latency_ms: 45,
    success_rate: 85,
    region: 'eu-west',
    zone: 'zone-2',
    enabled: false,
    last_heartbeat_at: '2026-05-24T11:00:00Z',
  },
];

function mockList() {
  (api.get as ReturnType<typeof vi.fn>).mockResolvedValue({
    data: { nodes: mockNodes, total: 2 },
  });
}

describe('RelayNodesPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('shows loading state initially', () => {
    (api.get as ReturnType<typeof vi.fn>).mockReturnValue(new Promise(() => {}));
    const { container } = renderPage();
    expect(container.querySelector('.animate-spin')).toBeTruthy();
  });

  it('shows error state when API fails', async () => {
    (api.get as ReturnType<typeof vi.fn>).mockRejectedValue(new Error('Network error'));
    renderPage();
    await waitFor(() => {
      expect(screen.getByText(/failed to load relay nodes/i)).toBeTruthy();
    });
  });

  it('renders relay nodes from the `nodes` list field', async () => {
    mockList();
    renderPage();
    await waitFor(() => {
      expect(screen.getByText('Central Relay A')).toBeTruthy();
      expect(screen.getByText('Edge Node B')).toBeTruthy();
    });
  });

  it('opens Add Relay Node dialog when button is clicked', async () => {
    mockList();
    renderPage();
    await waitFor(() => {
      expect(screen.getByText('Central Relay A')).toBeTruthy();
    });

    fireEvent.click(screen.getByRole('button', { name: 'Add Relay Node' }));
    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Add Relay Node' })).toBeTruthy();
      expect(screen.getByLabelText('Name')).toBeTruthy();
      expect(screen.getByLabelText('Node Type')).toBeTruthy();
      expect(screen.getByLabelText('Region')).toBeTruthy();
      expect(screen.getByLabelText('Zone')).toBeTruthy();
      expect(screen.getByLabelText('Max Capacity')).toBeTruthy();
      expect(screen.getByLabelText('Capabilities (comma-separated)')).toBeTruthy();
    });
  });

  it('calls register POST API when dialog is submitted', async () => {
    mockList();
    (api.post as ReturnType<typeof vi.fn>).mockResolvedValue({ data: {} });
    renderPage();
    await waitFor(() => {
      expect(screen.getByText('Central Relay A')).toBeTruthy();
    });

    fireEvent.click(screen.getByRole('button', { name: 'Add Relay Node' }));
    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Add Relay Node' })).toBeTruthy();
    });

    fireEvent.change(screen.getByLabelText('Name'), { target: { value: 'New Node' } });
    fireEvent.change(screen.getByLabelText('Region'), { target: { value: 'ap-southeast' } });
    fireEvent.change(screen.getByLabelText('Zone'), { target: { value: 'zone-3' } });
    fireEvent.click(screen.getByRole('button', { name: 'Submit' }));

    await waitFor(() => {
      expect(api.post).toHaveBeenCalledWith('/v1/relay-nodes/register', {
        node_name: 'New Node',
        node_type: 'central',
        capabilities: ['task_delivery'],
        region: 'ap-southeast',
        zone: 'zone-3',
      });
    });
  });

  it('splits capabilities on commas and omits blank optional fields', async () => {
    mockList();
    (api.post as ReturnType<typeof vi.fn>).mockResolvedValue({ data: {} });
    renderPage();
    await waitFor(() => {
      expect(screen.getByText('Central Relay A')).toBeTruthy();
    });

    fireEvent.click(screen.getByRole('button', { name: 'Add Relay Node' }));
    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Add Relay Node' })).toBeTruthy();
    });

    fireEvent.change(screen.getByLabelText('Name'), { target: { value: 'Caps Node' } });
    fireEvent.change(screen.getByLabelText('Capabilities (comma-separated)'), {
      target: { value: 'task_delivery, file_transfer ,  ' },
    });
    fireEvent.change(screen.getByLabelText('Max Capacity'), { target: { value: '42' } });
    fireEvent.click(screen.getByRole('button', { name: 'Submit' }));

    await waitFor(() => {
      expect(api.post).toHaveBeenCalledWith('/v1/relay-nodes/register', {
        node_name: 'Caps Node',
        node_type: 'central',
        capabilities: ['task_delivery', 'file_transfer'],
        max_capacity: 42,
      });
    });
  });
});

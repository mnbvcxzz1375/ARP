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

const mockNodes = [
  {
    node_id: 'rn-1',
    node_name: 'Central Relay A',
    node_type: 'central_relay',
    status: 'healthy',
    current_load: 45,
    queue_depth: 3,
    avg_latency_ms: 12,
    success_rate: 98,
    region: 'us-east',
    zone: 'zone-1',
    enabled: true,
    endpoint: 'wss://relay.example.com',
    capacity: 100,
    last_heartbeat_at: '2026-05-24T12:00:00Z',
  },
  {
    node_id: 'rn-2',
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
    endpoint: 'wss://edge.example.com',
    capacity: 50,
    last_heartbeat_at: '2026-05-24T11:00:00Z',
  },
];

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

  it('renders relay nodes from API', async () => {
    (api.get as ReturnType<typeof vi.fn>).mockResolvedValue({
      data: { relay_nodes: mockNodes, total: 2 },
    });
    renderPage();
    await waitFor(() => {
      expect(screen.getByText('Central Relay A')).toBeTruthy();
      expect(screen.getByText('Edge Node B')).toBeTruthy();
    });
  });

  it('opens Add Relay Node dialog when button is clicked', async () => {
    (api.get as ReturnType<typeof vi.fn>).mockResolvedValue({
      data: { relay_nodes: mockNodes, total: 2 },
    });
    renderPage();
    await waitFor(() => {
      expect(screen.getByText('Central Relay A')).toBeTruthy();
    });

    fireEvent.click(screen.getByRole('button', { name: 'Add Relay Node' }));
    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Add Relay Node' })).toBeTruthy();
      expect(screen.getByLabelText('Name')).toBeTruthy();
      expect(screen.getByLabelText('Endpoint')).toBeTruthy();
      expect(screen.getByLabelText('Zone')).toBeTruthy();
      expect(screen.getByLabelText('Relay Type')).toBeTruthy();
      expect(screen.getByLabelText('Capacity')).toBeTruthy();
    });
  });

  it('calls POST API when dialog is submitted', async () => {
    (api.get as ReturnType<typeof vi.fn>).mockResolvedValue({
      data: { relay_nodes: mockNodes, total: 2 },
    });
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
    fireEvent.change(screen.getByLabelText('Endpoint'), { target: { value: 'wss://new.example.com' } });
    fireEvent.change(screen.getByLabelText('Zone'), { target: { value: 'zone-3' } });
    fireEvent.click(screen.getByRole('button', { name: 'Submit' }));

    await waitFor(() => {
      expect(api.post).toHaveBeenCalledWith('/v1/routes/relay-nodes', {
        name: 'New Node',
        endpoint: 'wss://new.example.com',
        zone: 'zone-3',
        relay_type: 'central_relay',
        capacity: undefined,
      });
    });
  });

  it('opens ConfirmDialog when Delete is clicked and calls DELETE on confirm', async () => {
    (api.get as ReturnType<typeof vi.fn>).mockResolvedValue({
      data: { relay_nodes: mockNodes, total: 2 },
    });
    (api.delete as ReturnType<typeof vi.fn>).mockResolvedValue({ data: {} });
    renderPage();
    await waitFor(() => {
      expect(screen.getByText('Central Relay A')).toBeTruthy();
    });

    // Click Delete on first row
    const deleteButtons = screen.getAllByText('Delete');
    fireEvent.click(deleteButtons[0]);

    await waitFor(() => {
      expect(screen.getByText('Delete Relay Node')).toBeTruthy();
      expect(screen.getByText(/are you sure you want to delete/i)).toBeTruthy();
    });

    // Confirm delete
    const confirmButtons = screen.getAllByText('Delete');
    // The last Delete button is the confirm button in the dialog
    fireEvent.click(confirmButtons[confirmButtons.length - 1]);

    await waitFor(() => {
      expect(api.delete).toHaveBeenCalledWith('/v1/routes/relay-nodes/rn-1');
    });
  });

  it('opens Edit dialog pre-filled with existing data', async () => {
    (api.get as ReturnType<typeof vi.fn>).mockResolvedValue({
      data: { relay_nodes: mockNodes, total: 2 },
    });
    (api.put as ReturnType<typeof vi.fn>).mockResolvedValue({ data: {} });
    renderPage();
    await waitFor(() => {
      expect(screen.getByText('Central Relay A')).toBeTruthy();
    });

    // Click Edit on first row
    const editButtons = screen.getAllByText('Edit');
    fireEvent.click(editButtons[0]);

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Edit Relay Node' })).toBeTruthy();
      expect((screen.getByLabelText('Name') as HTMLInputElement).value).toBe('Central Relay A');
      expect((screen.getByLabelText('Endpoint') as HTMLInputElement).value).toBe('wss://relay.example.com');
      expect((screen.getByLabelText('Zone') as HTMLInputElement).value).toBe('zone-1');
    });
  });

  it('calls PUT API when edit dialog is submitted', async () => {
    (api.get as ReturnType<typeof vi.fn>).mockResolvedValue({
      data: { relay_nodes: mockNodes, total: 2 },
    });
    (api.put as ReturnType<typeof vi.fn>).mockResolvedValue({ data: {} });
    renderPage();
    await waitFor(() => {
      expect(screen.getByText('Central Relay A')).toBeTruthy();
    });

    // Open edit dialog
    const editButtons = screen.getAllByText('Edit');
    fireEvent.click(editButtons[0]);

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Edit Relay Node' })).toBeTruthy();
    });

    // Modify name
    fireEvent.change(screen.getByLabelText('Name'), { target: { value: 'Updated Node' } });
    fireEvent.click(screen.getByRole('button', { name: 'Submit' }));

    await waitFor(() => {
      expect(api.put).toHaveBeenCalledWith('/v1/routes/relay-nodes/rn-1', expect.objectContaining({
        name: 'Updated Node',
      }));
    });
  });
});
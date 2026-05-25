import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import DedicatedChannelsPage from '../DedicatedChannelsPage';

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
  return render(<QueryClientProvider client={qc}><DedicatedChannelsPage /></QueryClientProvider>);
}

const mockChannels = [
  {
    channel_id: 'dc-1',
    name: 'Kafka Channel',
    channel_type: 'kafka',
    status: 'healthy',
    target_agent_id: 'agent-12345678-abcd',
    config: { bootstrap_servers: 'kafka:9092', topic: 'events' },
    last_health_check: '2026-05-24T12:00:00Z',
    created_at: '2026-05-24T10:00:00Z',
  },
  {
    channel_id: 'dc-2',
    name: 'gRPC Channel',
    channel_type: 'grpc',
    status: 'degraded',
    target_agent_id: 'agent-87654321-efgh',
    config: { endpoint: 'grpc://grpc.example.com:443' },
    last_health_check: '2026-05-24T11:00:00Z',
    created_at: '2026-05-24T09:00:00Z',
  },
];

describe('DedicatedChannelsPage', () => {
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
      expect(screen.getByText(/failed to load dedicated channels/i)).toBeTruthy();
    });
  });

  it('renders channels from API', async () => {
    (api.get as ReturnType<typeof vi.fn>).mockResolvedValue({
      data: { channels: mockChannels, total: 2 },
    });
    renderPage();
    await waitFor(() => {
      expect(screen.getByText('Kafka Channel')).toBeTruthy();
      expect(screen.getByText('gRPC Channel')).toBeTruthy();
    });
  });

  it('opens Add Channel dialog when button is clicked', async () => {
    (api.get as ReturnType<typeof vi.fn>).mockResolvedValue({
      data: { channels: mockChannels, total: 2 },
    });
    renderPage();
    await waitFor(() => {
      expect(screen.getByText('Kafka Channel')).toBeTruthy();
    });

    fireEvent.click(screen.getByText('Add Channel'));
    await waitFor(() => {
      expect(screen.getByText('Add Channel')).toBeTruthy(); // dialog title
      expect(screen.getByLabelText('Name')).toBeTruthy();
      expect(screen.getByLabelText('Target Agent ID')).toBeTruthy();
      expect(screen.getByLabelText('Channel Type')).toBeTruthy();
      expect(screen.getByLabelText('Config (JSON)')).toBeTruthy();
    });
  });

  it('calls POST API when dialog is submitted', async () => {
    (api.get as ReturnType<typeof vi.fn>).mockResolvedValue({
      data: { channels: mockChannels, total: 2 },
    });
    (api.post as ReturnType<typeof vi.fn>).mockResolvedValue({ data: {} });
    renderPage();
    await waitFor(() => {
      expect(screen.getByText('Kafka Channel')).toBeTruthy();
    });

    fireEvent.click(screen.getByText('Add Channel'));
    await waitFor(() => {
      expect(screen.getByText('Add Channel')).toBeTruthy(); // dialog title
    });

    fireEvent.change(screen.getByLabelText('Name'), { target: { value: 'New Channel' } });
    fireEvent.change(screen.getByLabelText('Target Agent ID'), { target: { value: 'agent-new' } });
    fireEvent.change(screen.getByLabelText('Config (JSON)'), {
      target: { value: '{"endpoint": "kafka:9093"}' },
    });
    fireEvent.click(screen.getByText('Submit'));

    await waitFor(() => {
      expect(api.post).toHaveBeenCalledWith('/v1/egress/dedicated-channels', {
        name: 'New Channel',
        target_agent_id: 'agent-new',
        channel_type: 'kafka',
        config: { endpoint: 'kafka:9093' },
      });
    });
  });

  it('opens ConfirmDialog when Delete is clicked and calls DELETE on confirm', async () => {
    (api.get as ReturnType<typeof vi.fn>).mockResolvedValue({
      data: { channels: mockChannels, total: 2 },
    });
    (api.delete as ReturnType<typeof vi.fn>).mockResolvedValue({ data: {} });
    renderPage();
    await waitFor(() => {
      expect(screen.getByText('Kafka Channel')).toBeTruthy();
    });

    // Click Delete on first row
    const deleteButtons = screen.getAllByText('Delete');
    fireEvent.click(deleteButtons[0]);

    await waitFor(() => {
      expect(screen.getByText('Delete Dedicated Channel')).toBeTruthy();
      expect(screen.getByText(/are you sure you want to delete/i)).toBeTruthy();
    });

    // Confirm delete
    const confirmButtons = screen.getAllByText('Delete');
    fireEvent.click(confirmButtons[confirmButtons.length - 1]);

    await waitFor(() => {
      expect(api.delete).toHaveBeenCalledWith('/v1/egress/dedicated-channels/dc-1');
    });
  });

  it('calls POST health-check API when Health Check button is clicked', async () => {
    (api.get as ReturnType<typeof vi.fn>).mockResolvedValue({
      data: { channels: mockChannels, total: 2 },
    });
    (api.post as ReturnType<typeof vi.fn>).mockResolvedValue({ data: {} });
    renderPage();
    await waitFor(() => {
      expect(screen.getByText('Kafka Channel')).toBeTruthy();
    });

    // Click Health Check on first row
    const healthButtons = screen.getAllByText('Health Check');
    fireEvent.click(healthButtons[0]);

    await waitFor(() => {
      expect(api.post).toHaveBeenCalledWith('/v1/egress/dedicated-channels/dc-1/health-check');
    });
  });

  it('opens Edit dialog pre-filled with existing data', async () => {
    (api.get as ReturnType<typeof vi.fn>).mockResolvedValue({
      data: { channels: mockChannels, total: 2 },
    });
    (api.put as ReturnType<typeof vi.fn>).mockResolvedValue({ data: {} });
    renderPage();
    await waitFor(() => {
      expect(screen.getByText('Kafka Channel')).toBeTruthy();
    });

    const editButtons = screen.getAllByText('Edit');
    fireEvent.click(editButtons[0]);

    await waitFor(() => {
      expect(screen.getByText('Edit Dedicated Channel')).toBeTruthy();
      expect((screen.getByLabelText('Name') as HTMLInputElement).value).toBe('Kafka Channel');
      expect((screen.getByLabelText('Target Agent ID') as HTMLInputElement).value).toBe('agent-12345678-abcd');
    });
  });

  it('shows form error when config is not valid JSON', async () => {
    (api.get as ReturnType<typeof vi.fn>).mockResolvedValue({
      data: { channels: mockChannels, total: 2 },
    });
    renderPage();
    await waitFor(() => {
      expect(screen.getByText('Kafka Channel')).toBeTruthy();
    });

    fireEvent.click(screen.getByText('Add Channel'));
    await waitFor(() => {
      expect(screen.getByText('Add Channel')).toBeTruthy(); // dialog title
    });

    fireEvent.change(screen.getByLabelText('Config (JSON)'), {
      target: { value: 'not-valid-json' },
    });
    fireEvent.click(screen.getByText('Submit'));

    await waitFor(() => {
      expect(screen.getByText('Config must be valid JSON')).toBeTruthy();
    });
  });
});
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import DedicatedChannelsPage from '../DedicatedChannelsPage';

vi.mock('../../../api/client', () => ({
  default: { get: vi.fn(), post: vi.fn(), put: vi.fn(), patch: vi.fn(), delete: vi.fn() },
}));

vi.mock('../../../hooks/useAuth', () => ({
  useAuth: vi.fn(),
}));

import api from '../../../api/client';
import { useAuth } from '../../../hooks/useAuth';

function renderPage() {
  const qc = new QueryClient({
    defaultOptions: {
      queries: { retry: false, refetchOnWindowFocus: false },
      mutations: { retry: false },
    },
  });
  return render(<QueryClientProvider client={qc}><DedicatedChannelsPage /></QueryClientProvider>);
}

/** Every channel write is behind require_high_risk("super_admin:write");
 * the default mock is stepped-up so the write paths run directly. */
function mockSuperAdmin(stepUp: string | null = '2999-01-01T00:00:00Z') {
  (useAuth as any).mockReturnValue({
    data: {
      user_id: 'u-admin',
      username: 'admin',
      role: 'super_admin',
      step_up_until: stepUp,
    },
  });
}

// Mirrors DedicatedChannelResponse (apps/api/app/schemas/dedicated_channel.py):
// id / channel_name / channel_type / source_agent_id / target_agent_id /
// connection_config / encryption_config / bandwidth_mbps / latency_target_ms
// / enabled / created_at / updated_at. There is no `status` field.
const mockChannels = [
  {
    id: 'dc-1',
    channel_name: 'VPN Channel Alpha',
    channel_type: 'vpn',
    source_agent_id: 'agent-12345678-abcd',
    target_agent_id: 'agent-87654321-efgh',
    connection_config: { endpoint: 'vpn-edge-1.internal:51820' },
    encryption_config: { algorithm: 'aes-256-gcm' },
    bandwidth_mbps: 100,
    latency_target_ms: 20,
    enabled: true,
    created_at: '2026-05-24T10:00:00Z',
    updated_at: '2026-05-24T10:00:00Z',
  },
  {
    id: 'dc-2',
    channel_name: 'Private Link Beta',
    channel_type: 'private_link',
    source_agent_id: 'agent-00000000-0000',
    target_agent_id: 'agent-11111111-1111',
    connection_config: { endpoint: 'pls-2.internal' },
    encryption_config: null,
    bandwidth_mbps: null,
    latency_target_ms: null,
    enabled: false,
    created_at: '2026-05-24T09:00:00Z',
    updated_at: '2026-05-24T09:00:00Z',
  },
];

describe('DedicatedChannelsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockSuperAdmin();
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
      expect(screen.getByText('VPN Channel Alpha')).toBeTruthy();
      expect(screen.getByText('Private Link Beta')).toBeTruthy();
    });
  });

  it('opens Add Channel dialog when button is clicked', async () => {
    (api.get as ReturnType<typeof vi.fn>).mockResolvedValue({
      data: { channels: mockChannels, total: 2 },
    });
    renderPage();
    await waitFor(() => {
      expect(screen.getByText('VPN Channel Alpha')).toBeTruthy();
    });

    fireEvent.click(screen.getByText('Add Channel'));
    await waitFor(() => {
      expect(screen.getByText('Add Dedicated Channel')).toBeTruthy();
      expect(screen.getByLabelText('Name')).toBeTruthy();
      expect(screen.getByLabelText('Source Agent ID')).toBeTruthy();
      expect(screen.getByLabelText('Target Agent ID')).toBeTruthy();
      expect(screen.getByLabelText('Channel Type')).toBeTruthy();
      expect(screen.getByLabelText('Connection Config (JSON)')).toBeTruthy();
      expect(screen.getByLabelText('Encryption Config (JSON, optional)')).toBeTruthy();
      expect(screen.getByLabelText('Bandwidth (Mbps)')).toBeTruthy();
      expect(screen.getByLabelText('Latency Target (ms)')).toBeTruthy();
    });
  });

  it('calls POST API when dialog is submitted', async () => {
    (api.get as ReturnType<typeof vi.fn>).mockResolvedValue({
      data: { channels: mockChannels, total: 2 },
    });
    (api.post as ReturnType<typeof vi.fn>).mockResolvedValue({ data: {} });
    renderPage();
    await waitFor(() => {
      expect(screen.getByText('VPN Channel Alpha')).toBeTruthy();
    });

    fireEvent.click(screen.getByText('Add Channel'));
    await waitFor(() => {
      expect(screen.getByText('Add Dedicated Channel')).toBeTruthy();
    });

    fireEvent.change(screen.getByLabelText('Name'), { target: { value: 'New Channel' } });
    fireEvent.change(screen.getByLabelText('Source Agent ID'), { target: { value: 'agent-src' } });
    fireEvent.change(screen.getByLabelText('Target Agent ID'), { target: { value: 'agent-new' } });
    fireEvent.change(screen.getByLabelText('Connection Config (JSON)'), {
      target: { value: '{"endpoint": "vpn-edge-2.internal:51820"}' },
    });
    fireEvent.click(screen.getByText('Submit'));

    await waitFor(() => {
      expect(api.post).toHaveBeenCalledWith('/v1/dashboard/admin/dedicated-channels', {
        channel_name: 'New Channel',
        channel_type: 'vpn',
        source_agent_id: 'agent-src',
        target_agent_id: 'agent-new',
        connection_config: { endpoint: 'vpn-edge-2.internal:51820' },
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
      expect(screen.getByText('VPN Channel Alpha')).toBeTruthy();
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
      expect(api.delete).toHaveBeenCalledWith('/v1/dashboard/admin/dedicated-channels/dc-1');
    });
  });

  it('calls POST health-check API when Health Check button is clicked', async () => {
    (api.get as ReturnType<typeof vi.fn>).mockResolvedValue({
      data: { channels: mockChannels, total: 2 },
    });
    (api.post as ReturnType<typeof vi.fn>).mockResolvedValue({ data: {} });
    renderPage();
    await waitFor(() => {
      expect(screen.getByText('VPN Channel Alpha')).toBeTruthy();
    });

    // Click Health Check on first row
    const healthButtons = screen.getAllByText('Health Check');
    fireEvent.click(healthButtons[0]);

    await waitFor(() => {
      expect(api.post).toHaveBeenCalledWith('/v1/dashboard/admin/dedicated-channels/dc-1/health-check');
    });
  });

  it('opens Edit dialog pre-filled with existing data', async () => {
    (api.get as ReturnType<typeof vi.fn>).mockResolvedValue({
      data: { channels: mockChannels, total: 2 },
    });
    (api.patch as ReturnType<typeof vi.fn>).mockResolvedValue({ data: {} });
    renderPage();
    await waitFor(() => {
      expect(screen.getByText('VPN Channel Alpha')).toBeTruthy();
    });

    const editButtons = screen.getAllByText('Edit');
    fireEvent.click(editButtons[0]);

    await waitFor(() => {
      expect(screen.getByText('Edit Dedicated Channel')).toBeTruthy();
      expect((screen.getByLabelText('Name') as HTMLInputElement).value).toBe('VPN Channel Alpha');
      expect((screen.getByLabelText('Source Agent ID') as HTMLInputElement).value).toBe(
        'agent-12345678-abcd',
      );
      expect((screen.getByLabelText('Target Agent ID') as HTMLInputElement).value).toBe(
        'agent-87654321-efgh',
      );
    });
  });

  it('shows form error when config is not valid JSON', async () => {
    (api.get as ReturnType<typeof vi.fn>).mockResolvedValue({
      data: { channels: mockChannels, total: 2 },
    });
    renderPage();
    await waitFor(() => {
      expect(screen.getByText('VPN Channel Alpha')).toBeTruthy();
    });

    fireEvent.click(screen.getByText('Add Channel'));
    await waitFor(() => {
      expect(screen.getByText('Add Dedicated Channel')).toBeTruthy();
    });

    fireEvent.change(screen.getByLabelText('Connection Config (JSON)'), {
      target: { value: 'not-valid-json' },
    });
    fireEvent.click(screen.getByText('Submit'));

    await waitFor(() => {
      expect(screen.getByText('Config must be valid JSON')).toBeTruthy();
    });
  });
});
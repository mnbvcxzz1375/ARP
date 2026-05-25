import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import EgressGatewaysPage from '../EgressGatewaysPage';

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
  return render(<QueryClientProvider client={qc}><EgressGatewaysPage /></QueryClientProvider>);
}

const mockGateways = [
  {
    gateway_id: 'eg-1',
    name: 'Primary Gateway',
    endpoint: 'https://gw.example.com',
    protocol: 'https',
    enabled: true,
    allowed_domains: ['api.example.com', 'cdn.example.com'],
    created_at: '2026-05-24T12:00:00Z',
  },
  {
    gateway_id: 'eg-2',
    name: 'SOCKS5 Proxy',
    endpoint: 'socks5://proxy.example.com:1080',
    protocol: 'socks5',
    enabled: false,
    allowed_domains: [],
    created_at: '2026-05-24T11:00:00Z',
  },
];

describe('EgressGatewaysPage', () => {
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
      expect(screen.getByText(/failed to load egress gateways/i)).toBeTruthy();
    });
  });

  it('renders gateways from API', async () => {
    (api.get as ReturnType<typeof vi.fn>).mockResolvedValue({
      data: { gateways: mockGateways, total: 2 },
    });
    renderPage();
    await waitFor(() => {
      expect(screen.getByText('Primary Gateway')).toBeTruthy();
      expect(screen.getByText('SOCKS5 Proxy')).toBeTruthy();
    });
  });

  it('opens Add Gateway dialog when button is clicked', async () => {
    (api.get as ReturnType<typeof vi.fn>).mockResolvedValue({
      data: { gateways: mockGateways, total: 2 },
    });
    renderPage();
    await waitFor(() => {
      expect(screen.getByText('Primary Gateway')).toBeTruthy();
    });

    fireEvent.click(screen.getByText('Add Gateway'));
    await waitFor(() => {
      expect(screen.getByText('Add Gateway')).toBeTruthy(); // dialog title
      expect(screen.getByLabelText('Name')).toBeTruthy();
      expect(screen.getByLabelText('Endpoint')).toBeTruthy();
      expect(screen.getByLabelText('Protocol')).toBeTruthy();
    });
  });

  it('calls POST API when dialog is submitted', async () => {
    (api.get as ReturnType<typeof vi.fn>).mockResolvedValue({
      data: { gateways: mockGateways, total: 2 },
    });
    (api.post as ReturnType<typeof vi.fn>).mockResolvedValue({ data: {} });
    renderPage();
    await waitFor(() => {
      expect(screen.getByText('Primary Gateway')).toBeTruthy();
    });

    fireEvent.click(screen.getByText('Add Gateway'));
    await waitFor(() => {
      expect(screen.getByText('Add Gateway')).toBeTruthy(); // dialog title
    });

    fireEvent.change(screen.getByLabelText('Name'), { target: { value: 'New Gateway' } });
    fireEvent.change(screen.getByLabelText('Endpoint'), { target: { value: 'https://new.example.com' } });
    fireEvent.change(screen.getByLabelText('Allowed Domains (comma-separated)'), {
      target: { value: 'api.test.com, cdn.test.com' },
    });
    fireEvent.click(screen.getByText('Submit'));

    await waitFor(() => {
      expect(api.post).toHaveBeenCalledWith('/v1/egress/gateways', {
        name: 'New Gateway',
        endpoint: 'https://new.example.com',
        protocol: 'https',
        enabled: true,
        allowed_domains: ['api.test.com', 'cdn.test.com'],
      });
    });
  });

  it('opens ConfirmDialog when Delete is clicked and calls DELETE on confirm', async () => {
    (api.get as ReturnType<typeof vi.fn>).mockResolvedValue({
      data: { gateways: mockGateways, total: 2 },
    });
    (api.delete as ReturnType<typeof vi.fn>).mockResolvedValue({ data: {} });
    renderPage();
    await waitFor(() => {
      expect(screen.getByText('Primary Gateway')).toBeTruthy();
    });

    // Click Delete on first row
    const deleteButtons = screen.getAllByText('Delete');
    fireEvent.click(deleteButtons[0]);

    await waitFor(() => {
      expect(screen.getByText('Delete Egress Gateway')).toBeTruthy();
      expect(screen.getByText(/are you sure you want to delete/i)).toBeTruthy();
    });

    // Confirm delete
    const confirmButtons = screen.getAllByText('Delete');
    fireEvent.click(confirmButtons[confirmButtons.length - 1]);

    await waitFor(() => {
      expect(api.delete).toHaveBeenCalledWith('/v1/egress/gateways/eg-1');
    });
  });

  it('calls PATCH API when enabled toggle is clicked', async () => {
    (api.get as ReturnType<typeof vi.fn>).mockResolvedValue({
      data: { gateways: mockGateways, total: 2 },
    });
    (api.patch as ReturnType<typeof vi.fn>).mockResolvedValue({ data: {} });
    renderPage();
    await waitFor(() => {
      expect(screen.getByText('Primary Gateway')).toBeTruthy();
    });

    // Find the enabled toggle (button showing "Yes" for the enabled gateway)
    const yesButtons = screen.getAllByText('Yes');
    fireEvent.click(yesButtons[0]);

    await waitFor(() => {
      expect(api.patch).toHaveBeenCalledWith('/v1/egress/gateways/eg-1', { enabled: false });
    });
  });

  it('opens Edit dialog pre-filled with existing data', async () => {
    (api.get as ReturnType<typeof vi.fn>).mockResolvedValue({
      data: { gateways: mockGateways, total: 2 },
    });
    (api.put as ReturnType<typeof vi.fn>).mockResolvedValue({ data: {} });
    renderPage();
    await waitFor(() => {
      expect(screen.getByText('Primary Gateway')).toBeTruthy();
    });

    const editButtons = screen.getAllByText('Edit');
    fireEvent.click(editButtons[0]);

    await waitFor(() => {
      expect(screen.getByText('Edit Egress Gateway')).toBeTruthy();
      expect((screen.getByLabelText('Name') as HTMLInputElement).value).toBe('Primary Gateway');
      expect((screen.getByLabelText('Endpoint') as HTMLInputElement).value).toBe('https://gw.example.com');
    });
  });
});
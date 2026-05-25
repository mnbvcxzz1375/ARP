import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import RoutePoliciesPage from '../RoutePoliciesPage';

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
  return render(<QueryClientProvider client={qc}><RoutePoliciesPage /></QueryClientProvider>);
}

const mockPolicies = [
  {
    policy_id: 'rp-1',
    name: 'US to EU Policy',
    source_zone: 'us-east',
    dest_zone: 'eu-west',
    priority: 10,
    relay_type_preference: 'central_relay',
    enabled: true,
    created_at: '2026-05-24T12:00:00Z',
  },
  {
    policy_id: 'rp-2',
    name: 'Internal Policy',
    source_zone: 'zone-1',
    dest_zone: 'zone-2',
    priority: 5,
    relay_type_preference: 'edge',
    enabled: false,
    created_at: '2026-05-24T11:00:00Z',
  },
];

describe('RoutePoliciesPage', () => {
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
      expect(screen.getByText(/failed to load route policies/i)).toBeTruthy();
    });
  });

  it('renders policies from API', async () => {
    (api.get as ReturnType<typeof vi.fn>).mockResolvedValue({
      data: { policies: mockPolicies, total: 2 },
    });
    renderPage();
    await waitFor(() => {
      expect(screen.getByText('US to EU Policy')).toBeTruthy();
      expect(screen.getByText('Internal Policy')).toBeTruthy();
    });
  });

  it('opens Add Policy dialog when button is clicked', async () => {
    (api.get as ReturnType<typeof vi.fn>).mockResolvedValue({
      data: { policies: mockPolicies, total: 2 },
    });
    renderPage();
    await waitFor(() => {
      expect(screen.getByText('US to EU Policy')).toBeTruthy();
    });

    fireEvent.click(screen.getByText('Add Policy'));
    await waitFor(() => {
      expect(screen.getByText('Add Policy')).toBeTruthy(); // dialog title
      expect(screen.getByLabelText('Name')).toBeTruthy();
      expect(screen.getByLabelText('Source Zone')).toBeTruthy();
      expect(screen.getByLabelText('Dest Zone')).toBeTruthy();
      expect(screen.getByLabelText('Priority')).toBeTruthy();
      expect(screen.getByLabelText('Relay Type Preference')).toBeTruthy();
    });
  });

  it('calls POST API when dialog is submitted', async () => {
    (api.get as ReturnType<typeof vi.fn>).mockResolvedValue({
      data: { policies: mockPolicies, total: 2 },
    });
    (api.post as ReturnType<typeof vi.fn>).mockResolvedValue({ data: {} });
    renderPage();
    await waitFor(() => {
      expect(screen.getByText('US to EU Policy')).toBeTruthy();
    });

    fireEvent.click(screen.getByText('Add Policy'));
    await waitFor(() => {
      expect(screen.getByText('Add Policy')).toBeTruthy(); // dialog title
    });

    fireEvent.change(screen.getByLabelText('Name'), { target: { value: 'New Policy' } });
    fireEvent.change(screen.getByLabelText('Source Zone'), { target: { value: 'zone-a' } });
    fireEvent.change(screen.getByLabelText('Dest Zone'), { target: { value: 'zone-b' } });
    fireEvent.click(screen.getByText('Submit'));

    await waitFor(() => {
      expect(api.post).toHaveBeenCalledWith('/v1/routes/policies', {
        name: 'New Policy',
        source_zone: 'zone-a',
        dest_zone: 'zone-b',
        priority: undefined,
        relay_type_preference: 'central_relay',
        enabled: true,
      });
    });
  });

  it('opens ConfirmDialog when Delete is clicked and calls DELETE on confirm', async () => {
    (api.get as ReturnType<typeof vi.fn>).mockResolvedValue({
      data: { policies: mockPolicies, total: 2 },
    });
    (api.delete as ReturnType<typeof vi.fn>).mockResolvedValue({ data: {} });
    renderPage();
    await waitFor(() => {
      expect(screen.getByText('US to EU Policy')).toBeTruthy();
    });

    // Click Delete on first row
    const deleteButtons = screen.getAllByText('Delete');
    fireEvent.click(deleteButtons[0]);

    await waitFor(() => {
      expect(screen.getByText('Delete Route Policy')).toBeTruthy();
      expect(screen.getByText(/are you sure you want to delete/i)).toBeTruthy();
    });

    // Confirm delete
    const confirmButtons = screen.getAllByText('Delete');
    fireEvent.click(confirmButtons[confirmButtons.length - 1]);

    await waitFor(() => {
      expect(api.delete).toHaveBeenCalledWith('/v1/routes/policies/rp-1');
    });
  });

  it('calls PATCH API when enabled toggle is clicked', async () => {
    (api.get as ReturnType<typeof vi.fn>).mockResolvedValue({
      data: { policies: mockPolicies, total: 2 },
    });
    (api.patch as ReturnType<typeof vi.fn>).mockResolvedValue({ data: {} });
    renderPage();
    await waitFor(() => {
      expect(screen.getByText('US to EU Policy')).toBeTruthy();
    });

    // Find the enabled toggle (button showing "Yes" for the enabled policy)
    const yesButtons = screen.getAllByText('Yes');
    fireEvent.click(yesButtons[0]);

    await waitFor(() => {
      expect(api.patch).toHaveBeenCalledWith('/v1/routes/policies/rp-1', { enabled: false });
    });
  });

  it('opens Edit dialog pre-filled with existing data', async () => {
    (api.get as ReturnType<typeof vi.fn>).mockResolvedValue({
      data: { policies: mockPolicies, total: 2 },
    });
    (api.put as ReturnType<typeof vi.fn>).mockResolvedValue({ data: {} });
    renderPage();
    await waitFor(() => {
      expect(screen.getByText('US to EU Policy')).toBeTruthy();
    });

    const editButtons = screen.getAllByText('Edit');
    fireEvent.click(editButtons[0]);

    await waitFor(() => {
      expect(screen.getByText('Edit Route Policy')).toBeTruthy();
      expect((screen.getByLabelText('Name') as HTMLInputElement).value).toBe('US to EU Policy');
      expect((screen.getByLabelText('Source Zone') as HTMLInputElement).value).toBe('us-east');
      expect((screen.getByLabelText('Dest Zone') as HTMLInputElement).value).toBe('eu-west');
    });
  });
});
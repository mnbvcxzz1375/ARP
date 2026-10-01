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

// Mirrors RoutePolicyResponse (apps/api/app/schemas/route_policy.py):
// id / policy_name / description / priority / scope_id / source_zone_id /
// target_zone_id / allowed_route_types / denied_route_types /
// require_approval / risk_level / data_boundary_rules / enabled. The API
// exposes POST + PATCH only — there is no PUT and no DELETE.
const mockPolicies = [
  {
    id: 'rp-1',
    policy_name: 'Deny Personal Edge',
    description: 'Personal edge relays never carry enterprise traffic.',
    priority: 10,
    scope_id: null,
    source_zone_id: null,
    target_zone_id: null,
    allowed_route_types: null,
    denied_route_types: ['personal_edge'],
    require_approval: false,
    risk_level: 'low',
    data_boundary_rules: null,
    enabled: true,
    created_at: '2026-05-24T12:00:00Z',
    updated_at: '2026-05-24T12:00:00Z',
  },
  {
    id: 'rp-2',
    policy_name: 'Central Relay Default',
    description: null,
    priority: 50,
    scope_id: null,
    source_zone_id: 'z1000001-0000-4000-8000-000000000002',
    target_zone_id: null,
    allowed_route_types: ['central_relay'],
    denied_route_types: null,
    require_approval: false,
    risk_level: 'medium',
    data_boundary_rules: null,
    enabled: false,
    created_at: '2026-05-24T11:00:00Z',
    updated_at: '2026-05-24T11:00:00Z',
  },
];

function mockList() {
  (api.get as ReturnType<typeof vi.fn>).mockResolvedValue({
    data: { policies: mockPolicies, total: 2 },
  });
}

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
    mockList();
    renderPage();
    await waitFor(() => {
      expect(screen.getByText('Deny Personal Edge')).toBeTruthy();
      expect(screen.getByText('Central Relay Default')).toBeTruthy();
      expect(screen.getByText('personal_edge')).toBeTruthy();
      expect(screen.getByText('central_relay')).toBeTruthy();
    });
  });

  it('opens Add Policy dialog when button is clicked', async () => {
    mockList();
    renderPage();
    await waitFor(() => {
      expect(screen.getByText('Deny Personal Edge')).toBeTruthy();
    });

    fireEvent.click(screen.getByRole('button', { name: 'Add Policy' }));
    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Add Route Policy' })).toBeTruthy();
      expect(screen.getByLabelText('Policy Name')).toBeTruthy();
      expect(screen.getByLabelText('Description')).toBeTruthy();
      expect(screen.getByLabelText('Source Zone ID')).toBeTruthy();
      expect(screen.getByLabelText('Target Zone ID')).toBeTruthy();
      expect(screen.getByLabelText('Priority')).toBeTruthy();
      expect(screen.getByLabelText('Allowed Route Types (comma-separated)')).toBeTruthy();
      expect(screen.getByLabelText('Denied Route Types (comma-separated)')).toBeTruthy();
      expect(screen.getByLabelText('Risk Level')).toBeTruthy();
    });
  });

  it('calls POST API when dialog is submitted', async () => {
    mockList();
    (api.post as ReturnType<typeof vi.fn>).mockResolvedValue({ data: {} });
    renderPage();
    await waitFor(() => {
      expect(screen.getByText('Deny Personal Edge')).toBeTruthy();
    });

    fireEvent.click(screen.getByRole('button', { name: 'Add Policy' }));
    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Add Route Policy' })).toBeTruthy();
    });

    fireEvent.change(screen.getByLabelText('Policy Name'), { target: { value: 'New Policy' } });
    fireEvent.change(screen.getByLabelText('Source Zone ID'), { target: { value: 'zone-a' } });
    fireEvent.change(screen.getByLabelText('Denied Route Types (comma-separated)'), {
      target: { value: 'personal_edge, local_edge' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Submit' }));

    await waitFor(() => {
      expect(api.post).toHaveBeenCalledWith('/v1/routes/policies', {
        policy_name: 'New Policy',
        priority: 100,
        require_approval: false,
        enabled: true,
        source_zone_id: 'zone-a',
        denied_route_types: ['personal_edge', 'local_edge'],
      });
    });
  });

  it('calls PATCH API when enabled toggle is clicked', async () => {
    mockList();
    (api.patch as ReturnType<typeof vi.fn>).mockResolvedValue({ data: {} });
    renderPage();
    await waitFor(() => {
      expect(screen.getByText('Deny Personal Edge')).toBeTruthy();
    });

    // Find the enabled toggle (button showing "Yes" for the enabled policy)
    const yesButtons = screen.getAllByText('Yes');
    fireEvent.click(yesButtons[0]);

    await waitFor(() => {
      expect(api.patch).toHaveBeenCalledWith('/v1/routes/policies/rp-1', { enabled: false });
    });
  });

  it('opens Edit dialog pre-filled with existing data', async () => {
    mockList();
    (api.patch as ReturnType<typeof vi.fn>).mockResolvedValue({ data: {} });
    renderPage();
    await waitFor(() => {
      expect(screen.getByText('Deny Personal Edge')).toBeTruthy();
    });

    const editButtons = screen.getAllByText('Edit');
    fireEvent.click(editButtons[0]);

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Edit Route Policy' })).toBeTruthy();
      expect((screen.getByLabelText('Policy Name') as HTMLInputElement).value).toBe(
        'Deny Personal Edge',
      );
      expect((screen.getByLabelText('Denied Route Types (comma-separated)') as HTMLInputElement).value).toBe(
        'personal_edge',
      );
      expect((screen.getByLabelText('Source Zone ID') as HTMLInputElement).value).toBe('');
      expect(screen.getByLabelText('Requires Approval')).not.toBeChecked();
    });
  });

  it('submits edit via PATCH with only changed fields', async () => {
    mockList();
    (api.patch as ReturnType<typeof vi.fn>).mockResolvedValue({ data: {} });
    renderPage();
    await waitFor(() => {
      expect(screen.getByText('Deny Personal Edge')).toBeTruthy();
    });

    fireEvent.click(screen.getAllByText('Edit')[0]);
    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Edit Route Policy' })).toBeTruthy();
    });

    fireEvent.change(screen.getByLabelText('Policy Name'), { target: { value: 'Renamed Policy' } });
    fireEvent.change(screen.getByLabelText('Priority'), { target: { value: '25' } });
    fireEvent.click(screen.getByRole('button', { name: 'Submit' }));

    await waitFor(() => {
      expect(api.patch).toHaveBeenCalledWith(
        '/v1/routes/policies/rp-1',
        expect.objectContaining({ policy_name: 'Renamed Policy', priority: 25 }),
      );
    });
  });
});

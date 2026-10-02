import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import EgressGatewaysPage from '../EgressGatewaysPage';

vi.mock('../../../api/client', () => ({
  default: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), delete: vi.fn() },
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
  return render(
    <QueryClientProvider client={qc}>
      <EgressGatewaysPage />
    </QueryClientProvider>,
  );
}

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

const mockGateways = [
  {
    id: 'eg-1',
    scope_id: 'sc-1',
    gateway_name: 'Primary Gateway',
    gateway_type: 'api',
    domain_allowlist: ['api.example.com', 'cdn.example.com'],
    secret_store_ref: 'env:EGRESS_PRIMARY_KEY',
    rate_limit_config: null,
    cache_config: null,
    cost_tracking: true,
    enabled: true,
    allow_internal_egress: false,
    created_at: '2026-05-24T12:00:00Z',
    updated_at: '2026-05-24T12:00:00Z',
  },
  {
    id: 'eg-2',
    scope_id: 'sc-2',
    gateway_name: 'Model Proxy',
    gateway_type: 'model',
    domain_allowlist: [],
    secret_store_ref: null,
    rate_limit_config: null,
    cache_config: null,
    cost_tracking: false,
    enabled: false,
    allow_internal_egress: true,
    created_at: '2026-05-24T11:00:00Z',
    updated_at: '2026-05-24T11:00:00Z',
  },
];

const mockScopes = {
  scopes: [
    { scope_id: 'sc-1', scope_name: 'HQ Network', scope_type: 'enterprise', username: null },
    { scope_id: 'sc-2', scope_name: 'Lab', scope_type: 'personal', username: 'lab-user' },
  ],
  total: 2,
};

/** GET has two calls (gateways + scopes); gateways is the first one. */
function mockGets(gateways: unknown, scopes: unknown = mockScopes) {
  (api.get as any).mockImplementation((url: string) => {
    if (url === '/v1/egress/gateways') return Promise.resolve({ data: gateways });
    if (url === '/v1/dashboard/admin/network/scopes')
      return Promise.resolve({ data: scopes });
    return Promise.reject(new Error(`unexpected GET ${url}`));
  });
}

describe('EgressGatewaysPage (full CRUD against /v1/egress/gateways)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockSuperAdmin();
  });

  it('shows loading state initially', () => {
    (api.get as any).mockReturnValue(new Promise(() => {}));
    const { container } = renderPage();
    expect(container.querySelector('.animate-spin')).toBeTruthy();
  });

  it('shows error state when the list load fails', async () => {
    (api.get as any).mockRejectedValue(new Error('Network error'));
    renderPage();
    await waitFor(() => {
      expect(screen.getByText(/failed to load egress gateways/i)).toBeTruthy();
    });
  });

  it('renders gateways from the read endpoint', async () => {
    mockGets({ gateways: mockGateways, total: 2 });
    renderPage();
    await waitFor(() => {
      expect(screen.getByText('Primary Gateway')).toBeTruthy();
      expect(screen.getByText('Model Proxy')).toBeTruthy();
    });
    expect(api.get).toHaveBeenCalledWith('/v1/egress/gateways');
  });

  it('renders type, scope names, allowlist and cost chips', async () => {
    mockGets({ gateways: mockGateways, total: 2 });
    renderPage();
    await waitFor(() => {
      expect(screen.getByText('Primary Gateway')).toBeTruthy();
    });
    expect(screen.getByText('api')).toBeTruthy();
    expect(screen.getByText('model')).toBeTruthy();
    expect(screen.getByText('HQ Network')).toBeTruthy();
    expect(screen.getByText('api.example.com, cdn.example.com')).toBeTruthy();
  });

  // M4 egress policy point: allow_internal_egress is the default-deny
  // opt-in (EgressGatewayResponse / EgressGatewayCreate).
  it('renders the internal-egress column with default-deny chips', async () => {
    mockGets({ gateways: mockGateways, total: 2 });
    renderPage();
    await waitFor(() => {
      expect(screen.getByText('Primary Gateway')).toBeTruthy();
    });
    expect(screen.getByText('Internal Egress')).toBeTruthy();
    // eg-1 keeps the default-deny baseline (No, neutral chip).
    expect(screen.getAllByText('No').length).toBeGreaterThanOrEqual(1);
    // eg-2 opted in (Yes, amber chip).
    const yesChips = screen.getAllByText('Yes');
    expect(yesChips.length).toBeGreaterThanOrEqual(1);
  });

  it('opts into internal egress in the create form and posts the flag', async () => {
    mockGets({ gateways: mockGateways, total: 2 });
    (api.post as any).mockResolvedValue({ data: mockGateways[0] });
    renderPage();
    await waitFor(() => {
      expect(screen.getByText('Primary Gateway')).toBeTruthy();
    });

    fireEvent.click(screen.getByText('Add Gateway'));
    const nameInput = await screen.findByLabelText(/name/i);
    fireEvent.change(nameInput, { target: { value: 'Internal Gateway' } });
    // Checkbox is unchecked by default (default deny).
    const internalCheckbox = screen.getByLabelText(/allow internal egress/i);
    expect((internalCheckbox as HTMLInputElement).checked).toBe(false);
    fireEvent.click(internalCheckbox);

    fireEvent.click(screen.getByRole('button', { name: 'Submit' }));
    await waitFor(() => {
      expect(api.post).toHaveBeenCalledWith('/v1/egress/gateways', {
        gateway_name: 'Internal Gateway',
        gateway_type: 'api',
        domain_allowlist: [],
        secret_store_ref: null,
        cost_tracking: true,
        allow_internal_egress: true,
        scope_id: 'sc-1',
      });
    });
  });

  it('prefills the internal-egress checkbox from the edited row', async () => {
    mockGets({ gateways: mockGateways, total: 2 });
    (api.patch as any).mockResolvedValue({ data: mockGateways[1] });
    renderPage();
    await waitFor(() => {
      expect(screen.getByText('Model Proxy')).toBeTruthy();
    });

    // Edit eg-2, which is opted into internal egress.
    fireEvent.click(screen.getAllByText('Edit')[1]);
    const internalCheckbox = await screen.findByLabelText(/allow internal egress/i);
    expect((internalCheckbox as HTMLInputElement).checked).toBe(true);
  });

  it('filters rows client-side by name and clears the filter', async () => {
    mockGets({ gateways: mockGateways, total: 2 });
    renderPage();
    await waitFor(() => {
      expect(screen.getByText('Primary Gateway')).toBeTruthy();
    });

    const input = screen.getByPlaceholderText(/filter by name, domain or type/i);
    fireEvent.change(input, { target: { value: 'model' } });
    expect(screen.getByText('Model Proxy')).toBeTruthy();
    expect(screen.queryByText('Primary Gateway')).not.toBeInTheDocument();

    fireEvent.click(screen.getByText('Clear'));
    expect(screen.getByText('Primary Gateway')).toBeTruthy();
  });

  it('opens the create form with scope options and posts the gateway', async () => {
    mockGets({ gateways: mockGateways, total: 2 });
    (api.post as any).mockResolvedValue({ data: mockGateways[0] });
    renderPage();
    await waitFor(() => {
      expect(screen.getByText('Primary Gateway')).toBeTruthy();
    });

    fireEvent.click(screen.getByText('Add Gateway'));
    const nameInput = await screen.findByLabelText(/name/i);
    fireEvent.change(nameInput, { target: { value: 'New Gateway' } });
    fireEvent.change(screen.getByLabelText(/allowed domains/i), {
      target: { value: 'a.example.com, b.example.com' },
    });

    fireEvent.click(screen.getByRole('button', { name: 'Submit' }));
    await waitFor(() => {
      expect(api.post).toHaveBeenCalledWith('/v1/egress/gateways', {
        gateway_name: 'New Gateway',
        gateway_type: 'api',
        domain_allowlist: ['a.example.com', 'b.example.com'],
        secret_store_ref: null,
        cost_tracking: true,
        allow_internal_egress: false,
        scope_id: 'sc-1',
      });
    });
  });

  it('blocks create when the name is empty', async () => {
    mockGets({ gateways: mockGateways, total: 2 });
    renderPage();
    await waitFor(() => {
      expect(screen.getByText('Primary Gateway')).toBeTruthy();
    });

    fireEvent.click(screen.getByText('Add Gateway'));
    const submit = await screen.findByRole('button', { name: 'Submit' });
    fireEvent.click(submit);
    expect(await screen.findByText(/gateway name is required/i)).toBeTruthy();
    expect(api.post).not.toHaveBeenCalled();
  });

  it('toggles enabled via PATCH', async () => {
    mockGets({ gateways: mockGateways, total: 2 });
    (api.patch as any).mockResolvedValue({ data: mockGateways[0] });
    renderPage();
    await waitFor(() => {
      expect(screen.getByText('Primary Gateway')).toBeTruthy();
    });

    // The enabled cell for eg-1 is a button labeled with the gateway name.
    const toggle = screen.getByLabelText(/toggle enabled state of gateway primary gateway/i);
    fireEvent.click(toggle);
    await waitFor(() => {
      expect(api.patch).toHaveBeenCalledWith('/v1/egress/gateways/eg-1', { enabled: false });
    });
  });

  it('opens the edit form prefilled and patches only changed fields', async () => {
    mockGets({ gateways: mockGateways, total: 2 });
    (api.patch as any).mockResolvedValue({ data: mockGateways[0] });
    renderPage();
    await waitFor(() => {
      expect(screen.getByText('Primary Gateway')).toBeTruthy();
    });

    fireEvent.click(screen.getAllByText('Edit')[0]);
    const nameInput = await screen.findByLabelText(/name/i);
    expect((nameInput as HTMLInputElement).value).toBe('Primary Gateway');
    // Scope is locked while editing. (Exact match: the internal-egress
    // checkbox hint also mentions "scope CIDR".)
    expect((screen.getByLabelText('Scope') as HTMLSelectElement).disabled).toBe(true);

    fireEvent.change(nameInput, { target: { value: 'Renamed Gateway' } });
    fireEvent.click(screen.getByRole('button', { name: 'Submit' }));
    await waitFor(() => {
      expect(api.patch).toHaveBeenCalledWith('/v1/egress/gateways/eg-1', {
        gateway_name: 'Renamed Gateway',
        gateway_type: 'api',
        domain_allowlist: ['api.example.com', 'cdn.example.com'],
        secret_store_ref: 'env:EGRESS_PRIMARY_KEY',
        cost_tracking: true,
        enabled: true,
        allow_internal_egress: false,
      });
    });
  });

  it('deletes a gateway after confirmation', async () => {
    mockGets({ gateways: mockGateways, total: 2 });
    (api.delete as any).mockResolvedValue({ status: 204 });
    renderPage();
    await waitFor(() => {
      expect(screen.getByText('Primary Gateway')).toBeTruthy();
    });

    fireEvent.click(screen.getAllByText('Delete')[0]);
    const dialog = await screen.getByRole('dialog');
    fireEvent.click(within(dialog).getByText('Delete'));
    await waitFor(() => {
      expect(api.delete).toHaveBeenCalledWith('/v1/egress/gateways/eg-1');
    });
  });

  it('demands step-up before writing when step-up has expired', async () => {
    mockSuperAdmin(null); // never stepped up
    mockGets({ gateways: mockGateways, total: 2 });
    renderPage();
    await waitFor(() => {
      expect(screen.getByText('Primary Gateway')).toBeTruthy();
    });

    fireEvent.click(screen.getByText('Add Gateway'));
    // Step-up dialog opens instead of the create form.
    await waitFor(() => {
      expect(screen.getByText(/api key/i)).toBeTruthy();
    });
    expect(api.post).not.toHaveBeenCalled();
  });

  it('hides write controls for non-super-admins', async () => {
    (useAuth as any).mockReturnValue({
      data: {
        user_id: 'u-viewer',
        username: 'viewer',
        role: 'admin',
        step_up_until: '2999-01-01T00:00:00Z',
      },
    });
    mockGets({ gateways: mockGateways, total: 2 });
    renderPage();
    await waitFor(() => {
      expect(screen.getByText('Primary Gateway')).toBeTruthy();
    });

    expect(screen.queryByText('Add Gateway')).not.toBeInTheDocument();
    expect(screen.queryByText('Edit')).not.toBeInTheDocument();
    expect(screen.queryByText('Delete')).not.toBeInTheDocument();
    // Enabled state is a plain chip, not a button.
    screen.getAllByText('Yes').forEach((badge) => expect(badge.tagName).not.toBe('BUTTON'));
    expect(api.post).not.toHaveBeenCalled();
    expect(api.patch).not.toHaveBeenCalled();
    expect(api.delete).not.toHaveBeenCalled();
  });
});

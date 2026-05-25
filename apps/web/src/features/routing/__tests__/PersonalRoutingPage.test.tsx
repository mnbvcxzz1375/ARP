import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import PersonalRoutingPage from '../PersonalRoutingPage';

// Mock path resolves from __tests__/ -> ../../api/client
const mockGet = vi.fn();
const mockPatch = vi.fn();

vi.mock('../../../api/client', () => ({
  default: {
    get: (...args: any[]) => mockGet(...args),
    patch: (...args: any[]) => mockPatch(...args),
  },
}));

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function renderPage() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false, refetchOnWindowFocus: false },
      mutations: { retry: false },
    },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <PersonalRoutingPage />
    </QueryClientProvider>,
  );
}

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const mockScope = {
  user_id: 'user-001',
  scope_name: 'personal',
  default_relay_type: 'central_relay',
  enable_edge_relay: false,
  enable_secure_channel: true,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-05-20T00:00:00Z',
};

const mockEdgeRelays = [
  {
    id: 'relay-001',
    node_name: 'home-edge',
    status: 'healthy',
    current_load: 0.25,
    queue_depth: 2,
    avg_latency_ms: 12.5,
    success_rate: 0.98,
    is_healthy: true,
    network_info: { subnet: '10.0.0.0/24' },
    last_heartbeat_at: '2026-05-20T12:00:00Z',
    created_at: '2026-01-15T00:00:00Z',
  },
  {
    id: 'relay-002',
    node_name: 'office-edge',
    status: 'degraded',
    current_load: 0.8,
    queue_depth: 15,
    avg_latency_ms: 45.0,
    success_rate: 0.85,
    is_healthy: false,
    network_info: { subnet: '192.168.1.0/24' },
    last_heartbeat_at: '2026-05-20T11:55:00Z',
    created_at: '2026-02-10T00:00:00Z',
  },
];

const mockDecisions = [
  {
    task_id: 'task-aaaa-bbbb-cccc',
    selected_route_type: 'central_relay',
    risk_level: 'low',
    fallback_from_route: null,
    fallback_reason: null,
    shadow_mode: false,
    decision_time_ms: 3,
    created_at: '2026-05-20T10:00:00Z',
  },
  {
    task_id: 'task-dddd-eeee-ffff',
    selected_route_type: 'edge',
    risk_level: 'medium',
    fallback_from_route: 'dedicated',
    fallback_reason: 'dedicated node unhealthy',
    shadow_mode: true,
    decision_time_ms: 8,
    created_at: '2026-05-20T09:30:00Z',
  },
];

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('PersonalRoutingPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  // --- 1. Loading state ---
  it('shows loading spinners while queries are pending', async () => {
    mockGet.mockImplementation(() => new Promise(() => {}));
    const { container } = renderPage();

    // LoadingState renders a Loader2 SVG with animate-spin class
    await waitFor(() => {
      const spinners = container.querySelectorAll('.animate-spin');
      expect(spinners.length).toBeGreaterThanOrEqual(1);
    });
  });

  // --- 2. Error state ---
  it('renders error state when scope query fails', async () => {
    mockGet.mockRejectedValue(new Error('Network error'));
    renderPage();

    expect(await screen.findByText('Failed to load routing scope')).toBeInTheDocument();
  });

  it('renders error state when edge relays query fails', async () => {
    mockGet.mockImplementation((url: string) => {
      if (url === '/v1/personal/scope') return Promise.resolve({ data: mockScope });
      if (url === '/v1/personal/edge-relays') return Promise.reject(new Error('fail'));
      if (url.startsWith('/v1/routes/decisions')) return Promise.resolve({ data: { decisions: [] } });
      return Promise.resolve({ data: {} });
    });
    renderPage();

    expect(await screen.findByText('Failed to load edge relays')).toBeInTheDocument();
  });

  it('renders error state when route decisions query fails', async () => {
    mockGet.mockImplementation((url: string) => {
      if (url === '/v1/personal/scope') return Promise.resolve({ data: mockScope });
      if (url === '/v1/personal/edge-relays') return Promise.resolve({ data: [] });
      if (url.startsWith('/v1/routes/decisions')) return Promise.reject(new Error('fail'));
      return Promise.resolve({ data: {} });
    });
    renderPage();

    expect(await screen.findByText('Failed to load route decisions')).toBeInTheDocument();
  });

  // --- 3. Renders scope config from API ---
  it('renders scope configuration from API', async () => {
    mockGet.mockImplementation((url: string) => {
      if (url === '/v1/personal/scope') return Promise.resolve({ data: mockScope });
      if (url === '/v1/personal/edge-relays') return Promise.resolve({ data: [] });
      if (url.startsWith('/v1/routes/decisions')) return Promise.resolve({ data: { decisions: [] } });
      return Promise.resolve({ data: {} });
    });
    renderPage();

    // Wait for scope data to render (not just the section heading)
    await waitFor(() => {
      expect(screen.getByText('central_relay')).toBeInTheDocument();
    });

    // Toggle states reflected via aria-checked
    const toggles = screen.getAllByRole('switch');
    expect(toggles[0]).toHaveAttribute('aria-checked', 'false'); // enable_edge_relay
    expect(toggles[1]).toHaveAttribute('aria-checked', 'true'); // enable_secure_channel

    // Routing mode labels
    expect(screen.getByText('Fast')).toBeInTheDocument();
    expect(screen.getByText('Normal')).toBeInTheDocument();
    expect(screen.getByText('Reliable')).toBeInTheDocument();

    // Normal mode is active (central_relay maps to normal)
    expect(screen.getByText('Balanced latency and reliability')).toBeInTheDocument();
  });

  // --- 4. Renders edge relay cards ---
  it('renders edge relay cards', async () => {
    mockGet.mockImplementation((url: string) => {
      if (url === '/v1/personal/scope') return Promise.resolve({ data: mockScope });
      if (url === '/v1/personal/edge-relays') return Promise.resolve({ data: mockEdgeRelays });
      if (url.startsWith('/v1/routes/decisions')) return Promise.resolve({ data: { decisions: [] } });
      return Promise.resolve({ data: {} });
    });
    renderPage();

    await waitFor(() => {
      expect(screen.getByText('home-edge')).toBeInTheDocument();
    });

    expect(screen.getByText('office-edge')).toBeInTheDocument();
    expect(screen.getByText('25%')).toBeInTheDocument();
    expect(screen.getByText('80%')).toBeInTheDocument();
    expect(screen.getByText('12.5ms')).toBeInTheDocument();
    expect(screen.getByText('45ms')).toBeInTheDocument();
    expect(screen.getByText('98%')).toBeInTheDocument();
    expect(screen.getByText('85%')).toBeInTheDocument();
  });

  // --- 5. Renders route decisions table ---
  it('renders route decisions table', async () => {
    mockGet.mockImplementation((url: string) => {
      if (url === '/v1/personal/scope') return Promise.resolve({ data: mockScope });
      if (url === '/v1/personal/edge-relays') return Promise.resolve({ data: [] });
      if (url.startsWith('/v1/routes/decisions'))
        return Promise.resolve({ data: { decisions: mockDecisions } });
      return Promise.resolve({ data: {} });
    });
    renderPage();

    // Wait for actual task ID data to appear (not just section heading)
    await waitFor(() => {
      expect(screen.getByText('task-aaa')).toBeInTheDocument();
    });

    expect(screen.getByText('task-ddd')).toBeInTheDocument();

    // Route types
    // Route types -- appear in scope config and decisions table
    expect(screen.getAllByText("central_relay").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("edge").length).toBeGreaterThanOrEqual(1);
    // Column headers
    expect(screen.getByText('Route Type')).toBeInTheDocument();
    expect(screen.getByText('Risk')).toBeInTheDocument();
    expect(screen.getByText('Shadow')).toBeInTheDocument();
  });

  // --- 6. Toggle update calls PATCH API ---
  it('calls PATCH endpoint when edge relay toggle is clicked', async () => {
    mockGet.mockImplementation((url: string) => {
      if (url === '/v1/personal/scope') return Promise.resolve({ data: mockScope });
      if (url === '/v1/personal/edge-relays') return Promise.resolve({ data: [] });
      if (url.startsWith('/v1/routes/decisions')) return Promise.resolve({ data: { decisions: [] } });
      return Promise.resolve({ data: {} });
    });
    mockPatch.mockResolvedValue({
      data: { ...mockScope, enable_edge_relay: true },
    });

    renderPage();

    // Wait for the scope data to render (toggle exists)
    await waitFor(() => {
      expect(screen.getAllByRole('switch').length).toBeGreaterThanOrEqual(1);
    });

    const toggles = screen.getAllByRole('switch');
    fireEvent.click(toggles[0]); // enable_edge_relay toggle

    await waitFor(() => {
      expect(mockPatch).toHaveBeenCalledWith('/v1/personal/scope', {
        enable_edge_relay: true,
      });
    });
  });

  it('calls PATCH endpoint when secure channel toggle is clicked', async () => {
    mockGet.mockImplementation((url: string) => {
      if (url === '/v1/personal/scope') return Promise.resolve({ data: mockScope });
      if (url === '/v1/personal/edge-relays') return Promise.resolve({ data: [] });
      if (url.startsWith('/v1/routes/decisions')) return Promise.resolve({ data: { decisions: [] } });
      return Promise.resolve({ data: {} });
    });
    mockPatch.mockResolvedValue({
      data: { ...mockScope, enable_secure_channel: false },
    });

    renderPage();

    // Wait for the scope data to render (toggle exists)
    await waitFor(() => {
      expect(screen.getAllByRole('switch').length).toBeGreaterThanOrEqual(1);
    });

    const toggles = screen.getAllByRole('switch');
    fireEvent.click(toggles[1]); // enable_secure_channel toggle

    await waitFor(() => {
      expect(mockPatch).toHaveBeenCalledWith('/v1/personal/scope', {
        enable_secure_channel: false,
      });
    });
  });
});

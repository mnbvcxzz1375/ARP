import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent, within } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import NetworkZonesPage from '../NetworkZonesPage';

function mockAxios() {
  return {
    default: {
      get: vi.fn(),
      post: vi.fn(),
      put: vi.fn(),
      delete: vi.fn(),
    },
  };
}

vi.mock('../../../api/client', () => mockAxios());

import api from '../../../api/client';

const mockedApi = vi.mocked(api, true);

function renderPage() {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <NetworkZonesPage />
      </MemoryRouter>
    </QueryClientProvider>
  );
}

describe('NetworkZonesPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders zone list', async () => {
    mockedApi.get.mockResolvedValueOnce({
      data: {
        zones: [
          { zone_id: 'z-1', scope_id: 's-1', zone_name: 'Zone A', zone_type: 'regional', region: 'us-east', security_level: 'standard', network_cidr: '10.0.0.0/16', agent_count: 5, created_at: '', updated_at: '' },
        ],
        total: 1,
      },
    });
    renderPage();
    await waitFor(() => expect(screen.getByText('Zone A')).toBeInTheDocument());
  });

  it('shows pagination when total > page size', async () => {
    mockedApi.get.mockResolvedValueOnce({
      data: {
        zones: [{ zone_id: 'z-1', scope_id: 's-1', zone_name: 'Zone A', zone_type: 'regional', region: null, security_level: null, network_cidr: null, agent_count: 0, created_at: '', updated_at: '' }],
        total: 100,
      },
    });
    renderPage();
    await waitFor(() => expect(screen.getByText('Next')).toBeInTheDocument());
  });

  it('displays delete error when mutation fails', async () => {
    mockedApi.get.mockResolvedValueOnce({
      data: { zones: [{ zone_id: 'z-1', scope_id: 's-1', zone_name: 'Zone A', zone_type: 'regional', region: null, security_level: null, network_cidr: null, agent_count: 0, created_at: '', updated_at: '' }], total: 1 },
    });
    mockedApi.delete.mockRejectedValueOnce({
      response: { data: { error: { message: 'Cannot delete zone with active agents' } } },
    });
    renderPage();
    await waitFor(() => expect(screen.getByText('Zone A')).toBeInTheDocument());
    // Click the row-level Delete link
    fireEvent.click(screen.getByText('Delete'));
    // ConfirmDialog opens — find the danger confirm button inside it
    const dialog = await screen.findByRole('heading', { name: 'Delete Zone' });
    const dialogContainer = dialog.closest('.bg-white')!;
    const confirmBtn = within(dialogContainer as HTMLElement).getByRole('button', { name: 'Delete' });
    fireEvent.click(confirmBtn);
    await waitFor(() => expect(screen.getByText(/Cannot delete zone with active agents/)).toBeInTheDocument());
  });

  it('shows form error from DomainException structure', async () => {
    mockedApi.get.mockResolvedValueOnce({
      data: { zones: [], total: 0 },
    });
    mockedApi.post.mockRejectedValueOnce({
      response: { data: { error: { message: 'Scope not found' } } },
    });
    renderPage();
    await waitFor(() => expect(screen.getByText('Add Zone')).toBeInTheDocument());
    fireEvent.click(screen.getByText('Add Zone'));
    await waitFor(() => expect(screen.getByLabelText('Zone Name')).toBeInTheDocument());
    fireEvent.change(screen.getByLabelText('Zone Name'), { target: { value: 'Test Zone' } });
    fireEvent.change(screen.getByLabelText('Scope ID'), { target: { value: 'nonexistent-scope-id' } });
    fireEvent.click(screen.getByText('Submit'));
    await waitFor(() => expect(screen.getByText(/Scope not found/)).toBeInTheDocument());
  });
});

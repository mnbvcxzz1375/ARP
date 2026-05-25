import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent, within } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import NetworkScopesPage from '../NetworkScopesPage';

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
        <NetworkScopesPage />
      </MemoryRouter>
    </QueryClientProvider>
  );
}

describe('NetworkScopesPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders scope list', async () => {
    mockedApi.get.mockResolvedValueOnce({
      data: {
        scopes: [
          { scope_id: 's-1', scope_name: 'Scope A', scope_type: 'personal', user_id: 'u-1', username: 'alice', network_cidr: null, agent_count: 2, zone_count: 1, created_at: '', updated_at: '' },
        ],
        total: 1,
      },
    });
    renderPage();
    await waitFor(() => expect(screen.getByText('Scope A')).toBeInTheDocument());
  });

  it('shows pagination when total > page size', async () => {
    mockedApi.get.mockResolvedValueOnce({
      data: {
        scopes: [{ scope_id: 's-1', scope_name: 'Scope A', scope_type: 'personal', user_id: 'u-1', username: 'alice', network_cidr: null, agent_count: 2, zone_count: 1, created_at: '', updated_at: '' }],
        total: 100,
      },
    });
    renderPage();
    await waitFor(() => expect(screen.getByText('Next')).toBeInTheDocument());
  });

  it('displays delete error when mutation fails', async () => {
    mockedApi.get.mockResolvedValueOnce({
      data: { scopes: [{ scope_id: 's-1', scope_name: 'Scope A', scope_type: 'personal', user_id: 'u-1', username: 'alice', network_cidr: null, agent_count: 2, zone_count: 1, created_at: '', updated_at: '' }], total: 1 },
    });
    mockedApi.delete.mockRejectedValueOnce({
      response: { data: { error: { message: 'Cannot delete scope with child zones' } } },
    });
    renderPage();
    await waitFor(() => expect(screen.getByText('Scope A')).toBeInTheDocument());
    // Click the row-level Delete link
    fireEvent.click(screen.getByText('Delete'));
    // ConfirmDialog opens — find the danger confirm button inside it
    const dialog = await screen.findByRole('heading', { name: 'Delete Scope' });
    const dialogContainer = dialog.closest('.bg-white')!;
    const confirmBtn = within(dialogContainer as HTMLElement).getByRole('button', { name: 'Delete' });
    fireEvent.click(confirmBtn);
    await waitFor(() => expect(screen.getByText(/Cannot delete scope with child zones/)).toBeInTheDocument());
  });

  it('shows form error from DomainException structure', async () => {
    mockedApi.get.mockResolvedValueOnce({
      data: { scopes: [], total: 0 },
    });
    mockedApi.post.mockRejectedValueOnce({
      response: { data: { error: { message: 'User not found' } } },
    });
    renderPage();
    await waitFor(() => expect(screen.getByText('Add Scope')).toBeInTheDocument());
    fireEvent.click(screen.getByText('Add Scope'));
    await waitFor(() => expect(screen.getByLabelText('Scope Name')).toBeInTheDocument());
    fireEvent.change(screen.getByLabelText('Scope Name'), { target: { value: 'Test Scope' } });
    fireEvent.change(screen.getByLabelText('User ID'), { target: { value: 'nonexistent-user-id' } });
    fireEvent.click(screen.getByText('Submit'));
    await waitFor(() => expect(screen.getByText(/User not found/)).toBeInTheDocument());
  });
});

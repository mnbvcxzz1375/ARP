import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import ApiKeysPage from '../ApiKeysPage';

// Mock path MUST match the resolved path from the source code.
// ApiKeysPage.tsx imports from '../../api/client' → resolves to src/api/client.ts.
// From __tests__/ dir the correct relative path is '../../../api/client'.
vi.mock('../../../api/client', () => ({
  default: { get: vi.fn(), post: vi.fn() },
}));

import api from '../../../api/client';

// ---------------------------------------------------------------------------
// Test helpers
// ---------------------------------------------------------------------------

function renderWithClient(ui: React.ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false, refetchOnWindowFocus: false },
      mutations: { retry: false },
    },
  });
  return render(<QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>);
}

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const mockApiKeys = [
  {
    api_key_id: 'key-1',
    name: 'Active Key',
    key_prefix: 'ak_abc',
    created_at: '2026-01-01T00:00:00Z',
    expires_at: null,
    revoked_at: null,
  },
  {
    api_key_id: 'key-2',
    name: 'Revoked Key',
    key_prefix: 'ak_def',
    created_at: '2026-01-02T00:00:00Z',
    expires_at: '2026-06-01T00:00:00Z',
    revoked_at: '2026-03-01T00:00:00Z',
  },
];

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('ApiKeysPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  // --- 1. Query error state ---
  it('renders error state when query fails', async () => {
    (api.get as any).mockRejectedValue(new Error('fail'));
    renderWithClient(<ApiKeysPage />);
    expect(await screen.findByText('Failed to load API keys')).toBeInTheDocument();
  });

  // --- 2. Rendering table and create form ---
  it('renders the table, create form, and heading', async () => {
    (api.get as any).mockResolvedValue({ data: { api_keys: mockApiKeys } });
    renderWithClient(<ApiKeysPage />);

    // Wait for query to resolve
    await screen.findByText('Active Key');

    // Heading
    expect(screen.getByText('API Keys')).toBeInTheDocument();

    // Form elements
    expect(screen.getByLabelText('Name')).toBeInTheDocument();
    expect(screen.getByLabelText('Expires At (optional)')).toBeInTheDocument();
    expect(screen.getByText('Create Key')).toBeInTheDocument();

    // Table data
    expect(screen.getByText('Revoked Key')).toBeInTheDocument();
  });

  // --- 3. Creating a key successfully and showing the raw key panel ---
  it('creates a key successfully and shows raw key panel', async () => {
    (api.get as any).mockResolvedValue({ data: { api_keys: mockApiKeys } });
    renderWithClient(<ApiKeysPage />);
    await screen.findByText('API Keys');

    fireEvent.change(screen.getByLabelText('Name'), { target: { value: 'My New Key' } });

    const createData = {
      api_key_id: 'key-new',
      key_prefix: 'ak_new',
      name: 'My New Key',
      expires_at: null,
      api_key: 'ak_new_test_key_value_12345',
    };
    (api.post as any).mockResolvedValue({ data: createData });

    fireEvent.click(screen.getByText('Create Key'));

    // Wait for the raw key panel to appear
    await screen.findByText('API Key Created: My New Key');

    // Creation endpoint payload
    expect(api.post as any).toHaveBeenCalledWith('/v1/dashboard/api-keys', {
      name: 'My New Key',
      expires_at: null,
    });

    // Raw key panel content
    expect(
      screen.getByText('Copy this key now. You will not be able to see it again.'),
    ).toBeInTheDocument();
    expect(screen.getByText('Close')).toBeInTheDocument();

    // Raw key value is masked by SecretMaskedText
    expect(screen.getByText('***')).toBeInTheDocument();

    // Form is reset
    expect((screen.getByLabelText('Name') as HTMLInputElement).value).toBe('');
  });

  // --- 4. Closing the raw key panel ---
  it('closes the raw key panel when close button is clicked', async () => {
    (api.get as any).mockResolvedValue({ data: { api_keys: mockApiKeys } });
    renderWithClient(<ApiKeysPage />);
    await screen.findByText('API Keys');

    // Create a key first
    fireEvent.change(screen.getByLabelText('Name'), { target: { value: 'Temporary Key' } });
    (api.post as any).mockResolvedValue({
      data: {
        api_key_id: 'key-tmp',
        key_prefix: 'ak_tmp',
        name: 'Temporary Key',
        expires_at: null,
        api_key: 'ak_tmp_secret',
      },
    });
    fireEvent.click(screen.getByText('Create Key'));
    await screen.findByText('API Key Created: Temporary Key');

    // Click Close
    fireEvent.click(screen.getByText('Close'));
    await waitFor(() => {
      expect(
        screen.queryByText('API Key Created: Temporary Key'),
      ).not.toBeInTheDocument();
    });

    expect(
      screen.queryByText('Copy this key now. You will not be able to see it again.'),
    ).not.toBeInTheDocument();
  });

  // --- 5. Raw key panel replaced on new creation ---
  it('replaces the raw key panel when a new key is created', async () => {
    (api.get as any).mockResolvedValue({ data: { api_keys: mockApiKeys } });
    renderWithClient(<ApiKeysPage />);
    await screen.findByText('API Keys');

    // Create first key
    fireEvent.change(screen.getByLabelText('Name'), { target: { value: 'First Key' } });
    (api.post as any).mockResolvedValue({
      data: {
        api_key_id: 'key-1',
        key_prefix: 'ak_1',
        name: 'First Key',
        expires_at: null,
        api_key: 'ak_first_secret',
      },
    });
    fireEvent.click(screen.getByText('Create Key'));
    await screen.findByText('API Key Created: First Key');

    // Create a second key
    fireEvent.change(screen.getByLabelText('Name'), { target: { value: 'Second Key' } });
    (api.post as any).mockResolvedValue({
      data: {
        api_key_id: 'key-2',
        key_prefix: 'ak_2',
        name: 'Second Key',
        expires_at: null,
        api_key: 'ak_second_secret',
      },
    });
    fireEvent.click(screen.getByText('Create Key'));
    await screen.findByText('API Key Created: Second Key');

    // Old panel is replaced by the new one
    expect(screen.queryByText('API Key Created: First Key')).not.toBeInTheDocument();
  });

  // --- 6. API error during creation ---
  it('shows error message when key creation fails', async () => {
    (api.get as any).mockResolvedValue({ data: { api_keys: mockApiKeys } });
    renderWithClient(<ApiKeysPage />);
    await screen.findByText('API Keys');

    fireEvent.change(screen.getByLabelText('Name'), { target: { value: 'Failing Key' } });
    (api.post as any).mockRejectedValue({
      response: { data: { detail: 'Name already exists' } },
    });
    fireEvent.click(screen.getByText('Create Key'));
    await screen.findByText('Name already exists');

    // Raw key panel is NOT shown
    expect(
      screen.queryByText('Copy this key now. You will not be able to see it again.'),
    ).not.toBeInTheDocument();
  });

  // --- 7. Revoke button opens confirm dialog ---
  it('opens a confirm dialog when Revoke is clicked', async () => {
    (api.get as any).mockResolvedValue({ data: { api_keys: mockApiKeys } });
    renderWithClient(<ApiKeysPage />);

    await screen.findByText('Active Key');

    // Only the first key (revoked_at: null) has a Revoke button
    const revokeButtons = screen.getAllByText('Revoke');
    expect(revokeButtons).toHaveLength(1);

    fireEvent.click(revokeButtons[0]);
    await screen.findByText('Revoke API Key');

    // Confirm dialog is open
    expect(
      screen.getByText(/Are you sure you want to revoke "Active Key"/),
    ).toBeInTheDocument();
    expect(screen.getByText('Cancel')).toBeInTheDocument();

    // Dialog adds a second "Revoke" button (confirm button)
    const buttonsAfterOpen = screen.getAllByText('Revoke');
    expect(buttonsAfterOpen).toHaveLength(2);
  });

  // --- 8. Revoke calls the revoke endpoint ---
  it('calls the revoke endpoint on confirm and closes dialog', async () => {
    (api.get as any).mockResolvedValue({ data: { api_keys: mockApiKeys } });
    renderWithClient(<ApiKeysPage />);
    await screen.findByText('Active Key');

    // Open dialog
    fireEvent.click(screen.getAllByText('Revoke')[0]);
    await screen.findByText('Revoke API Key');

    // Confirm via the dialog button (second Revoke text)
    (api.post as any).mockResolvedValue({ data: {} });
    fireEvent.click(screen.getAllByText('Revoke')[1]);

    // Wait for dialog to close
    await waitFor(() => {
      expect(screen.queryByText('Revoke API Key')).not.toBeInTheDocument();
    });

    // Revoke endpoint payload
    expect(api.post as any).toHaveBeenCalledWith(
      '/v1/dashboard/api-keys/key-1/revoke',
      { allow_last_key: false },
    );
  });

  // --- 9. Revoke error shows error message ---
  it('shows error message when revoke fails', async () => {
    (api.get as any).mockResolvedValue({ data: { api_keys: mockApiKeys } });
    renderWithClient(<ApiKeysPage />);
    await screen.findByText('Active Key');

    // Open dialog
    fireEvent.click(screen.getAllByText('Revoke')[0]);
    await screen.findByText('Revoke API Key');

    // Confirm (revoke will fail)
    (api.post as any).mockRejectedValue({
      response: { data: { detail: 'Cannot revoke the last active API key' } },
    });
    fireEvent.click(screen.getAllByText('Revoke')[1]);
    await screen.findByText('Cannot revoke the last active API key');

    // Dialog is closed
    expect(screen.queryByText('Revoke API Key')).not.toBeInTheDocument();

    // Only one Revoke button remains (the revoked key doesn't have one)
    expect(screen.getAllByText('Revoke')).toHaveLength(1);
  });

  // --- 10. Empty state for revoked_at (no revoke button) ---
  it('does not show a Revoke button for keys with revoked_at set', async () => {
    (api.get as any).mockResolvedValue({ data: { api_keys: mockApiKeys } });
    renderWithClient(<ApiKeysPage />);

    await screen.findByText('Active Key');

    // Only "Active Key" (revoked_at: null) should have a Revoke button
    const revokeButtons = screen.getAllByText('Revoke');
    expect(revokeButtons).toHaveLength(1);
  });
});

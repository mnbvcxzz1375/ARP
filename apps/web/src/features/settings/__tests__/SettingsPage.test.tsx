import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { RouterForTesting } from '../../../test-utils';
import { __resetI18n } from '../../../i18n/core';
import type { UserPreferences } from '../../../hooks/usePreferences';

// Mock path MUST match the resolved path from the source code.
// SettingsPage.tsx imports from '../../hooks/...' -> resolves to src/hooks/...
vi.mock('../../../hooks/useAuth', () => ({
  useAuth: vi.fn(),
  useLogout: vi.fn(() => ({ mutate: vi.fn(), isPending: false })),
}));

vi.mock('../../../hooks/useTheme', () => ({
  useTheme: vi.fn(() => ({ theme: 'dark', setTheme: vi.fn(), toggleTheme: vi.fn() })),
}));

vi.mock('../../../hooks/usePreferences', () => ({
  usePreferences: vi.fn(),
}));

// UsernameRow PATCHes /me/profile through the shared axios client; mock
// it so the rename interaction test never touches the network.
vi.mock('../../../api/client', () => ({
  default: {
    patch: vi.fn(async (_url: string, body: { username: string }) => ({
      data: { user_id: 'user-123', username: body.username },
    })),
  },
}));

import { useAuth, useLogout } from '../../../hooks/useAuth';
import { useTheme } from '../../../hooks/useTheme';
import { usePreferences } from '../../../hooks/usePreferences';
import SettingsPage from '../SettingsPage';

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
  return render(
    <QueryClientProvider client={queryClient}>
      <RouterForTesting>{ui}</RouterForTesting>
    </QueryClientProvider>,
  );
}

interface MockPrefsResult {
  data?: UserPreferences;
  isLoading?: boolean;
  isError?: boolean;
  isSaving?: boolean;
  saveError?: unknown;
  patchPreferences?: ReturnType<typeof vi.fn>;
}

function setupPrefs(overrides: MockPrefsResult = {}): MockPrefsResult {
  const mock: MockPrefsResult = {
    data: undefined,
    isLoading: false,
    isError: false,
    isSaving: false,
    saveError: null,
    patchPreferences: vi.fn(),
    ...overrides,
  };
  (usePreferences as any).mockReturnValue(mock);
  return mock;
}

function setupAuth(overrides: Record<string, unknown> = {}) {
  (useAuth as any).mockReturnValue({
    data: {
      user_id: 'user-123',
      username: 'alice',
      role: 'admin',
      permissions: [],
      csrf_required: false,
      session_expires_at: '2026-01-01T00:00:00Z',
      step_up_until: null,
      locale: null,
      ...overrides,
    },
  });
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('SettingsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    window.localStorage.clear();
    __resetI18n();
    setupAuth();
    setupPrefs();
  });

  afterEach(() => {
    __resetI18n();
  });

  // --- 1. Renders both panels and their rows in English ---
  it('renders the appearance and account panels with account fields', () => {
    setupPrefs();
    renderWithClient(<SettingsPage />);

    expect(screen.getByRole('heading', { name: 'Settings', level: 2 })).toBeInTheDocument();
    expect(screen.getByTestId('settings-appearance-panel')).toHaveTextContent('Appearance');
    expect(screen.getByTestId('settings-account-panel')).toHaveTextContent('Account');

    // Account rows. The username is an editable input (UsernameRow), so
    // assert its value rather than text content; the hint below it
    // explains the non-unique-display-label identity model.
    expect(screen.getByLabelText('Username')).toHaveValue('alice');
    expect(screen.getByTestId('settings-username')).toHaveTextContent(
      'Display name - it may duplicate another user.',
    );
    expect(screen.getByTestId('settings-role')).toHaveTextContent('Admin');
    expect(screen.getByTestId('settings-user-id')).toHaveTextContent('user-123');
    expect(screen.getByTestId('settings-session-expires')).toHaveTextContent('1/1/2026');
    expect(screen.getByTestId('settings-step-up-until')).toHaveTextContent('None');

    // Actions
    expect(screen.getByTestId('settings-api-keys-link')).toHaveAttribute('href', '/app/api-keys');
    expect(screen.getByTestId('settings-logout')).toHaveTextContent('Sign Out');
  });

  // --- 2. Theme segmented control calls back with the picked theme ---
  it('applies the light theme locally and patches it to the backend', () => {
    const prefs = setupPrefs();
    renderWithClient(<SettingsPage />);
    const { setTheme } = (useTheme as any).mock.results[0].value;

    fireEvent.click(screen.getByTestId('settings-theme-light'));

    expect(setTheme).toHaveBeenCalledWith('light');
    expect(prefs.patchPreferences).toHaveBeenCalledWith({
      preferences: { theme: 'light' },
    });
  });

  // --- 3. Language switch patches the locale and flips the copy to Chinese ---
  it('switches the locale to Chinese and patches it', async () => {
    const prefs = setupPrefs();
    renderWithClient(<SettingsPage />);

    fireEvent.click(screen.getByTestId('settings-language-zh'));

    expect(prefs.patchPreferences).toHaveBeenCalledWith({ locale: 'zh' });

    // The real i18n store was switched: the settings copy turns Chinese.
    await waitFor(() => {
      expect(screen.getByRole('heading', { name: '设置', level: 2 })).toBeInTheDocument();
    });
    expect(screen.getByTestId('settings-account-panel')).toHaveTextContent('账户');
    expect(screen.getByTestId('settings-logout')).toHaveTextContent('退出登录');
  });

  // --- 4. Font scale ---
  it('patches the picked font scale', () => {
    const prefs = setupPrefs();
    renderWithClient(<SettingsPage />);

    fireEvent.click(screen.getByTestId('settings-font-scale-1.25'));
    expect(prefs.patchPreferences).toHaveBeenCalledWith({
      preferences: { fontScale: 1.25 },
    });
  });

  it('applies a backend font scale as a document zoom', () => {
    setupPrefs({ data: { locale: null, theme: null, fontScale: 1.25, reducedMotion: null } });
    renderWithClient(<SettingsPage />);
    expect(document.documentElement.style.zoom).toBe('1.25');
  });

  // --- 5. Reduced motion ---
  it('patches the reduced-motion toggle', () => {
    const prefs = setupPrefs();
    renderWithClient(<SettingsPage />);

    // No preference + no OS hint -> switch is off.
    expect(screen.getByTestId('settings-reduced-motion')).toHaveAttribute('aria-checked', 'false');

    fireEvent.click(screen.getByTestId('settings-reduced-motion'));
    expect(prefs.patchPreferences).toHaveBeenCalledWith({
      preferences: { reducedMotion: true },
    });
  });

  it('installs the reduced-motion style override for a backend preference', () => {
    setupPrefs({
      data: { locale: null, theme: null, fontScale: null, reducedMotion: true },
    });
    renderWithClient(<SettingsPage />);

    const style = document.getElementById('agentnet-reduced-motion');
    expect(style).not.toBeNull();
    expect(style?.textContent).toContain('pixel-scanlines');

    // The switch reflects the effective value.
    expect(screen.getByTestId('settings-reduced-motion')).toHaveAttribute('aria-checked', 'true');
  });

  // --- 6. Server preference overrides the local theme pick ---
  it('syncs the local theme when the server prefers light', () => {
    setupPrefs({ data: { locale: null, theme: 'light', fontScale: null, reducedMotion: null } });
    renderWithClient(<SettingsPage />);
    const { setTheme } = (useTheme as any).mock.results[0].value;

    expect(setTheme).toHaveBeenCalledWith('light');
  });

  // --- 7. Unknown roles fall back to the raw value ---
  it('renders unknown roles verbatim', () => {
    setupAuth({ role: 'auditor' });
    renderWithClient(<SettingsPage />);
    expect(screen.getByTestId('settings-role')).toHaveTextContent('auditor');
  });

  it('maps the super_admin role label', () => {
    setupAuth({ role: 'super_admin' });
    renderWithClient(<SettingsPage />);
    expect(screen.getByTestId('settings-role')).toHaveTextContent('Super Admin');
  });

  // --- 8. Error states ---
  it('shows the load error banner when the preferences query fails', () => {
    setupPrefs({ isError: true });
    renderWithClient(<SettingsPage />);
    expect(screen.getByText('Failed to load preferences.')).toBeInTheDocument();
  });

  it('shows the save error banner when a patch fails', () => {
    setupPrefs({ saveError: new Error('boom') });
    renderWithClient(<SettingsPage />);
    expect(screen.getByText('Failed to save preferences.')).toBeInTheDocument();
  });

  // --- 9. Loading state ---
  it('renders the loading state while preferences load', () => {
    setupPrefs({ isLoading: true });
    const { container } = renderWithClient(<SettingsPage />);
    expect(container.querySelector('.animate-spin')).toBeInTheDocument();
  });

  // --- 10. Sign out invokes the logout mutation ---
  it('calls logout when the sign out button is clicked', () => {
    renderWithClient(<SettingsPage />);
    const { mutate } = (useLogout as any).mock.results[0].value as {
      mutate: ReturnType<typeof vi.fn>;
    };

    fireEvent.click(screen.getByTestId('settings-logout'));
    expect(mutate).toHaveBeenCalled();
  });

  // --- 11. Username rename (non-unique display label, PATCH /me/profile) ---
  it('renames the user via the profile endpoint', async () => {
    const apiModule = await import('../../../api/client');
    const patch = vi.mocked(apiModule.default.patch);
    renderWithClient(<SettingsPage />);

    const input = screen.getByLabelText('Username') as HTMLInputElement;
    fireEvent.change(input, { target: { value: 'alice-2' } });
    fireEvent.click(screen.getByRole('button', { name: 'Save' }));

    await waitFor(() =>
      expect(patch).toHaveBeenCalledWith('/v1/dashboard/auth/me/profile', {
        username: 'alice-2',
      }),
    );
  });
});

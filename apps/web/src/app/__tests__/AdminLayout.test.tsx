import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { RouterForTesting } from '../../test-utils';
import AdminLayout from '../AdminLayout';

vi.mock('../../hooks/useAuth', () => ({
  useAuth: vi.fn(),
  useLogout: vi.fn(() => ({ mutate: vi.fn() })),
}));

import { useAuth } from '../../hooks/useAuth';

function renderLayout() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });

  vi.mocked(useAuth).mockReturnValue({
    data: { username: 'admin1', role: 'admin', user_id: '1', permissions: [], csrf_required: false, session_expires_at: '', step_up_until: null },
    isLoading: false,
    isError: false,
    error: null,
  } as any);

  return render(
    <QueryClientProvider client={queryClient}>
      <RouterForTesting initialEntries={['/admin/overview']}>
        <AdminLayout />
      </RouterForTesting>
    </QueryClientProvider>,
  );
}

describe('AdminLayout', () => {
  it('has no emoji in the enterprise banner', () => {
    const { container } = renderLayout();
    const emojiRegex = /[\u{1F300}-\u{1F9FF}\u{2600}-\u{26FF}\u{2700}-\u{27BF}]/u;
    // DashboardShell renders the enterprise banner (pixel restyle: queried
    // by testid instead of a Tailwind class).
    const banner = container.querySelector('[data-testid="enterprise-banner"]');
    expect(banner).toBeTruthy();
    expect(emojiRegex.test(banner?.textContent || '')).toBe(false);
  });

  it('shows Enterprise label in sidebar', () => {
    renderLayout();
    // Sidebar scope switcher plus the mobile bottom-bar scope button.
    expect(screen.getAllByText('Enterprise').length).toBeGreaterThan(0);
  });
});
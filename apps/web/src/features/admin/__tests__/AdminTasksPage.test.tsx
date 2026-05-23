import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { RouterForTesting } from '../../../test-utils';
import AdminTasksPage from '../AdminTasksPage';

vi.mock('../../../api/client', () => ({
  default: { get: vi.fn(), post: vi.fn() },
}));

vi.mock('../../../hooks/useAuth', () => ({
  useAuth: vi.fn(),
}));

import api from '../../../api/client';
import { useAuth } from '../../../hooks/useAuth';

function renderWithClient(ui: React.ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false, refetchOnWindowFocus: false },
      mutations: { retry: false },
    },
  });
  return render(<QueryClientProvider client={queryClient}><RouterForTesting>{ui}</RouterForTesting></QueryClientProvider>);
}

const mockTasks = {
  tasks: [
    {
      task_id: 'aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee',
      status: 'pending',
      owner_username: 'alice',
      sender_agent: 'AGT-001',
      target_agent: 'AGT-002',
      created_at: '2024-01-01',
    },
    {
      task_id: 'ffffffff-gggg-hhhh-iiii-jjjjjjjjjjjj',
      status: 'running',
      owner_username: 'bob',
      sender_agent: 'AGT-003',
      target_agent: 'AGT-004',
      created_at: '2024-01-02',
    },
    {
      task_id: 'kkkkkkkk-llll-mmmm-nnnn-oooooooooooo',
      status: 'completed',
      owner_username: 'charlie',
      sender_agent: 'AGT-005',
      target_agent: 'AGT-006',
      created_at: '2024-01-03',
    },
  ],
  total: 3,
};

function setupAuth(overrides: Record<string, any> = {}) {
  (useAuth as any).mockReturnValue({
    data: {
      user_id: 'admin1',
      username: 'admin',
      role: 'super_admin',
      permissions: [],
      step_up_until: null,
      ...overrides,
    },
    isLoading: false,
    isError: false,
  });
}

function clickConfirmDialogButton(label: string) {
  fireEvent.click(screen.getByRole('button', { name: label }));
}

describe('AdminTasksPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    (api.get as any).mockResolvedValue({ data: mockTasks });
  });

  it('renders task table with data', async () => {
    setupAuth();
    renderWithClient(<AdminTasksPage />);

    await waitFor(() => {
      expect(screen.getByText('alice')).toBeInTheDocument();
      expect(screen.getByText('bob')).toBeInTheDocument();
    });
  });

  it('shows Cancel button for pending tasks as super_admin', async () => {
    setupAuth();
    renderWithClient(<AdminTasksPage />);

    await waitFor(() => {
      const cancelButtons = screen.getAllByRole('button', { name: 'Cancel' });
      expect(cancelButtons.length).toBe(2); // pending + running
    });
  });

  it('shows Cancel for pending but not running as admin', async () => {
    setupAuth({ role: 'admin' });
    renderWithClient(<AdminTasksPage />);

    await waitFor(() => {
      const cancelButtons = screen.getAllByRole('button', { name: 'Cancel' });
      expect(cancelButtons.length).toBe(1); // only pending
      expect(screen.getByText('Super admin required')).toBeInTheDocument();
    });
  });

  it('shows dash for completed tasks', async () => {
    setupAuth();
    renderWithClient(<AdminTasksPage />);

    await waitFor(() => {
      expect(screen.getByText('-')).toBeInTheDocument();
    });
  });

  it('opens confirm dialog when Cancel is clicked on pending task', async () => {
    setupAuth();
    renderWithClient(<AdminTasksPage />);

    await waitFor(() => {
      expect(screen.getAllByRole('button', { name: 'Cancel' })[0]).toBeInTheDocument();
    });

    fireEvent.click(screen.getAllByRole('button', { name: 'Cancel' })[0]);

    expect(screen.getByRole('heading', { name: 'Cancel Task' })).toBeInTheDocument();
  });

  it('calls cancel API for pending task without step-up', async () => {
    setupAuth({ role: 'admin', step_up_until: null });
    (api.post as any).mockResolvedValue({ data: { ok: true } });
    renderWithClient(<AdminTasksPage />);

    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Cancel' })).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: 'Cancel' })); // pending task cancel
    clickConfirmDialogButton('Cancel Task'); // confirm dialog

    await waitFor(() => {
      expect(api.post).toHaveBeenCalledWith(
        '/v1/dashboard/admin/tasks/aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee/cancel'
      );
    });
  });

  it('shows step-up dialog for running task cancel when step-up is needed', async () => {
    setupAuth({ step_up_until: null });
    renderWithClient(<AdminTasksPage />);

    await waitFor(() => {
      const buttons = screen.getAllByRole('button', { name: 'Cancel' });
      expect(buttons.length).toBe(2);
    });

    fireEvent.click(screen.getAllByRole('button', { name: 'Cancel' })[1]); // running task
    clickConfirmDialogButton('Cancel Task'); // confirm

    await waitFor(() => {
      expect(screen.getByText('Step-Up Verification')).toBeInTheDocument();
    });
  });

  it('calls cancel API directly for running task when step-up is not needed', async () => {
    setupAuth({ step_up_until: new Date(Date.now() + 3600000).toISOString() });
    (api.post as any).mockResolvedValue({ data: { ok: true } });
    renderWithClient(<AdminTasksPage />);

    await waitFor(() => {
      expect(screen.getAllByRole('button', { name: 'Cancel' }).length).toBe(2);
    });

    fireEvent.click(screen.getAllByRole('button', { name: 'Cancel' })[1]); // running task
    clickConfirmDialogButton('Cancel Task'); // confirm

    await waitFor(() => {
      expect(api.post).toHaveBeenCalledWith(
        '/v1/dashboard/admin/tasks/ffffffff-gggg-hhhh-iiii-jjjjjjjjjjjj/cancel'
      );
    });
  });

  it('shows error message on cancel failure', async () => {
    setupAuth({ role: 'admin' });
    (api.post as any).mockRejectedValue({
      response: { data: { detail: 'Task not found' } },
    });
    renderWithClient(<AdminTasksPage />);

    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Cancel' })).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }));
    clickConfirmDialogButton('Cancel Task');

    await waitFor(() => {
      expect(screen.getByTestId('action-error')).toHaveTextContent('Task not found');
    });
  });

  it('renders View links for each task', async () => {
    setupAuth();
    renderWithClient(<AdminTasksPage />);

    await waitFor(() => {
      const viewLinks = screen.getAllByText('View');
      expect(viewLinks.length).toBe(3);
    });

    const firstLink = screen.getAllByText('View')[0].closest('a');
    expect(firstLink).toHaveAttribute('href', '/admin/tasks/aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee');

    const secondLink = screen.getAllByText('View')[1].closest('a');
    expect(secondLink).toHaveAttribute('href', '/admin/tasks/ffffffff-gggg-hhhh-iiii-jjjjjjjjjjjj');
  });

  describe('Expire task', () => {
    it('shows Expire button for super_admin on pending and running tasks', async () => {
      setupAuth();
      renderWithClient(<AdminTasksPage />);

      await waitFor(() => {
        const expireButtons = screen.getAllByRole('button', { name: 'Expire' });
        expect(expireButtons.length).toBe(2); // pending + running
      });
    });

    it('does not show Expire button for admin (non-super_admin)', async () => {
      setupAuth({ role: 'admin' });
      renderWithClient(<AdminTasksPage />);

      await waitFor(() => {
        expect(screen.getByText('bob')).toBeInTheDocument();
      });

      expect(screen.queryByRole('button', { name: 'Expire' })).toBeNull();
    });

    it('does not show Expire button for regular user', async () => {
      setupAuth({ role: 'user' });
      renderWithClient(<AdminTasksPage />);

      await waitFor(() => {
        expect(screen.getByText('Admin required')).toBeInTheDocument();
      });

      expect(screen.queryByRole('button', { name: 'Expire' })).toBeNull();
    });

    it('shows confirm dialog when Expire is clicked', async () => {
      setupAuth();
      renderWithClient(<AdminTasksPage />);

      await waitFor(() => {
        expect(screen.getAllByRole('button', { name: 'Expire' })[0]).toBeInTheDocument();
      });

      fireEvent.click(screen.getAllByRole('button', { name: 'Expire' })[0]);

      expect(screen.getByRole('heading', { name: 'Expire Task' })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: 'Expire Task' })).toBeInTheDocument();
    });

    it('shows step-up dialog after confirming expire', async () => {
      setupAuth({ step_up_until: null });
      renderWithClient(<AdminTasksPage />);

      await waitFor(() => {
        expect(screen.getAllByRole('button', { name: 'Expire' })[0]).toBeInTheDocument();
      });

      fireEvent.click(screen.getAllByRole('button', { name: 'Expire' })[0]);
      clickConfirmDialogButton('Expire Task');

      await waitFor(() => {
        expect(screen.getByText('Step-Up Verification')).toBeInTheDocument();
      });
    });

    it('calls expire API after step-up success', async () => {
      setupAuth({ step_up_until: null });
      (api.post as any).mockImplementation((url: string) => {
        if (url === '/v1/dashboard/auth/step-up') {
          return Promise.resolve({ data: { ok: true } });
        }
        return Promise.resolve({ data: { ok: true } });
      });
      renderWithClient(<AdminTasksPage />);

      await waitFor(() => {
        expect(screen.getAllByRole('button', { name: 'Expire' })[0]).toBeInTheDocument();
      });

      fireEvent.click(screen.getAllByRole('button', { name: 'Expire' })[0]);
      clickConfirmDialogButton('Expire Task');

      await waitFor(() => {
        expect(screen.getByTestId('step-up-input')).toBeInTheDocument();
      });

      fireEvent.change(screen.getByTestId('step-up-input'), { target: { value: 'test-key' } });
      fireEvent.click(screen.getByRole('button', { name: 'Verify' }));

      await waitFor(() => {
        expect(api.post).toHaveBeenCalledWith(
          '/v1/dashboard/admin/tasks/aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee/expire'
        );
      });
    });

    it('shows error message on expire failure', async () => {
      setupAuth({ step_up_until: null });
      (api.post as any).mockImplementation((url: string) => {
        if (url === '/v1/dashboard/auth/step-up') {
          return Promise.resolve({ data: { ok: true } });
        }
        return Promise.reject({
          response: { data: { detail: 'Cannot expire task in completed state' } },
        });
      });
      renderWithClient(<AdminTasksPage />);

      await waitFor(() => {
        expect(screen.getAllByRole('button', { name: 'Expire' })[0]).toBeInTheDocument();
      });

      fireEvent.click(screen.getAllByRole('button', { name: 'Expire' })[0]);
      clickConfirmDialogButton('Expire Task');

      await waitFor(() => {
        expect(screen.getByTestId('step-up-input')).toBeInTheDocument();
      });

      fireEvent.change(screen.getByTestId('step-up-input'), { target: { value: 'test-key' } });
      fireEvent.click(screen.getByRole('button', { name: 'Verify' }));

      await waitFor(() => {
        expect(screen.getByTestId('action-error')).toHaveTextContent('Cannot expire task in completed state');
      });
    });
  });
});

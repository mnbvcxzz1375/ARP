import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Route, Routes } from 'react-router-dom';
import { RouterForTesting } from '../../../test-utils';
import AdminTaskDetailPage from '../AdminTaskDetailPage';

vi.mock('../../../api/client', () => ({
  default: { get: vi.fn() },
}));

import api from '../../../api/client';

const mockTask = {
  task_id: 'admin-task-001-abcd-efgh-ijkl',
  status: 'failed',
  delivery_status: 'delivered',
  retry_count: 2,
  payload_preview: '{"command": "deploy"}',
  result_preview: null,
  error_message: 'Connection timeout',
  owner_username: 'charlie',
  created_at: '2024-04-01T10:00:00Z',
  updated_at: '2024-04-01T10:01:00Z',
};

function renderDetail(taskId: string) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false, refetchOnWindowFocus: false },
    },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <RouterForTesting initialEntries={[`/admin/tasks/${taskId}`]}>
        <Routes>
          <Route path="/admin/tasks/:taskId" element={<AdminTaskDetailPage />} />
        </Routes>
      </RouterForTesting>
    </QueryClientProvider>,
  );
}

describe('AdminTaskDetailPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    (api.get as any).mockResolvedValue({ data: mockTask });
  });

  it('renders task detail data with owner', async () => {
    renderDetail('admin-task-001-abcd-efgh-ijkl');

    await waitFor(() => {
      expect(screen.getByText(/Task admin-ta/)).toBeInTheDocument();
    });

    expect(screen.getByText('charlie')).toBeInTheDocument();
    expect(screen.getByText('Failed')).toBeInTheDocument();
    expect(screen.getByText('delivered')).toBeInTheDocument();
    expect(screen.getByText('2')).toBeInTheDocument();
    expect(screen.getByText('Connection timeout')).toBeInTheDocument();
    expect(screen.getByText('{"command": "deploy"}')).toBeInTheDocument();
  });

  it('fetches the correct endpoint', async () => {
    renderDetail('admin-task-001-abcd-efgh-ijkl');

    await waitFor(() => {
      expect(api.get).toHaveBeenCalledWith('/v1/dashboard/admin/tasks/admin-task-001-abcd-efgh-ijkl');
    });
  });

  it('shows error state on failure', async () => {
    (api.get as any).mockRejectedValue(new Error('Network error'));
    renderDetail('task-001');

    await waitFor(() => {
      expect(screen.getByText('Failed to load task detail')).toBeInTheDocument();
    });
  });

  it('renders back link to admin tasks list', async () => {
    renderDetail('admin-task-001-abcd-efgh-ijkl');

    await waitFor(() => {
      expect(screen.getByText('Back to Tasks')).toBeInTheDocument();
    });
    const link = screen.getByText('Back to Tasks').closest('a');
    expect(link).toHaveAttribute('href', '/admin/tasks');
  });

  it('renders code blocks as text safely', async () => {
    renderDetail('admin-task-001-abcd-efgh-ijkl');

    await waitFor(() => {
      expect(screen.getByText('{"command": "deploy"}')).toBeInTheDocument();
    });

    const preElements = screen.getAllByText('{"command": "deploy"}');
    expect(preElements[0].tagName).toBe('PRE');
  });

  it('renders error in red-styled block', async () => {
    renderDetail('admin-task-001-abcd-efgh-ijkl');

    await waitFor(() => {
      const errorPre = screen.getByText('Connection timeout');
      expect(errorPre.tagName).toBe('PRE');
      expect(errorPre.className).toContain('red');
    });
  });

  it('does not show content section when all content fields are null', async () => {
    const emptyTask = {
      ...mockTask,
      payload_preview: null,
      result_preview: null,
      error_message: null,
    };
    (api.get as any).mockResolvedValue({ data: emptyTask });
    renderDetail('empty-task');

    await waitFor(() => {
      expect(screen.queryByText('Payload')).not.toBeInTheDocument();
      expect(screen.queryByText('Result')).not.toBeInTheDocument();
      expect(screen.queryByText('Error')).not.toBeInTheDocument();
    });
  });
});

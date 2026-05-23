import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Route, Routes } from 'react-router-dom';
import { RouterForTesting } from '../../../test-utils';
import TaskDetailPage from '../TaskDetailPage';

vi.mock('../../../api/client', () => ({
  default: { get: vi.fn() },
}));

import api from '../../../api/client';

const mockTask = {
  task_id: 'task-0001-abcd-efgh-ijklmnopqrst',
  status: 'completed',
  delivery_status: 'delivered',
  retry_count: 1,
  payload_preview: '{"action": "test"}',
  result_preview: '{"ok": true}',
  error_message: null,
  created_at: '2024-03-01T08:00:00Z',
  updated_at: '2024-03-01T08:05:00Z',
};

const mockMessages = {
  messages: [
    { message_id: 'msg-001', type: 'task_request', delivery_status: 'delivered', created_at: '2024-03-01T08:00:01Z' },
    { message_id: 'msg-002', type: 'task_response', delivery_status: 'delivered', created_at: '2024-03-01T08:05:00Z' },
  ],
  total: 2,
};

const mockProgress = {
  progress: [
    { seq: 1, status: 'running', progress_pct: 50, message: 'halfway', created_at: '2024-03-01T08:02:00Z' },
  ],
  total: 1,
};

function renderDetail(taskId: string) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false, refetchOnWindowFocus: false },
    },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <RouterForTesting initialEntries={[`/app/tasks/${taskId}`]}>
        <Routes>
          <Route path="/app/tasks/:taskId" element={<TaskDetailPage />} />
        </Routes>
      </RouterForTesting>
    </QueryClientProvider>,
  );
}

describe('TaskDetailPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    (api.get as any).mockImplementation((url: string) => {
      if (url.includes('/messages')) return Promise.resolve({ data: mockMessages });
      if (url.includes('/progress')) return Promise.resolve({ data: mockProgress });
      return Promise.resolve({ data: mockTask });
    });
  });

  it('renders task detail data', async () => {
    renderDetail('task-0001-abcd-efgh-ijklmnopqrst');

    await waitFor(() => {
      expect(screen.getByText(/Task task-000/)).toBeInTheDocument();
    });

    expect(screen.getByText('Completed')).toBeInTheDocument();
    expect(screen.getAllByText('delivered').length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText('1').length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText('{"action": "test"}')).toBeInTheDocument();
    expect(screen.getByText('{"ok": true}')).toBeInTheDocument();
  });

  it('fetches task, messages, and progress endpoints', async () => {
    renderDetail('task-0001-abcd-efgh-ijklmnopqrst');

    await waitFor(() => {
      expect(api.get).toHaveBeenCalledWith('/v1/dashboard/tasks/task-0001-abcd-efgh-ijklmnopqrst');
      expect(api.get).toHaveBeenCalledWith('/v1/dashboard/tasks/task-0001-abcd-efgh-ijklmnopqrst/messages');
      expect(api.get).toHaveBeenCalledWith('/v1/dashboard/tasks/task-0001-abcd-efgh-ijklmnopqrst/progress');
    });
  });

  it('shows error state when task fetch fails', async () => {
    (api.get as any).mockRejectedValue(new Error('Network error'));
    renderDetail('task-0001');

    await waitFor(() => {
      expect(screen.getByText('Failed to load task detail')).toBeInTheDocument();
    });
  });

  it('renders messages table', async () => {
    renderDetail('task-0001-abcd-efgh-ijklmnopqrst');

    await waitFor(() => {
      expect(screen.getByText('task_request')).toBeInTheDocument();
      expect(screen.getByText('task_response')).toBeInTheDocument();
    });
  });

  it('renders progress table', async () => {
    renderDetail('task-0001-abcd-efgh-ijklmnopqrst');

    await waitFor(() => {
      expect(screen.getByText('halfway')).toBeInTheDocument();
      expect(screen.getByText('50%')).toBeInTheDocument();
    });
  });

  it('renders back link to tasks list', async () => {
    renderDetail('task-0001-abcd-efgh-ijklmnopqrst');

    await waitFor(() => {
      expect(screen.getByText('Back to Tasks')).toBeInTheDocument();
    });
    const link = screen.getByText('Back to Tasks').closest('a');
    expect(link).toHaveAttribute('href', '/app/tasks');
  });

  it('shows error message section when present', async () => {
    const taskWithError = { ...mockTask, error_message: 'Something went wrong', payload_preview: null, result_preview: null };
    (api.get as any).mockImplementation((url: string) => {
      if (url.includes('/messages')) return Promise.resolve({ data: mockMessages });
      if (url.includes('/progress')) return Promise.resolve({ data: mockProgress });
      return Promise.resolve({ data: taskWithError });
    });
    renderDetail('task-with-error');

    await waitFor(() => {
      expect(screen.getByText('Something went wrong')).toBeInTheDocument();
    });
  });

  it('renders code blocks as text without dangerouslySetInnerHTML', async () => {
    renderDetail('task-0001-abcd-efgh-ijklmnopqrst');

    await waitFor(() => {
      expect(screen.getByText('{"action": "test"}')).toBeInTheDocument();
    });

    // Verify content is rendered as text in a <pre> tag, not via dangerouslySetInnerHTML
    const preElements = screen.getAllByText('{"action": "test"}');
    expect(preElements[0].tagName).toBe('PRE');
  });
});

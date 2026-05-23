import { Link } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import api from '../../api/client';
import { useAuth } from '../../hooks/useAuth';
import DataTable from '../../components/DataTable';
import Pagination from '../../components/Pagination';
import StatusBadge from '../../components/StatusBadge';
import LoadingState from '../../components/LoadingState';
import ErrorState from '../../components/ErrorState';
import ConfirmDialog from '../../components/ConfirmDialog';
import StepUpDialog from '../../components/StepUpDialog';

type PendingTaskAction = {
  type: 'cancel';
  taskId: string;
  isRunning: boolean;
} | {
  type: 'expire';
  taskId: string;
} | null;

function isStepUpNeeded(stepUpUntil: string | null | undefined): boolean {
  if (!stepUpUntil) return true;
  return new Date(stepUpUntil) <= new Date();
}

export default function AdminTasksPage() {
  const [page, setPage] = useState(1);
  const limit = 20;
  const queryClient = useQueryClient();
  const { data: auth } = useAuth();
  const isSuperAdmin = auth?.role === 'super_admin';
  const isAdmin = auth?.role === 'admin' || isSuperAdmin;

  const { data, isLoading, isError } = useQuery({
    queryKey: ['admin/tasks', page, limit],
    queryFn: () => api.get('/v1/dashboard/admin/tasks', { params: { offset: (page - 1) * limit, limit } }).then((r) => r.data),
  });

  const [pendingAction, setPendingAction] = useState<PendingTaskAction>(null);
  const [showStepUp, setShowStepUp] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  const cancelMutation = useMutation({
    mutationFn: (taskId: string) =>
      api.post(`/v1/dashboard/admin/tasks/${taskId}/cancel`),
    onSuccess: () => {
      setPendingAction(null);
      setShowStepUp(false);
      setActionError(null);
      queryClient.invalidateQueries({ queryKey: ['admin/tasks'] });
      queryClient.invalidateQueries({ queryKey: ['admin/overview'] });
    },
    onError: (err: any) => {
      setPendingAction(null);
      setShowStepUp(false);
      setActionError(err?.response?.data?.detail || 'Failed to cancel task');
    },
  });

  const expireMutation = useMutation({
    mutationFn: (taskId: string) =>
      api.post(`/v1/dashboard/admin/tasks/${taskId}/expire`),
    onSuccess: () => {
      setPendingAction(null);
      setShowStepUp(false);
      setActionError(null);
      queryClient.invalidateQueries({ queryKey: ['admin/tasks'] });
      queryClient.invalidateQueries({ queryKey: ['admin/overview'] });
    },
    onError: (err: any) => {
      setPendingAction(null);
      setShowStepUp(false);
      setActionError(err?.response?.data?.detail || 'Failed to expire task');
    },
  });

  const handleConfirmAction = () => {
    if (!pendingAction) return;
    setActionError(null);
    if (pendingAction.type === 'expire') {
      // Expire always requires step-up
      setShowStepUp(true);
    } else if (pendingAction.isRunning && isStepUpNeeded(auth?.step_up_until)) {
      setShowStepUp(true);
    } else {
      cancelMutation.mutate(pendingAction.taskId);
    }
  };

  const handleStepUpSuccess = () => {
    setShowStepUp(false);
    if (!pendingAction) return;
    if (pendingAction.type === 'expire') {
      expireMutation.mutate(pendingAction.taskId);
    } else {
      cancelMutation.mutate(pendingAction.taskId);
    }
  };

  if (isLoading) return <LoadingState />;
  if (isError) return <ErrorState message="Failed to load tasks" />;

  return (
    <div>
      <h2 className="text-xl font-semibold mb-6">Tasks</h2>
      {actionError && (
        <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded text-sm text-red-700" data-testid="action-error">
          {actionError}
        </div>
      )}
      <div className="bg-white rounded-lg border overflow-hidden">
        <DataTable
          columns={[
            { key: 'task_id', label: 'ID', render: (r: any) => r.task_id?.slice(0, 8) },
            {
              key: 'details',
              label: '',
              render: (r: any) => (
                <Link to={`/admin/tasks/${r.task_id}`} className="text-blue-600 hover:underline text-xs font-medium">
                  View
                </Link>
              ),
            },
            { key: 'status', label: 'Status', render: (r: any) => <StatusBadge status={r.status} /> },
            { key: 'owner_username', label: 'Owner' },
            { key: 'sender_agent', label: 'Sender', render: (r: any) => r.sender_agent?.slice(0, 8) },
            { key: 'target_agent', label: 'Target', render: (r: any) => r.target_agent?.slice(0, 8) },
            { key: 'created_at', label: 'Created' },
            {
              key: 'actions',
              label: 'Actions',
              render: (r: any) => {
                const taskStatus = r.status;
                const isTerminal = ['completed', 'failed', 'cancelled', 'expired'].includes(taskStatus);
                if (taskStatus === 'pending') {
                  if (!isAdmin) {
                    return <span className="text-xs text-gray-400">Admin required</span>;
                  }
                  return (
                    <>
                      <button
                        onClick={() => setPendingAction({ type: 'cancel', taskId: r.task_id, isRunning: false })}
                        disabled={cancelMutation.isPending}
                        className="px-2 py-1 text-xs font-medium text-red-700 bg-red-50 border border-red-200 rounded hover:bg-red-100 disabled:opacity-50"
                      >
                        Cancel
                      </button>
                      {isSuperAdmin && (
                        <button
                          onClick={() => setPendingAction({ type: 'expire', taskId: r.task_id })}
                          disabled={expireMutation.isPending}
                          className="ml-1 px-2 py-1 text-xs font-medium text-orange-700 bg-orange-50 border border-orange-200 rounded hover:bg-orange-100 disabled:opacity-50"
                        >
                          Expire
                        </button>
                      )}
                    </>
                  );
                }
                if (taskStatus === 'running') {
                  if (!isSuperAdmin) {
                    return <span className="text-xs text-gray-400">Super admin required</span>;
                  }
                  return (
                    <>
                      <button
                        onClick={() => setPendingAction({ type: 'cancel', taskId: r.task_id, isRunning: true })}
                        disabled={cancelMutation.isPending}
                        className="px-2 py-1 text-xs font-medium text-red-700 bg-red-50 border border-red-200 rounded hover:bg-red-100 disabled:opacity-50"
                      >
                        Cancel
                      </button>
                      <button
                        onClick={() => setPendingAction({ type: 'expire', taskId: r.task_id })}
                        disabled={expireMutation.isPending}
                        className="ml-1 px-2 py-1 text-xs font-medium text-orange-700 bg-orange-50 border border-orange-200 rounded hover:bg-orange-100 disabled:opacity-50"
                      >
                        Expire
                      </button>
                    </>
                  );
                }
                if (!isTerminal && isSuperAdmin) {
                  return (
                    <button
                      onClick={() => setPendingAction({ type: 'expire', taskId: r.task_id })}
                      disabled={expireMutation.isPending}
                      className="px-2 py-1 text-xs font-medium text-orange-700 bg-orange-50 border border-orange-200 rounded hover:bg-orange-100 disabled:opacity-50"
                    >
                      Expire
                    </button>
                  );
                }
                return <span className="text-xs text-gray-400">-</span>;
              },
            },
          ]}
          data={data?.tasks ?? []}
        />
        <Pagination
          offset={(page - 1) * limit}
          limit={limit}
          total={data?.total ?? 0}
          onPageChange={(offset) => setPage(Math.floor(offset / limit) + 1)}
        />
      </div>

      <ConfirmDialog
        open={pendingAction !== null && !showStepUp}
        title={
          pendingAction?.type === 'expire' ? 'Expire Task' : 'Cancel Task'
        }
        message={
          pendingAction?.type === 'expire'
            ? `Force expire task "${pendingAction?.taskId?.slice(0, 8)}"? This will mark the task as expired and stop further processing.`
            : pendingAction?.isRunning
              ? `Cancel running task "${pendingAction?.taskId?.slice(0, 8)}"? This will immediately stop the task and may leave it in an incomplete state.`
              : `Cancel pending task "${pendingAction?.taskId?.slice(0, 8)}"? The task will be marked as cancelled and will not execute.`
        }
        variant="danger"
        confirmLabel={
          pendingAction?.type === 'expire' ? 'Expire Task' : 'Cancel Task'
        }
        onConfirm={handleConfirmAction}
        onCancel={() => {
          setPendingAction(null);
          setActionError(null);
        }}
      />

      <StepUpDialog
        open={showStepUp}
        onSuccess={handleStepUpSuccess}
        onCancel={() => {
          setShowStepUp(false);
          setPendingAction(null);
          setActionError(null);
        }}
      />
    </div>
  );
}

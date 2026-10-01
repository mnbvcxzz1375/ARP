import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api from '../../api/client';
import DataTable from '../../components/DataTable';
import StatusBadge from '../../components/StatusBadge';
import RiskBadge from '../../components/RiskBadge';
import ConfirmDialog from '../../components/ConfirmDialog';
import LoadingState from '../../components/LoadingState';
import ErrorState from '../../components/ErrorState';
import { ErrorBanner, PageTitle, PixButton } from '../connections/pixel-ui';
import { useT } from '../../i18n';

interface DialogState {
  approvalId: string;
  action: 'accept' | 'reject';
}

export default function ApprovalsPage() {
  const t = useT();
  const queryClient = useQueryClient();
  const [dialogState, setDialogState] = useState<DialogState | null>(null);
  const [error, setError] = useState<string | null>(null);

  const { data, isLoading, isError: isQueryError } = useQuery({
    queryKey: ['approvals'],
    queryFn: () => api.get('/v1/dashboard/approvals').then((r) => r.data),
  });

  const acceptMutation = useMutation({
    mutationFn: (approvalId: string) =>
      api.post(`/v1/dashboard/approvals/${approvalId}/accept`),
    onSuccess: () => {
      setDialogState(null);
      setError(null);
      queryClient.invalidateQueries({ queryKey: ['approvals'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard/overview'] });
    },
    onError: (err: unknown) => {
      setDialogState(null);
      const detail = (err as any)?.response?.data?.detail;
      setError(detail || (err as any)?.message || t('approvals.error.acceptFailed'));
    },
  });

  const rejectMutation = useMutation({
    mutationFn: (approvalId: string) =>
      api.post(`/v1/dashboard/approvals/${approvalId}/reject`),
    onSuccess: () => {
      setDialogState(null);
      setError(null);
      queryClient.invalidateQueries({ queryKey: ['approvals'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard/overview'] });
    },
    onError: (err: unknown) => {
      setDialogState(null);
      const detail = (err as any)?.response?.data?.detail;
      setError(detail || (err as any)?.message || t('approvals.error.rejectFailed'));
    },
  });

  const isMutating = acceptMutation.isPending || rejectMutation.isPending;

  const handleDialogOpen = (approvalId: string, action: 'accept' | 'reject') => {
    setError(null);
    setDialogState({ approvalId, action });
  };

  const handleDialogCancel = () => {
    setDialogState(null);
    setError(null);
  };

  const handleConfirm = () => {
    if (!dialogState || isMutating) return;
    if (dialogState.action === 'accept') {
      acceptMutation.mutate(dialogState.approvalId);
    } else {
      rejectMutation.mutate(dialogState.approvalId);
    }
  };

  if (isLoading) return <LoadingState />;
  if (isQueryError) return <ErrorState message={t('approvals.error.load')} />;

  return (
    <div>
      <PageTitle>{t('approvals.page.title')}</PageTitle>

      {error && <ErrorBanner message={error} />}

      <DataTable
        columns={[
          { key: 'approval_id', label: t('approvals.table.id'), render: (r: any) => r.approval_id?.slice(0, 8) },
          { key: 'type', label: t('approvals.table.type') },
          { key: 'status', label: t('approvals.table.status'), render: (r: any) => <StatusBadge status={r.status} /> },
          { key: 'risk_level', label: t('approvals.table.risk'), render: (r: any) => <RiskBadge level={r.risk_level} /> },
          { key: 'action_kind', label: t('approvals.table.action') },
          { key: 'created_at', label: t('approvals.table.created') },
          {
            key: 'actions',
            label: t('approvals.table.actions'),
            render: (r: any) => {
              if (r.status !== 'pending') return null;
              const isAcceptPending = acceptMutation.isPending;
              const isRejectPending = rejectMutation.isPending;
              return (
                <div className="flex gap-2">
                  <PixButton
                    variant="ok"
                    compact
                    onClick={() => handleDialogOpen(r.approval_id, 'accept')}
                    disabled={isMutating}
                  >
                    {isAcceptPending ? t('approvals.button.accepting') : t('approvals.button.accept')}
                  </PixButton>
                  <PixButton
                    variant="danger"
                    compact
                    onClick={() => handleDialogOpen(r.approval_id, 'reject')}
                    disabled={isMutating}
                  >
                    {isRejectPending ? t('approvals.button.rejecting') : t('approvals.button.reject')}
                  </PixButton>
                </div>
              );
            },
          },
        ]}
        data={data?.approvals ?? []}
      />

      <ConfirmDialog
        open={dialogState !== null}
        title={dialogState?.action === 'accept' ? t('approvals.dialog.acceptTitle') : t('approvals.dialog.rejectTitle')}
        message={
          dialogState?.action === 'accept'
            ? t('approvals.dialog.acceptMessage')
            : t('approvals.dialog.rejectMessage')
        }
        variant={dialogState?.action === 'accept' ? 'default' : 'danger'}
        confirmLabel={dialogState?.action === 'accept' ? t('approvals.dialog.acceptConfirm') : t('approvals.dialog.rejectConfirm')}
        onConfirm={handleConfirm}
        onCancel={handleDialogCancel}
      />
    </div>
  );
}

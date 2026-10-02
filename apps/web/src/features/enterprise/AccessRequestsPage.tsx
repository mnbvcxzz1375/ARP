import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api from '../../api/client';
import { useT, useFormat } from '../../i18n';
import DataTable from '../../components/DataTable';
import Pagination from '../../components/Pagination';
import StatusBadge from '../../components/StatusBadge';
import ConfirmDialog from '../../components/ConfirmDialog';
import LoadingState from '../../components/LoadingState';
import ErrorState from '../../components/ErrorState';
import EmptyState from '../../components/EmptyState';
import {
  ErrorBanner,
  FilterPill,
  NeutralChip,
  PageTitle,
  PixelCopyButton,
  PixelField,
  PixButton,
  PIXEL_INPUT,
} from '../connections/pixel-ui';
import { cn } from '../../lib/utils';

interface DialogState {
  requestId: string;
  action: 'approve' | 'reject';
}

interface ProvisionedResult {
  request_id: string;
  status: string;
  reviewed_by: string;
  user_id: string;
  api_key: string;
  scope_id?: string;
}

export default function AccessRequestsPage() {
  const queryClient = useQueryClient();
  const t = useT();
  const { formatDate } = useFormat();
  const [page, setPage] = useState(1);
  const [statusFilter, setStatusFilter] = useState<string | undefined>(undefined);
  const [dialogState, setDialogState] = useState<DialogState | null>(null);
  const [rejectReason, setRejectReason] = useState('');
  const [rejectError, setRejectError] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [provisionedResult, setProvisionedResult] = useState<ProvisionedResult | null>(null);
  const limit = 20;

  const { data, isLoading, isError } = useQuery({
    queryKey: ['admin/access-requests', page, limit, statusFilter],
    queryFn: () =>
      api
        .get('/v1/dashboard/admin/access-requests', {
          params: { offset: (page - 1) * limit, limit, status_filter: statusFilter || undefined },
        })
        .then((r) => r.data),
  });

  const approveMutation = useMutation({
    mutationFn: (requestId: string) =>
      api.post(`/v1/dashboard/admin/access-requests/${requestId}/approve`),
    onSuccess: (response) => {
      setDialogState(null);
      setError(null);
      setProvisionedResult(response.data);
      queryClient.invalidateQueries({ queryKey: ['admin/access-requests'] });
    },
    onError: (err: unknown) => {
      setDialogState(null);
      const detail = (err as any)?.response?.data?.detail;
      setError(detail || (err as any)?.message || t('enterprise.accessRequests.error.approve'));
    },
  });

  const rejectMutation = useMutation({
    mutationFn: ({ requestId, reason }: { requestId: string; reason: string }) =>
      api.post(`/v1/dashboard/admin/access-requests/${requestId}/reject`, {
        review_notes: reason,
      }),
    onSuccess: () => {
      setDialogState(null);
      setRejectReason('');
      setRejectError(null);
      setError(null);
      queryClient.invalidateQueries({ queryKey: ['admin/access-requests'] });
    },
    onError: (err: unknown) => {
      const detail = (err as any)?.response?.data?.error?.message;
      setError(detail || (err as any)?.message || t('enterprise.accessRequests.error.reject'));
      // Keep dialog open on error so user can fix
    },
  });

  const isMutating = approveMutation.isPending || rejectMutation.isPending;

  const handleDialogOpen = (requestId: string, action: 'approve' | 'reject') => {
    setError(null);
    setRejectReason('');
    setRejectError(null);
    setDialogState({ requestId, action });
  };

  const handleDialogCancel = () => {
    setDialogState(null);
    setRejectReason('');
    setRejectError(null);
    setError(null);
  };

  const handleConfirm = () => {
    if (!dialogState || isMutating) return;
    if (dialogState.action === 'approve') {
      approveMutation.mutate(dialogState.requestId);
    } else {
      if (!rejectReason.trim()) {
        setRejectError(t('enterprise.accessRequests.error.rejectReasonRequired'));
        return;
      }
      rejectMutation.mutate({ requestId: dialogState.requestId, reason: rejectReason });
    }
  };

  if (isLoading) return <LoadingState />;
  if (isError) return <ErrorState message={t('enterprise.accessRequests.error.load')} />;

  // Access-request status filter pills: 'all' is page copy, the rest reuse the
  // shared status labels (namespace `common`) so the pill matches the badge.
  const statusFilterLabels: Record<string, string> = {
    all: t('enterprise.filter.all'),
    pending: t('common.statusLabel.pending'),
    approved: t('common.statusLabel.approved'),
    rejected: t('common.statusLabel.rejected'),
    expired: t('common.statusLabel.expired'),
  };

  return (
    <div>
      <PageTitle>{t('enterprise.accessRequests.title')}</PageTitle>

      {/* Provisioned result: success state as a solid LED green panel (fixed contrast in both themes). */}
      {provisionedResult && (
        <div className="mb-4 border-2 border-[#191a26] bg-pixel-led-green p-4">
          <h3 className="mb-2 font-pixel text-pixel-sm uppercase tracking-pixel text-[#191a26]">
            {t('enterprise.accessRequests.result.title')}
          </h3>
          <div className="flex flex-col gap-2">
            <div className="font-mono text-lg text-[#191a26]">
              <span className="font-pixel text-pixel-sm uppercase tracking-pixel">
                {t('enterprise.accessRequests.result.userId')}
              </span>{' '}
              {provisionedResult.user_id}
            </div>
            {provisionedResult.scope_id && (
              <div className="font-mono text-lg text-[#191a26]">
                <span className="font-pixel text-pixel-sm uppercase tracking-pixel">
                  {t('enterprise.accessRequests.result.scopeId')}
                </span>{' '}
                {provisionedResult.scope_id}
              </div>
            )}
            <div className="flex flex-wrap items-center gap-2">
              <span className="font-pixel text-pixel-sm uppercase tracking-pixel text-[#191a26]">
                {t('enterprise.accessRequests.result.apiKey')}
              </span>
              <code className="select-all break-all border-2 border-[#191a26] bg-pixel-bg px-2 py-0.5 font-mono text-lg text-pixel-fg">
                {provisionedResult.api_key}
              </code>
              <PixelCopyButton text={provisionedResult.api_key} />
            </div>
            <p className="font-mono text-base text-[#191a26]">
              {t('enterprise.accessRequests.result.apiKeyHint')}
            </p>
          </div>
          <button
            onClick={() => setProvisionedResult(null)}
            className="mt-2 border-2 border-[#191a26] bg-pixel-led-green px-3 py-1 font-pixel text-pixel-sm text-[#191a26] hover:bg-[#191a26] hover:text-pixel-led-green"
          >
            {t('enterprise.action.dismiss')}
          </button>
        </div>
      )}

      {error && <ErrorBanner message={error} />}

      <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-center">
        {['all', 'pending', 'approved', 'rejected', 'expired'].map((s) => (
          <FilterPill
            key={s}
            active={(s === 'all' && !statusFilter) || statusFilter === s}
            onClick={() => {
              setStatusFilter(s === 'all' ? undefined : s);
              setPage(1);
            }}
          >
            {statusFilterLabels[s]}
          </FilterPill>
        ))}
      </div>

      {data?.access_requests?.length === 0 ? (
        <EmptyState message={t('enterprise.accessRequests.empty')} />
      ) : (
        <div className="bg-pixel-surface border-2 border-pixel-line">
          <DataTable
            className="border-0"
            columns={[
              { key: 'request_id', label: t('enterprise.table.id'), render: (r: any) => r.request_id?.slice(0, 8) },
              { key: 'applicant_name', label: t('enterprise.table.name') },
              { key: 'applicant_email', label: t('enterprise.accessRequests.table.email') },
              { key: 'organization', label: t('enterprise.accessRequests.table.organization'), render: (r: any) => r.organization || '-' },
              {
                key: 'requested_mode',
                label: t('enterprise.accessRequests.table.mode'),
                render: (r: any) => (
                  <NeutralChip>
                    {r.requested_mode === 'personal' || r.requested_mode === 'enterprise'
                      ? t(`enterprise.accessRequests.mode.${r.requested_mode}`)
                      : r.requested_mode}
                  </NeutralChip>
                ),
              },
              { key: 'status', label: t('enterprise.table.status'), render: (r: any) => <StatusBadge status={r.status} /> },
              {
                key: 'created_at',
                label: t('enterprise.accessRequests.table.submitted'),
                render: (r: any) => formatDate(r.created_at),
              },
              {
                key: 'actions',
                label: '',
                render: (r: any) =>
                  r.status === 'pending' ? (
                    <div className="flex gap-2">
                      <PixButton
                        variant="ok"
                        compact
                        onClick={() => handleDialogOpen(r.request_id, 'approve')}
                        disabled={isMutating}
                      >
                        {t('enterprise.action.approve')}
                      </PixButton>
                      <PixButton
                        variant="danger"
                        compact
                        onClick={() => handleDialogOpen(r.request_id, 'reject')}
                        disabled={isMutating}
                      >
                        {t('enterprise.action.reject')}
                      </PixButton>
                    </div>
                  ) : (
                    <span className="font-mono text-base text-pixel-muted">
                      {r.reviewed_at ? formatDate(r.reviewed_at) : ''}
                    </span>
                  ),
              },
            ]}
            data={data?.access_requests ?? []}
          />
          <Pagination
            offset={(page - 1) * limit}
            limit={limit}
            total={data?.total ?? 0}
            onPageChange={(offset) => setPage(Math.floor(offset / limit) + 1)}
          />
        </div>
      )}

      <ConfirmDialog
        open={dialogState !== null}
        title={
          dialogState?.action === 'approve'
            ? t('enterprise.accessRequests.confirm.approveTitle')
            : t('enterprise.accessRequests.confirm.rejectTitle')
        }
        message={
          dialogState?.action === 'approve'
            ? t('enterprise.accessRequests.confirm.approveMessage')
            : t('enterprise.accessRequests.confirm.rejectMessage')
        }
        variant={dialogState?.action === 'approve' ? 'default' : 'danger'}
        confirmLabel={
          dialogState?.action === 'approve'
            ? t('enterprise.action.approve')
            : t('enterprise.action.reject')
        }
        onConfirm={handleConfirm}
        onCancel={handleDialogCancel}
      >
        {dialogState?.action === 'reject' && (
          <div className="mt-3">
            <PixelField
              label={t('enterprise.accessRequests.form.rejectReason')}
              htmlFor="reject-reason"
            >
              <textarea
                id="reject-reason"
                value={rejectReason}
                onChange={(e) => {
                  setRejectReason(e.target.value);
                  if (rejectError) setRejectError(null);
                }}
                rows={2}
                className={cn(PIXEL_INPUT, rejectError && 'border-pixel-led-red')}
                placeholder={t('enterprise.accessRequests.form.rejectReasonPlaceholder')}
              />
            </PixelField>
            {rejectError && (
              <div className="mt-2 border-2 border-[#191a26] bg-pixel-led-red p-2 font-pixel text-pixel-sm text-[#f4f4fa]">
                {rejectError}
              </div>
            )}
          </div>
        )}
      </ConfirmDialog>
    </div>
  );
}

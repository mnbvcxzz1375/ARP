import { useParams, Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import api from '../../api/client';
import { useT, useFormat } from '../../i18n';
import LoadingState from '../../components/LoadingState';
import ErrorState from '../../components/ErrorState';
import EmptyState from '../../components/EmptyState';
import StatusBadge from '../../components/StatusBadge';
import DataTable from '../../components/DataTable';
import { PageTitle, PixelPanel } from '../connections/pixel-ui';
import { PIXEL_CHIP } from '../../lib/tokens';
import { cn } from '../../lib/utils';

interface AuditEntry {
  audit_id: string;
  actor_type: string;
  actor_id: string;
  action: string;
  resource_type: string | null;
  resource_id: string | null;
  task_id: string | null;
  error_code: string | null;
  request_ip: string | null;
  details: Record<string, unknown> | null;
  created_at: string;
}

export default function AccessRequestDetailPage() {
  const { requestId } = useParams<{ requestId: string }>();
  const t = useT();
  const { formatDateTime } = useFormat();

  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['admin/access-requests', requestId],
    queryFn: () =>
      api
        .get(`/v1/dashboard/admin/access-requests/${requestId}`)
        .then((r) => r.data),
    enabled: !!requestId,
  });

  const { data: auditData, isError: auditError } = useQuery({
    queryKey: ['admin/access-requests', requestId, 'audit-trail'],
    queryFn: () =>
      api
        .get(`/v1/dashboard/admin/access-requests/${requestId}/audit-trail`)
        .then((r) => r.data),
    enabled: !!requestId,
  });

  if (isLoading) return <LoadingState />;
  if (isError) {
    const statusCode = (error as any)?.response?.status;
    if (statusCode === 404) {
      return <ErrorState message={t('enterprise.accessRequestDetail.error.notFound')} />;
    }
    if (statusCode === 403) {
      return <ErrorState message={t('enterprise.error.accessDenied')} />;
    }
    return <ErrorState message={t('enterprise.accessRequestDetail.error.load')} />;
  }

  const auditEntries: AuditEntry[] = auditData?.audit_logs ?? [];

  return (
    <div>
      <div className="mb-4">
        <Link
          to="/enterprise/access-requests"
          className="font-pixel text-pixel-sm text-pixel-accent-2 hover:underline"
        >
          &larr; {t('enterprise.accessRequestDetail.back')}
        </Link>
      </div>

      <PageTitle>{t('enterprise.accessRequestDetail.title')}</PageTitle>

      <PixelPanel bodyClassName="p-4 md:p-6">
        <div className="flex flex-col gap-4">
          <DetailRow
            label={t('enterprise.accessRequestDetail.label.requestId')}
            value={data?.request_id}
          />
          <DetailRow label={t('enterprise.accessRequestDetail.label.status')}>
            <StatusBadge status={data?.status} />
          </DetailRow>

          <SectionLabel>
            {t('enterprise.accessRequestDetail.section.applicant')}
          </SectionLabel>
          <DetailRow label={t('enterprise.accessRequestDetail.label.name')} value={data?.applicant_name} />
          <DetailRow label={t('enterprise.accessRequestDetail.label.email')} value={data?.applicant_email} />
          <DetailRow
            label={t('enterprise.accessRequestDetail.label.organization')}
            value={data?.organization || t('enterprise.accessRequestDetail.value.notProvided')}
          />

          <SectionLabel>
            {t('enterprise.accessRequestDetail.section.requestDetails')}
          </SectionLabel>
          <DetailRow label={t('enterprise.accessRequestDetail.label.requestedMode')}>
            <span
              className={cn(
                'inline-flex items-center px-2 py-0.5 font-pixel text-sm leading-none',
                PIXEL_CHIP.info,
              )}
            >
              {data?.requested_mode === 'personal' || data?.requested_mode === 'enterprise'
                ? t(`enterprise.accessRequests.mode.${data.requested_mode}`)
                : data?.requested_mode}
            </span>
          </DetailRow>
          <DetailRow label={t('enterprise.accessRequestDetail.label.useCase')} value={data?.use_case} />
          <DetailRow
            label={t('enterprise.accessRequestDetail.label.termsAcknowledged')}
            value={data?.terms_acknowledged ? t('enterprise.value.yes') : t('enterprise.value.no')}
          />

          {data?.request_ip && (
            <DetailRow
              label={t('enterprise.accessRequestDetail.label.requestIp')}
              value={data.request_ip}
            />
          )}

          <SectionLabel>
            {t('enterprise.accessRequestDetail.section.review')}
          </SectionLabel>
          <DetailRow
            label={t('enterprise.accessRequestDetail.label.reviewedBy')}
            value={data?.reviewed_by || t('enterprise.accessRequestDetail.value.notReviewed')}
          />
          <DetailRow
            label={t('enterprise.accessRequestDetail.label.reviewedAt')}
            value={
              data?.reviewed_at
                ? formatDateTime(data.reviewed_at)
                : t('enterprise.accessRequestDetail.value.notReviewed')
            }
          />
          <DetailRow
            label={t('enterprise.accessRequestDetail.label.reviewNotes')}
            value={data?.review_notes || t('enterprise.accessRequestDetail.value.noNotes')}
          />

          <SectionLabel>
            {t('enterprise.accessRequestDetail.section.timestamps')}
          </SectionLabel>
          <DetailRow
            label={t('enterprise.accessRequestDetail.label.createdAt')}
            value={data?.created_at ? formatDateTime(data.created_at) : '-'}
          />
        </div>
      </PixelPanel>

      {/* Audit Trail Section */}
      <div className="mt-8">
        <h3 className="mb-4 font-display text-pixel-base text-pixel-fg">
          {t('enterprise.accessRequestDetail.audit.title')}
        </h3>
        {auditError ? (
          <ErrorState message={t('enterprise.accessRequestDetail.error.loadAudit')} />
        ) : !auditData ? (
          <LoadingState />
        ) : auditEntries.length === 0 ? (
          <EmptyState message={t('enterprise.accessRequestDetail.empty.audit')} />
        ) : (
          <PixelPanel>
            <DataTable
              className="border-0"
              columns={[
                {
                  key: 'created_at',
                  label: t('enterprise.accessRequestDetail.audit.table.time'),
                  render: (entry: AuditEntry) => (
                    <span className="whitespace-nowrap font-mono">
                      {formatDateTime(entry.created_at)}
                    </span>
                  ),
                },
                {
                  key: 'action',
                  label: t('enterprise.accessRequestDetail.audit.table.action'),
                  render: (entry: AuditEntry) => <span className="font-mono">{entry.action}</span>,
                },
                {
                  key: 'actor',
                  label: t('enterprise.accessRequestDetail.audit.table.actor'),
                  render: (entry: AuditEntry) => (
                    <span className="font-mono">
                      {entry.actor_type}:{entry.actor_id?.slice(0, 8)}
                    </span>
                  ),
                },
                {
                  key: 'request_ip',
                  label: t('enterprise.accessRequestDetail.audit.table.ip'),
                  render: (entry: AuditEntry) => (
                    <span className="font-mono">{entry.request_ip || '-'}</span>
                  ),
                },
                {
                  key: 'details',
                  label: t('enterprise.accessRequestDetail.audit.table.details'),
                  render: (entry: AuditEntry) => (
                    <span className="block max-w-xs truncate font-mono">
                      {entry.details ? JSON.stringify(entry.details) : '-'}
                    </span>
                  ),
                },
              ]}
              data={auditEntries}
            />
            <div className="border-t-2 border-pixel-line px-4 py-2 font-mono text-base text-pixel-muted">
              {t('enterprise.accessRequestDetail.audit.count', {
                count: auditEntries.length,
                total: auditData.total,
              })}
            </div>
          </PixelPanel>
        )}
      </div>
    </div>
  );
}

function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <h3 className="border-t-2 border-pixel-line pt-4 font-pixel text-pixel-sm uppercase tracking-pixel text-pixel-muted">
      {children}
    </h3>
  );
}

function DetailRow({
  label,
  value,
  children,
}: {
  label: string;
  value?: string;
  children?: React.ReactNode;
}) {
  return (
    <div className="flex flex-col gap-1 sm:flex-row sm:items-start sm:gap-4">
      <span className="w-full font-pixel text-pixel-sm uppercase tracking-pixel text-pixel-muted sm:w-40 sm:shrink-0">
        {label}
      </span>
      <span className="break-all font-mono text-lg text-pixel-fg">{children ?? value ?? '-'}</span>
    </div>
  );
}

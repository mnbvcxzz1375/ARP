import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';
import api from '../../api/client';
import { useT } from '../../i18n';
import DataTable from '../../components/DataTable';
import Pagination from '../../components/Pagination';
import LoadingState from '../../components/LoadingState';
import ErrorState from '../../components/ErrorState';
import { PageHeader } from './PixelKit';

export default function AuditLogsPage() {
  const [page, setPage] = useState(1);
  const limit = 20;
  const t = useT();

  const { data, isLoading, isError } = useQuery({
    queryKey: ['admin/audit', page, limit],
    queryFn: () => api.get('/v1/dashboard/admin/audit-logs', { params: { offset: (page - 1) * limit, limit } }).then((r) => r.data),
  });

  if (isLoading) return <LoadingState />;
  if (isError) return <ErrorState message={t('admin.error.loadAuditLogs')} />;

  return (
    <div>
      <PageHeader title={t('admin.title.auditLogs')} />
      {/* DataTable carries its own 2px pixel border + surface; the wrapper
          only adds the hard pixel-step shadow. */}
      <div className="shadow-pixel-sm">
        <DataTable
          columns={[
            { key: 'audit_id', label: t('admin.audit.table.id'), render: (r: any) => r.audit_id?.slice(0, 8) },
            { key: 'actor_type', label: t('admin.audit.table.actorType') },
            { key: 'actor_id', label: t('admin.audit.table.actor'), render: (r: any) => r.actor_id?.slice(0, 12) },
            { key: 'action', label: t('admin.audit.table.action') },
            { key: 'resource_type', label: t('admin.audit.table.resource') },
            { key: 'created_at', label: t('admin.table.created') },
          ]}
          data={data?.audit_logs ?? []}
        />
        <Pagination
          offset={(page - 1) * limit}
          limit={limit}
          total={data?.total ?? 0}
          onPageChange={(offset) => setPage(Math.floor(offset / limit) + 1)}
        />
      </div>
    </div>
  );
}

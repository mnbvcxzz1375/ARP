import { useParams, Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import api from '../../api/client';
import LoadingState from '../../components/LoadingState';
import ErrorState from '../../components/ErrorState';
import StatusBadge from '../../components/StatusBadge';

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
      return <ErrorState message="Access request not found" />;
    }
    if (statusCode === 403) {
      return <ErrorState message="Access denied" />;
    }
    return <ErrorState message="Failed to load access request" />;
  }

  const auditEntries: AuditEntry[] = auditData?.audit_logs ?? [];

  return (
    <div>
      <div className="mb-4">
        <Link
          to="/enterprise/access-requests"
          className="text-sm text-blue-600 hover:underline"
        >
          &larr; Back to Access Requests
        </Link>
      </div>

      <h2 className="text-xl font-semibold mb-6">Access Request Detail</h2>

      <div className="bg-white rounded-lg border p-6 space-y-4">
        <DetailRow label="Request ID" value={data?.request_id} />
        <DetailRow label="Status">
          <StatusBadge status={data?.status} />
        </DetailRow>

        <h3 className="text-sm font-medium text-gray-500 pt-4 border-t">
          Applicant Information
        </h3>
        <DetailRow label="Name" value={data?.applicant_name} />
        <DetailRow label="Email" value={data?.applicant_email} />
        <DetailRow label="Organization" value={data?.organization || 'Not provided'} />

        <h3 className="text-sm font-medium text-gray-500 pt-4 border-t">
          Request Details
        </h3>
        <DetailRow label="Requested Mode">
          <span className="text-xs font-medium px-2 py-0.5 rounded bg-blue-100 text-blue-800">
            {data?.requested_mode}
          </span>
        </DetailRow>
        <DetailRow label="Use Case" value={data?.use_case} />
        <DetailRow
          label="Terms Acknowledged"
          value={data?.terms_acknowledged ? 'Yes' : 'No'}
        />

        {data?.request_ip && (
          <DetailRow label="Request IP" value={data.request_ip} />
        )}

        <h3 className="text-sm font-medium text-gray-500 pt-4 border-t">
          Review Information
        </h3>
        <DetailRow label="Reviewed By" value={data?.reviewed_by || 'Not reviewed'} />
        <DetailRow
          label="Reviewed At"
          value={
            data?.reviewed_at
              ? new Date(data.reviewed_at).toLocaleString()
              : 'Not reviewed'
          }
        />
        <DetailRow
          label="Review Notes"
          value={data?.review_notes || 'No notes'}
        />

        <h3 className="text-sm font-medium text-gray-500 pt-4 border-t">
          Timestamps
        </h3>
        <DetailRow
          label="Created At"
          value={
            data?.created_at
              ? new Date(data.created_at).toLocaleString()
              : '-'
          }
        />
      </div>

      {/* Audit Trail Section */}
      <div className="mt-8">
        <h3 className="text-lg font-semibold mb-4">Audit Trail</h3>
        {auditError ? (
          <ErrorState message="Failed to load audit trail" />
        ) : !auditData ? (
          <LoadingState />
        ) : auditEntries.length === 0 ? (
          <p className="text-sm text-gray-500">No audit entries for this request.</p>
        ) : (
          <div className="bg-white rounded-lg border overflow-hidden">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-4 py-2 text-left text-xs font-medium text-gray-500">Time</th>
                  <th className="px-4 py-2 text-left text-xs font-medium text-gray-500">Action</th>
                  <th className="px-4 py-2 text-left text-xs font-medium text-gray-500">Actor</th>
                  <th className="px-4 py-2 text-left text-xs font-medium text-gray-500">IP</th>
                  <th className="px-4 py-2 text-left text-xs font-medium text-gray-500">Details</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {auditEntries.map((entry) => (
                  <tr key={entry.audit_id}>
                    <td className="px-4 py-2 text-xs text-gray-600 whitespace-nowrap">
                      {new Date(entry.created_at).toLocaleString()}
                    </td>
                    <td className="px-4 py-2 text-xs text-gray-900 font-mono">
                      {entry.action}
                    </td>
                    <td className="px-4 py-2 text-xs text-gray-600">
                      {entry.actor_type}:{entry.actor_id?.slice(0, 8)}
                    </td>
                    <td className="px-4 py-2 text-xs text-gray-600 font-mono">
                      {entry.request_ip || '-'}
                    </td>
                    <td className="px-4 py-2 text-xs text-gray-600 max-w-xs truncate">
                      {entry.details ? JSON.stringify(entry.details) : '-'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <div className="px-4 py-2 text-xs text-gray-500 border-t">
              Showing {auditEntries.length} of {auditData.total} entries
            </div>
          </div>
        )}
      </div>
    </div>
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
    <div className="flex items-start gap-4">
      <span className="text-sm text-gray-500 w-40 shrink-0">{label}</span>
      <span className="text-sm text-gray-900">
        {children ?? value ?? '-'}
      </span>
    </div>
  );
}

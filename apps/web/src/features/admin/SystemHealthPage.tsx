import { useQuery } from '@tanstack/react-query';
import { Shield, CheckCircle, XCircle, Server, Box } from 'lucide-react';
import api from '../../api/client';
import LoadingState from '../../components/LoadingState';
import ErrorState from '../../components/ErrorState';

function HealthBadge({ status, label }: { status: string; label: string }) {
  const ok = status === 'ok';
  return (
    <div className={`flex items-center gap-2 px-4 py-3 rounded-lg border ${ok ? 'border-green-200 bg-green-50' : 'border-red-200 bg-red-50'}`}>
      {ok ? <CheckCircle className="h-5 w-5 text-green-600" /> : <XCircle className="h-5 w-5 text-red-600" />}
      <div>
        <p className="text-sm font-medium text-gray-900">{label}</p>
        <p className={`text-xs font-mono ${ok ? 'text-green-600' : 'text-red-600'}`}>{status}</p>
      </div>
    </div>
  );
}

export default function SystemHealthPage() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ['admin/system'],
    queryFn: () => api.get('/v1/admin/system/health').then((r) => r.data),
    refetchInterval: 10000,
  });

  if (isLoading) return <LoadingState />;
  if (isError) return <ErrorState message="Failed to load system health" />;

  return (
    <div>
      <h2 className="text-xl font-semibold mb-6">System Health</h2>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        <HealthBadge status={data?.api_health || 'down'} label="API" />
        <HealthBadge status={data?.db_health || 'down'} label="PostgreSQL" />
        <HealthBadge status={data?.redis_health || 'down'} label="Redis" />
        <HealthBadge status={data?.https_wss_staging || 'not_configured'} label="HTTPS/WSS" />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-white rounded-lg border p-4">
          <h3 className="text-sm font-medium text-gray-700 mb-3 flex items-center gap-2">
            <Server className="h-4 w-4" /> System Info
          </h3>
          <dl className="space-y-2 text-sm">
            <div className="flex justify-between"><dt className="text-gray-500">App Version</dt><dd className="font-mono">{data?.app_version || 'unknown'}</dd></div>
            <div className="flex justify-between"><dt className="text-gray-500">Migration</dt><dd className="font-mono">{data?.migration_revision || 'unknown'}</dd></div>
            <div className="flex justify-between"><dt className="text-gray-500">Pending Queue</dt><dd className="font-medium">{data?.pending_queue_length ?? 0}</dd></div>
          </dl>
        </div>
        <div className="bg-white rounded-lg border p-4">
          <h3 className="text-sm font-medium text-gray-700 mb-3 flex items-center gap-2">
            <Box className="h-4 w-4" /> Workers
          </h3>
          <dl className="space-y-2 text-sm">
            <div className="flex justify-between"><dt className="text-gray-500">Retry Worker</dt><dd><span className={`px-2 py-0.5 rounded text-xs font-medium ${data?.retry_worker_health === 'ok' ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'}`}>{data?.retry_worker_health || 'unknown'}</span></dd></div>
            <div className="flex justify-between"><dt className="text-gray-500">Timeout Worker</dt><dd><span className={`px-2 py-0.5 rounded text-xs font-medium ${data?.timeout_worker_health === 'ok' ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'}`}>{data?.timeout_worker_health || 'unknown'}</span></dd></div>
          </dl>
        </div>
      </div>

      <p className="mt-6 text-xs text-gray-500 flex items-center gap-1">
        <Shield className="h-3 w-3" /> No secrets are exposed on this page.
      </p>
    </div>
  );
}

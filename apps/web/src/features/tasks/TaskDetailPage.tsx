import { useParams, Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { ArrowLeft } from 'lucide-react';
import api from '../../api/client';
import StatusBadge from '../../components/StatusBadge';
import RiskBadge from '../../components/RiskBadge';
import DataTable from '../../components/DataTable';
import LoadingState from '../../components/LoadingState';
import ErrorState from '../../components/ErrorState';
import EmptyState from '../../components/EmptyState';

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <dt className="text-xs font-medium text-gray-500 uppercase">{label}</dt>
      <dd className="mt-1 text-sm text-gray-900">{children}</dd>
    </div>
  );
}

function CodeBlock({ content }: { content: string | null | undefined }) {
  if (!content) return <span className="text-sm text-gray-400">-</span>;
  return (
    <pre className="mt-1 whitespace-pre-wrap break-all rounded bg-gray-50 p-3 text-xs text-gray-800 font-mono max-h-48 overflow-auto">
      {content}
    </pre>
  );
}

export default function TaskDetailPage() {
  const { taskId } = useParams<{ taskId: string }>();

  const taskQuery = useQuery({
    queryKey: ['task-detail', taskId],
    queryFn: () => api.get(`/v1/dashboard/tasks/${taskId}`).then((r) => r.data),
    enabled: !!taskId,
  });

  const messagesQuery = useQuery({
    queryKey: ['task-messages', taskId],
    queryFn: () => api.get(`/v1/dashboard/tasks/${taskId}/messages`).then((r) => r.data),
    enabled: !!taskId,
  });

  const progressQuery = useQuery({
    queryKey: ['task-progress', taskId],
    queryFn: () => api.get(`/v1/dashboard/tasks/${taskId}/progress`).then((r) => r.data),
    enabled: !!taskId,
  });

  const deliveryEventsQuery = useQuery({
    queryKey: ['task-delivery-events', taskId],
    queryFn: () => api.get(`/v1/tasks/${taskId}/delivery-events`).then((r) => r.data),
    enabled: !!taskId,
  });

  const routeDecisionsQuery = useQuery({
    queryKey: ['task-route-decisions', taskId],
    queryFn: () => api.get(`/v1/tasks/${taskId}/route-decisions`).then((r) => r.data),
    enabled: !!taskId,
  });

  if (taskQuery.isLoading) return <LoadingState />;
  if (taskQuery.isError) return <ErrorState message="Failed to load task detail" />;

  const task = taskQuery.data;

  return (
    <div>
      <Link
        to="/app/tasks"
        className="inline-flex items-center gap-1 text-sm text-blue-600 hover:underline mb-4"
      >
        <ArrowLeft className="h-4 w-4" />
        Back to Tasks
      </Link>
      <h2 className="text-xl font-semibold mb-6">Task {task.task_id?.slice(0, 8)}</h2>

      <div className="space-y-6">
        <div className="bg-white rounded-lg border p-6">
          <h3 className="text-sm font-semibold text-gray-700 mb-4">Status</h3>
          <dl className="grid grid-cols-2 gap-4">
            <Field label="Status">
              <StatusBadge status={task.status} />
            </Field>
            <Field label="Delivery Status">{task.delivery_status}</Field>
            <Field label="Retry Count">{task.retry_count}</Field>
            <Field label="Created">{new Date(task.created_at).toLocaleString()}</Field>
            <Field label="Updated">{new Date(task.updated_at).toLocaleString()}</Field>
          </dl>
        </div>

        {(task.payload_preview || task.result_preview || task.error_message) && (
          <div className="bg-white rounded-lg border p-6">
            <h3 className="text-sm font-semibold text-gray-700 mb-4">Content</h3>
            <div className="space-y-4">
              {task.payload_preview && (
                <div>
                  <dt className="text-xs font-medium text-gray-500 uppercase">Payload</dt>
                  <CodeBlock content={task.payload_preview} />
                </div>
              )}
              {task.result_preview && (
                <div>
                  <dt className="text-xs font-medium text-gray-500 uppercase mt-3">Result</dt>
                  <CodeBlock content={task.result_preview} />
                </div>
              )}
              {task.error_message && (
                <div>
                  <dt className="text-xs font-medium text-red-600 uppercase mt-3">Error</dt>
                  <pre className="mt-1 whitespace-pre-wrap break-all rounded bg-red-50 p-3 text-xs text-red-800 font-mono max-h-48 overflow-auto">
                    {task.error_message}
                  </pre>
                </div>
              )}
            </div>
          </div>
        )}

        <div className="bg-white rounded-lg border p-6">
          <h3 className="text-sm font-semibold text-gray-700 mb-4">Messages</h3>
          {messagesQuery.isLoading ? (
            <LoadingState className="p-4" />
          ) : messagesQuery.isError ? (
            <ErrorState message="Failed to load messages" />
          ) : (
            <DataTable
              columns={[
                { key: 'message_id', label: 'ID', render: (r: any) => r.message_id?.slice(0, 8) },
                { key: 'type', label: 'Type' },
                { key: 'delivery_status', label: 'Delivery' },
                { key: 'created_at', label: 'Created', render: (r: any) => new Date(r.created_at).toLocaleString() },
              ]}
              data={messagesQuery.data?.messages ?? []}
            />
          )}
        </div>

        <div className="bg-white rounded-lg border p-6">
          <h3 className="text-sm font-semibold text-gray-700 mb-4">Progress</h3>
          {progressQuery.isLoading ? (
            <LoadingState className="p-4" />
          ) : progressQuery.isError ? (
            <ErrorState message="Failed to load progress" />
          ) : (
            <DataTable
              columns={[
                { key: 'seq', label: 'Seq' },
                { key: 'status', label: 'Status', render: (r: any) => <StatusBadge status={r.status} /> },
                { key: 'progress_pct', label: '%', render: (r: any) => r.progress_pct != null ? `${r.progress_pct}%` : '-' },
                { key: 'message', label: 'Message' },
                { key: 'created_at', label: 'Created', render: (r: any) => new Date(r.created_at).toLocaleString() },
              ]}
              data={progressQuery.data?.progress ?? []}
            />
          )}
        </div>

        <div className="bg-white rounded-lg border p-6">
          <h3 className="text-sm font-semibold text-gray-700 mb-4">Delivery Events</h3>
          {deliveryEventsQuery.isLoading ? (
            <LoadingState className="p-4" />
          ) : deliveryEventsQuery.isError ? (
            <ErrorState message="Failed to load delivery events" />
          ) : (deliveryEventsQuery.data?.delivery_events ?? []).length === 0 ? (
            <EmptyState message="No delivery events recorded" />
          ) : (
            <DataTable
              columns={[
                {
                  key: 'event_type',
                  label: 'Event',
                  render: (r: any) => <StatusBadge status={r.event_type ?? 'unknown'} />,
                },
                { key: 'route_type', label: 'Route Type', render: (r: any) => r.route_type || '-' },
                {
                  key: 'relay_node_id',
                  label: 'Relay Node',
                  render: (r: any) => r.relay_node_id?.slice(0, 8) ?? '-',
                },
                {
                  key: 'latency_ms',
                  label: 'Latency (ms)',
                  render: (r: any) => r.latency_ms != null ? `${r.latency_ms}` : '-',
                },
                {
                  key: 'queue_wait_ms',
                  label: 'Queue Wait (ms)',
                  render: (r: any) => r.queue_wait_ms != null ? `${r.queue_wait_ms}` : '-',
                },
                {
                  key: 'error_code',
                  label: 'Error Code',
                  render: (r: any) => r.error_code ? (
                    <span className="text-red-600 font-mono text-xs">{r.error_code}</span>
                  ) : '-',
                },
                {
                  key: 'created_at',
                  label: 'Created',
                  render: (r: any) => r.created_at ? new Date(r.created_at).toLocaleString() : '-',
                },
              ]}
              data={deliveryEventsQuery.data?.delivery_events ?? []}
            />
          )}
        </div>

        <div className="bg-white rounded-lg border p-6">
          <h3 className="text-sm font-semibold text-gray-700 mb-4">Route Decisions</h3>
          {routeDecisionsQuery.isLoading ? (
            <LoadingState className="p-4" />
          ) : routeDecisionsQuery.isError ? (
            <ErrorState message="Failed to load route decisions" />
          ) : (routeDecisionsQuery.data?.decisions ?? []).length === 0 ? (
            <EmptyState message="No route decisions recorded" />
          ) : (
            <DataTable
              columns={[
                { key: 'selected_route_type', label: 'Route Type' },
                {
                  key: 'risk_level',
                  label: 'Risk',
                  render: (r: any) => <RiskBadge level={r.risk_level ?? 'low'} />,
                },
                { key: 'fallback_reason', label: 'Fallback Reason', render: (r: any) => r.fallback_reason || '-' },
                {
                  key: 'decision_time_ms',
                  label: 'Decision (ms)',
                  render: (r: any) => r.decision_time_ms != null ? `${r.decision_time_ms}` : '-',
                },
                {
                  key: 'shadow_mode',
                  label: 'Shadow',
                  render: (r: any) => (
                    <span className={`px-2 py-0.5 rounded text-xs font-medium ${
                      r.shadow_mode ? 'bg-yellow-100 text-yellow-800' : 'bg-gray-100 text-gray-600'
                    }`}>
                      {r.shadow_mode ? 'Yes' : 'No'}
                    </span>
                  ),
                },
                {
                  key: 'created_at',
                  label: 'Created',
                  render: (r: any) => r.created_at ? new Date(r.created_at).toLocaleString() : '-',
                },
              ]}
              data={routeDecisionsQuery.data?.decisions ?? []}
            />
          )}
        </div>
      </div>
    </div>
  );
}

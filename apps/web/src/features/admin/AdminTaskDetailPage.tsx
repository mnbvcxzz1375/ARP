import { useParams, Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { ArrowLeft } from 'lucide-react';
import api from '../../api/client';
import StatusBadge from '../../components/StatusBadge';
import LoadingState from '../../components/LoadingState';
import ErrorState from '../../components/ErrorState';

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

export default function AdminTaskDetailPage() {
  const { taskId } = useParams<{ taskId: string }>();

  const { data, isLoading, isError } = useQuery({
    queryKey: ['admin/task-detail', taskId],
    queryFn: () => api.get(`/v1/dashboard/admin/tasks/${taskId}`).then((r) => r.data),
    enabled: !!taskId,
  });

  if (isLoading) return <LoadingState />;
  if (isError) return <ErrorState message="Failed to load task detail" />;

  const task = data;

  return (
    <div>
      <Link
        to="/admin/tasks"
        className="inline-flex items-center gap-1 text-sm text-blue-600 hover:underline mb-4"
      >
        <ArrowLeft className="h-4 w-4" />
        Back to Tasks
      </Link>
      <h2 className="text-xl font-semibold mb-6">Task {task.task_id?.slice(0, 8)}</h2>

      <div className="space-y-6">
        <div className="bg-white rounded-lg border p-6">
          <h3 className="text-sm font-semibold text-gray-700 mb-4">Details</h3>
          <dl className="grid grid-cols-2 gap-4">
            <Field label="Owner">{task.owner_username}</Field>
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
      </div>
    </div>
  );
}

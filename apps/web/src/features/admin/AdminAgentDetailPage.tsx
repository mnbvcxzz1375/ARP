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

export default function AdminAgentDetailPage() {
  const { agentId } = useParams<{ agentId: string }>();

  const { data, isLoading, isError } = useQuery({
    queryKey: ['admin/agent-detail', agentId],
    queryFn: () => api.get(`/v1/dashboard/admin/agents/${agentId}`).then((r) => r.data),
    enabled: !!agentId,
  });

  if (isLoading) return <LoadingState />;
  if (isError) return <ErrorState message="Failed to load agent detail" />;

  const agent = data;

  return (
    <div>
      <Link
        to="/admin/agents"
        className="inline-flex items-center gap-1 text-sm text-blue-600 hover:underline mb-4"
      >
        <ArrowLeft className="h-4 w-4" />
        Back to Agents
      </Link>
      <h2 className="text-xl font-semibold mb-6">{agent.name || agent.agent_number}</h2>

      <div className="space-y-6">
        <div className="bg-white rounded-lg border p-6">
          <h3 className="text-sm font-semibold text-gray-700 mb-4">Core Identity</h3>
          <dl className="grid grid-cols-2 gap-4">
            <Field label="Owner">{agent.owner_username}</Field>
            <Field label="Agent Number">{agent.agent_number}</Field>
            <Field label="Name">{agent.name}</Field>
            <Field label="Runtime">{agent.runtime}</Field>
            <Field label="Status">
              <StatusBadge status={agent.status} />
            </Field>
            <Field label="Inbound Policy">{agent.inbound_policy}</Field>
            <Field label="Discoverable">{agent.discoverable ? 'Yes' : 'No'}</Field>
            <Field label="Created">{new Date(agent.created_at).toLocaleString()}</Field>
            <Field label="Updated">{new Date(agent.updated_at).toLocaleString()}</Field>
            <Field label="Tasks (24h)">{agent.tasks_24h}</Field>
            <Field label="Failed Tasks (24h)">{agent.failed_tasks_24h}</Field>
          </dl>
        </div>

        <div className="bg-white rounded-lg border p-6">
          <h3 className="text-sm font-semibold text-gray-700 mb-4">Capabilities</h3>
          {agent.capabilities && agent.capabilities.length > 0 ? (
            <div className="flex flex-wrap gap-2">
              {agent.capabilities.map((c: string) => (
                <span
                  key={c}
                  className="inline-flex items-center rounded-full bg-blue-50 px-2.5 py-0.5 text-xs font-medium text-blue-700"
                >
                  {c}
                </span>
              ))}
            </div>
          ) : (
            <p className="text-sm text-gray-500">None</p>
          )}
        </div>

        <div className="bg-white rounded-lg border p-6">
          <h3 className="text-sm font-semibold text-gray-700 mb-4">Token Metadata</h3>
          <dl className="grid grid-cols-2 gap-4">
            <Field label="Token Prefix">
              {agent.token_metadata?.prefix ?? '-'}
            </Field>
            <Field label="Token Created">
              {agent.token_metadata?.created_at
                ? new Date(agent.token_metadata.created_at).toLocaleString()
                : '-'}
            </Field>
            <Field label="Token Rotated">
              {agent.token_metadata?.rotated_at
                ? new Date(agent.token_metadata.rotated_at).toLocaleString()
                : 'Never'}
            </Field>
          </dl>
        </div>
      </div>
    </div>
  );
}

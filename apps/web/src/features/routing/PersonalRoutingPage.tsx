import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api from '../../api/client';
import DataTable from '../../components/DataTable';
import StatusBadge from '../../components/StatusBadge';
import RiskBadge from '../../components/RiskBadge';
import LoadingState from '../../components/LoadingState';
import ErrorState from '../../components/ErrorState';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface PersonalScope {
  user_id: string;
  scope_name: string;
  default_relay_type: string;
  enable_edge_relay: boolean;
  enable_secure_channel: boolean;
  created_at: string;
  updated_at: string;
}

interface EdgeRelay {
  id: string;
  node_name: string;
  status: string;
  current_load: number;
  queue_depth: number;
  avg_latency_ms: number | null;
  success_rate: number | null;
  is_healthy: boolean;
  network_info: Record<string, unknown>;
  last_heartbeat_at: string | null;
  created_at: string;
}

interface RouteDecision {
  task_id: string;
  selected_route_type: string;
  risk_level: string;
  fallback_from_route: string | null;
  fallback_reason: string | null;
  shadow_mode: boolean;
  decision_time_ms: number | null;
  created_at: string;
}

// ---------------------------------------------------------------------------
// Routing mode config
// ---------------------------------------------------------------------------

const ROUTING_MODES = [
  { key: 'fast', label: 'Fast', description: 'Lowest latency, may skip reliability checks' },
  { key: 'normal', label: 'Normal', description: 'Balanced latency and reliability' },
  { key: 'reliable', label: 'Reliable', description: 'Maximum delivery guarantee, higher latency' },
] as const;

const RELAY_TYPE_TO_MODE: Record<string, string> = {
  edge: 'fast',
  central_relay: 'normal',
  dedicated: 'reliable',
};

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function PersonalRoutingPage() {
  const queryClient = useQueryClient();

  // --- Queries ---

  const scopeQuery = useQuery<PersonalScope>({
    queryKey: ['personal-scope'],
    queryFn: () => api.get('/v1/personal/scope').then((r) => r.data),
  });

  const edgeRelaysQuery = useQuery<EdgeRelay[]>({
    queryKey: ['personal-edge-relays'],
    queryFn: () => api.get('/v1/personal/edge-relays').then((r) => r.data),
  });

  const decisionsQuery = useQuery<{ decisions: RouteDecision[] }>({
    queryKey: ['personal-route-decisions'],
    queryFn: () =>
      api.get('/v1/routes/decisions', { params: { limit: 20 } }).then((r) => r.data),
  });

  // --- Mutations ---

  const scopeMutation = useMutation({
    mutationFn: (patch: { enable_edge_relay?: boolean; enable_secure_channel?: boolean }) =>
      api.patch('/v1/personal/scope', patch).then((r) => r.data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['personal-scope'] });
    },
  });

  // --- Error states ---

  if (scopeQuery.isError) return <ErrorState message="Failed to load routing scope" />;
  if (edgeRelaysQuery.isError) return <ErrorState message="Failed to load edge relays" />;
  if (decisionsQuery.isError) return <ErrorState message="Failed to load route decisions" />;

  // --- Derived state ---

  const scope = scopeQuery.data;
  const activeMode = scope ? (RELAY_TYPE_TO_MODE[scope.default_relay_type] ?? 'normal') : 'normal';
  const edgeRelays = edgeRelaysQuery.data ?? [];

  return (
    <div>
      <h2 className="text-xl font-semibold mb-6">My Routing</h2>

      <div className="space-y-6">
        {/* Routing Scope Configuration */}
        <div className="bg-white rounded-lg border p-6">
          <h3 className="text-sm font-semibold text-gray-700 mb-4">Routing Scope</h3>
          {scopeQuery.isLoading ? (
            <LoadingState className="p-4" />
          ) : scope ? (
            <div className="space-y-4">
              {/* Default relay type display */}
              <div className="flex items-center justify-between">
                <span className="text-sm text-gray-600">Default Relay Type</span>
                <span className="text-sm font-mono font-medium text-gray-900">
                  {scope.default_relay_type}
                </span>
              </div>

              {/* Toggles */}
              <div className="flex items-center justify-between">
                <div>
                  <span className="text-sm text-gray-600">Edge Relay</span>
                  <p className="text-xs text-gray-400">Enable personal edge relay nodes</p>
                </div>
                <button
                  type="button"
                  role="switch"
                  aria-checked={scope.enable_edge_relay}
                  onClick={() =>
                    scopeMutation.mutate({ enable_edge_relay: !scope.enable_edge_relay })
                  }
                  disabled={scopeMutation.isPending}
                  className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2 ${
                    scope.enable_edge_relay ? 'bg-indigo-600' : 'bg-gray-200'
                  }`}
                >
                  <span
                    className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                      scope.enable_edge_relay ? 'translate-x-6' : 'translate-x-1'
                    }`}
                  />
                </button>
              </div>

              <div className="flex items-center justify-between">
                <div>
                  <span className="text-sm text-gray-600">Secure Channel</span>
                  <p className="text-xs text-gray-400">Enable end-to-end encrypted channels</p>
                </div>
                <button
                  type="button"
                  role="switch"
                  aria-checked={scope.enable_secure_channel}
                  onClick={() =>
                    scopeMutation.mutate({ enable_secure_channel: !scope.enable_secure_channel })
                  }
                  disabled={scopeMutation.isPending}
                  className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2 ${
                    scope.enable_secure_channel ? 'bg-indigo-600' : 'bg-gray-200'
                  }`}
                >
                  <span
                    className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                      scope.enable_secure_channel ? 'translate-x-6' : 'translate-x-1'
                    }`}
                  />
                </button>
              </div>

              {/* Mutation error */}
              {scopeMutation.isError && (
                <p className="text-xs text-red-600">
                  {((scopeMutation.error as any)?.response?.data?.detail as string) ||
                    (scopeMutation.error as Error)?.message ||
                    'Failed to update scope'}
                </p>
              )}
            </div>
          ) : null}
        </div>

        {/* Routing Mode Selection */}
        <div className="bg-white rounded-lg border p-6">
          <h3 className="text-sm font-semibold text-gray-700 mb-4">Routing Mode</h3>
          {scopeQuery.isLoading ? (
            <LoadingState className="p-4" />
          ) : (
            <div>
              <div className="flex rounded-lg border border-gray-200 overflow-hidden">
                {ROUTING_MODES.map((mode) => (
                  <button
                    key={mode.key}
                    type="button"
                    className={`flex-1 px-4 py-2 text-sm font-medium transition-colors ${
                      activeMode === mode.key
                        ? 'bg-indigo-600 text-white'
                        : 'bg-white text-gray-700 hover:bg-gray-50'
                    }`}
                    disabled
                    title="Routing mode is derived from default relay type"
                  >
                    {mode.label}
                  </button>
                ))}
              </div>
              <p className="mt-2 text-xs text-gray-500">
                {ROUTING_MODES.find((m) => m.key === activeMode)?.description}
              </p>
            </div>
          )}
        </div>

        {/* Edge Relay Health */}
        <div className="bg-white rounded-lg border p-6">
          <h3 className="text-sm font-semibold text-gray-700 mb-4">Edge Relay Health</h3>
          {edgeRelaysQuery.isLoading ? (
            <LoadingState className="p-4" />
          ) : edgeRelays.length === 0 ? (
            <div className="text-sm text-gray-500">No personal edge relays configured</div>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
              {edgeRelays.map((relay) => (
                <div key={relay.id} className="rounded-lg border p-4">
                  <div className="flex items-center justify-between mb-3">
                    <span className="text-sm font-medium text-gray-900">{relay.node_name}</span>
                    <StatusBadge status={relay.status} />
                  </div>
                  <dl className="space-y-1 text-xs">
                    <div className="flex justify-between">
                      <dt className="text-gray-500">Load</dt>
                      <dd className="font-mono">
                        {relay.current_load != null ? `${Math.round(relay.current_load * 100)}%` : '-'}
                      </dd>
                    </div>
                    <div className="flex justify-between">
                      <dt className="text-gray-500">Latency</dt>
                      <dd className="font-mono">
                        {relay.avg_latency_ms != null ? `${relay.avg_latency_ms}ms` : '-'}
                      </dd>
                    </div>
                    <div className="flex justify-between">
                      <dt className="text-gray-500">Success Rate</dt>
                      <dd className="font-mono">
                        {relay.success_rate != null ? `${Math.round(relay.success_rate * 100)}%` : '-'}
                      </dd>
                    </div>
                    <div className="flex justify-between">
                      <dt className="text-gray-500">Healthy</dt>
                      <dd className={relay.is_healthy ? 'text-green-600' : 'text-red-600'}>
                        {relay.is_healthy ? 'Yes' : 'No'}
                      </dd>
                    </div>
                  </dl>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Recent Route Decisions */}
        <div className="bg-white rounded-lg border p-6">
          <h3 className="text-sm font-semibold text-gray-700 mb-4">Recent Route Decisions</h3>
          {decisionsQuery.isLoading ? (
            <LoadingState className="p-4" />
          ) : (
            <DataTable
              columns={[
                {
                  key: 'task_id',
                  label: 'Task ID',
                  render: (r: RouteDecision) => r.task_id?.slice(0, 8) ?? '-',
                },
                { key: 'selected_route_type', label: 'Route Type' },
                {
                  key: 'risk_level',
                  label: 'Risk',
                  render: (r: RouteDecision) => <RiskBadge level={r.risk_level ?? 'low'} />,
                },
                {
                  key: 'fallback_from_route',
                  label: 'Fallback From',
                  render: (r: RouteDecision) => r.fallback_from_route || '-',
                },
                {
                  key: 'fallback_reason',
                  label: 'Fallback Reason',
                  render: (r: RouteDecision) => r.fallback_reason || '-',
                },
                {
                  key: 'shadow_mode',
                  label: 'Shadow',
                  render: (r: RouteDecision) => (
                    <span
                      className={`px-2 py-0.5 rounded text-xs font-medium ${
                        r.shadow_mode
                          ? 'bg-yellow-100 text-yellow-800'
                          : 'bg-gray-100 text-gray-600'
                      }`}
                    >
                      {r.shadow_mode ? 'Yes' : 'No'}
                    </span>
                  ),
                },
                {
                  key: 'decision_time_ms',
                  label: 'Decision (ms)',
                  render: (r: RouteDecision) =>
                    r.decision_time_ms != null ? `${r.decision_time_ms}` : '-',
                },
                {
                  key: 'created_at',
                  label: 'Created',
                  render: (r: RouteDecision) =>
                    r.created_at ? new Date(r.created_at).toLocaleString() : '-',
                },
              ]}
              data={decisionsQuery.data?.decisions ?? []}
            />
          )}
        </div>
      </div>
    </div>
  );
}

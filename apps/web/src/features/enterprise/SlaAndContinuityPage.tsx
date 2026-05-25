import { useQuery } from '@tanstack/react-query';
import api from '../../api/client';
import DataTable from '../../components/DataTable';
import StatusBadge from '../../components/StatusBadge';
import RiskBadge from '../../components/RiskBadge';
import LoadingState from '../../components/LoadingState';
import ErrorState from '../../components/ErrorState';

export default function SlaAndContinuityPage() {
  const targetsQuery = useQuery({
    queryKey: ['sla/targets'],
    queryFn: () => api.get('/v1/sla/targets').then((r) => r.data),
  });

  const violationsQuery = useQuery({
    queryKey: ['sla/violations'],
    queryFn: () => api.get('/v1/sla/violations', { params: { limit: 20, resolved: false } }).then((r) => r.data),
  });

  const circuitBreakersQuery = useQuery({
    queryKey: ['continuity/circuit-breakers'],
    queryFn: () => api.get('/v1/continuity/circuit-breakers').then((r) => r.data),
  });

  const failoverEventsQuery = useQuery({
    queryKey: ['continuity/failover-events'],
    queryFn: () => api.get('/v1/continuity/failover-events', { params: { limit: 10 } }).then((r) => r.data),
  });

  return (
    <div>
      <h2 className="text-xl font-semibold mb-6">SLA & Continuity</h2>

      <div className="space-y-6">
        {/* SLA Targets */}
        <div className="bg-white rounded-lg border p-6">
          <h3 className="text-sm font-semibold text-gray-700 mb-4">SLA Targets</h3>
          {targetsQuery.isLoading ? (
            <LoadingState className="p-4" />
          ) : targetsQuery.isError ? (
            <ErrorState message="Failed to load SLA targets" />
          ) : (
            <DataTable
              columns={[
                { key: 'target_name', label: 'Name' },
                { key: 'metric_type', label: 'Metric Type' },
                {
                  key: 'target_value',
                  label: 'Target',
                  render: (r: any) => r.target_value != null ? `${r.target_value}` : '-',
                },
                {
                  key: 'warning_threshold',
                  label: 'Warning',
                  render: (r: any) => r.warning_threshold != null ? `${r.warning_threshold}` : '-',
                },
                {
                  key: 'critical_threshold',
                  label: 'Critical',
                  render: (r: any) => r.critical_threshold != null ? `${r.critical_threshold}` : '-',
                },
                {
                  key: 'enabled',
                  label: 'Enabled',
                  render: (r: any) => (
                    <span className={`px-2 py-0.5 rounded text-xs font-medium ${
                      r.enabled ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-600'
                    }`}>
                      {r.enabled ? 'Yes' : 'No'}
                    </span>
                  ),
                },
              ]}
              data={targetsQuery.data?.targets ?? []}
            />
          )}
        </div>

        {/* Unresolved Violations */}
        <div className="bg-white rounded-lg border p-6">
          <h3 className="text-sm font-semibold text-gray-700 mb-4">Unresolved Violations</h3>
          {violationsQuery.isLoading ? (
            <LoadingState className="p-4" />
          ) : violationsQuery.isError ? (
            <ErrorState message="Failed to load SLA violations" />
          ) : (
            <DataTable
              columns={[
                {
                  key: 'target_id',
                  label: 'Target',
                  render: (r: any) => r.target_id?.slice(0, 8) ?? '-',
                },
                {
                  key: 'severity',
                  label: 'Severity',
                  render: (r: any) => <RiskBadge level={r.severity ?? 'low'} />,
                },
                {
                  key: 'violation_time',
                  label: 'Time',
                  render: (r: any) => r.violation_time ? new Date(r.violation_time).toLocaleString() : '-',
                },
                {
                  key: 'metric_value',
                  label: 'Metric Value',
                  render: (r: any) => r.metric_value != null ? `${r.metric_value}` : '-',
                },
              ]}
              data={violationsQuery.data?.violations ?? []}
            />
          )}
        </div>

        {/* Circuit Breakers */}
        <div className="bg-white rounded-lg border p-6">
          <h3 className="text-sm font-semibold text-gray-700 mb-4">Circuit Breakers</h3>
          {circuitBreakersQuery.isLoading ? (
            <LoadingState className="p-4" />
          ) : circuitBreakersQuery.isError ? (
            <ErrorState message="Failed to load circuit breakers" />
          ) : (
            <DataTable
              columns={[
                {
                  key: 'relay_node_id',
                  label: 'Relay Node',
                  render: (r: any) => r.relay_node_id?.slice(0, 8) ?? '-',
                },
                {
                  key: 'state',
                  label: 'State',
                  render: (r: any) => {
                    const stateMap: Record<string, string> = {
                      closed: 'healthy',
                      open: 'down',
                      half_open: 'degraded',
                    };
                    return <StatusBadge status={stateMap[r.state?.toLowerCase()] ?? r.state ?? 'unknown'} />;
                  },
                },
                {
                  key: 'failure_count',
                  label: 'Failures',
                  render: (r: any) => r.failure_count ?? 0,
                },
                {
                  key: 'success_count',
                  label: 'Successes',
                  render: (r: any) => r.success_count ?? 0,
                },
              ]}
              data={circuitBreakersQuery.data?.circuit_breakers ?? []}
            />
          )}
        </div>

        {/* Recent Failover Events */}
        <div className="bg-white rounded-lg border p-6">
          <h3 className="text-sm font-semibold text-gray-700 mb-4">Recent Failover Events</h3>
          {failoverEventsQuery.isLoading ? (
            <LoadingState className="p-4" />
          ) : failoverEventsQuery.isError ? (
            <ErrorState message="Failed to load failover events" />
          ) : (
            <DataTable
              columns={[
                {
                  key: 'config_id',
                  label: 'Config',
                  render: (r: any) => r.config_id?.slice(0, 8) ?? '-',
                },
                { key: 'trigger_reason', label: 'Trigger', render: (r: any) => r.trigger_reason || '-' },
                {
                  key: 'from_relay_id',
                  label: 'From',
                  render: (r: any) => r.from_relay_id?.slice(0, 8) ?? '-',
                },
                {
                  key: 'to_relay_id',
                  label: 'To',
                  render: (r: any) => r.to_relay_id?.slice(0, 8) ?? '-',
                },
                {
                  key: 'status',
                  label: 'Status',
                  render: (r: any) => <StatusBadge status={r.status ?? 'unknown'} />,
                },
                {
                  key: 'auto_triggered',
                  label: 'Auto',
                  render: (r: any) => (
                    <span className={`px-2 py-0.5 rounded text-xs font-medium ${
                      r.auto_triggered ? 'bg-yellow-100 text-yellow-800' : 'bg-gray-100 text-gray-600'
                    }`}>
                      {r.auto_triggered ? 'Yes' : 'No'}
                    </span>
                  ),
                },
              ]}
              data={failoverEventsQuery.data?.failover_events ?? []}
            />
          )}
        </div>
      </div>
    </div>
  );
}

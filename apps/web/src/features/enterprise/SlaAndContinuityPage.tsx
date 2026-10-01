import { useQuery } from '@tanstack/react-query';
import api from '../../api/client';
import { useT, useFormat } from '../../i18n';
import DataTable from '../../components/DataTable';
import StatusBadge from '../../components/StatusBadge';
import RiskBadge from '../../components/RiskBadge';
import LoadingState from '../../components/LoadingState';
import ErrorState from '../../components/ErrorState';
import { PageTitle, PixelPanel, YesNoChip } from '../connections/pixel-ui';

export default function SlaAndContinuityPage() {
  const t = useT();
  const { formatDateTime } = useFormat();
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
      <PageTitle>{t('enterprise.sla.title')}</PageTitle>

      <div className="flex flex-col gap-6">
        {/* SLA Targets */}
        <PixelPanel title={t('enterprise.sla.panel.targets')}>
          {targetsQuery.isLoading ? (
            <LoadingState className="p-4" />
          ) : targetsQuery.isError ? (
            <ErrorState message={t('enterprise.sla.error.loadTargets')} />
          ) : (
            <DataTable
              className="border-0"
              columns={[
                { key: 'target_name', label: t('enterprise.table.name') },
                { key: 'metric_type', label: t('enterprise.sla.targets.table.metricType') },
                {
                  key: 'target_value',
                  label: t('enterprise.sla.targets.table.target'),
                  render: (r: any) => (r.target_value != null ? `${r.target_value}` : '-'),
                },
                {
                  key: 'warning_threshold',
                  label: t('enterprise.sla.targets.table.warning'),
                  render: (r: any) => (r.warning_threshold != null ? `${r.warning_threshold}` : '-'),
                },
                {
                  key: 'critical_threshold',
                  label: t('enterprise.sla.targets.table.critical'),
                  render: (r: any) => (r.critical_threshold != null ? `${r.critical_threshold}` : '-'),
                },
                {
                  key: 'enabled',
                  label: t('enterprise.table.enabled'),
                  render: (r: any) => <YesNoChip value={!!r.enabled} />,
                },
              ]}
              data={targetsQuery.data?.targets ?? []}
            />
          )}
        </PixelPanel>

        {/* Unresolved Violations */}
        <PixelPanel title={t('enterprise.sla.panel.violations')}>
          {violationsQuery.isLoading ? (
            <LoadingState className="p-4" />
          ) : violationsQuery.isError ? (
            <ErrorState message={t('enterprise.sla.error.loadViolations')} />
          ) : (
            <DataTable
              className="border-0"
              columns={[
                {
                  key: 'target_id',
                  label: t('enterprise.sla.violations.table.target'),
                  render: (r: any) => r.target_id?.slice(0, 8) ?? '-',
                },
                {
                  key: 'severity',
                  label: t('enterprise.sla.violations.table.severity'),
                  render: (r: any) => <RiskBadge level={r.severity ?? 'low'} />,
                },
                {
                  key: 'violation_time',
                  label: t('enterprise.sla.violations.table.time'),
                  render: (r: any) =>
                    r.violation_time ? formatDateTime(r.violation_time) : '-',
                },
                {
                  key: 'metric_value',
                  label: t('enterprise.sla.violations.table.metricValue'),
                  render: (r: any) => (r.metric_value != null ? `${r.metric_value}` : '-'),
                },
              ]}
              data={violationsQuery.data?.violations ?? []}
            />
          )}
        </PixelPanel>

        {/* Circuit Breakers */}
        <PixelPanel title={t('enterprise.sla.panel.breakers')}>
          {circuitBreakersQuery.isLoading ? (
            <LoadingState className="p-4" />
          ) : circuitBreakersQuery.isError ? (
            <ErrorState message={t('enterprise.sla.error.loadBreakers')} />
          ) : (
            <DataTable
              className="border-0"
              columns={[
                {
                  key: 'relay_node_id',
                  label: t('enterprise.sla.breakers.table.relayNode'),
                  render: (r: any) => r.relay_node_id?.slice(0, 8) ?? '-',
                },
                {
                  key: 'state',
                  label: t('enterprise.sla.breakers.table.state'),
                  render: (r: any) => {
                    const stateMap: Record<string, string> = {
                      closed: 'healthy',
                      open: 'down',
                      half_open: 'degraded',
                    };
                    return (
                      <StatusBadge
                        status={stateMap[r.state?.toLowerCase()] ?? r.state ?? 'unknown'}
                      />
                    );
                  },
                },
                {
                  key: 'failure_count',
                  label: t('enterprise.sla.breakers.table.failures'),
                  render: (r: any) => r.failure_count ?? 0,
                },
                {
                  key: 'success_count',
                  label: t('enterprise.sla.breakers.table.successes'),
                  render: (r: any) => r.success_count ?? 0,
                },
              ]}
              data={circuitBreakersQuery.data?.circuit_breakers ?? []}
            />
          )}
        </PixelPanel>

        {/* Recent Failover Events */}
        <PixelPanel title={t('enterprise.sla.panel.failovers')}>
          {failoverEventsQuery.isLoading ? (
            <LoadingState className="p-4" />
          ) : failoverEventsQuery.isError ? (
            <ErrorState message={t('enterprise.sla.error.loadFailovers')} />
          ) : (
            <DataTable
              className="border-0"
              columns={[
                {
                  key: 'config_id',
                  label: t('enterprise.sla.failovers.table.config'),
                  render: (r: any) => r.config_id?.slice(0, 8) ?? '-',
                },
                {
                  key: 'trigger_reason',
                  label: t('enterprise.sla.failovers.table.trigger'),
                  render: (r: any) => r.trigger_reason || '-',
                },
                {
                  key: 'from_relay_id',
                  label: t('enterprise.sla.failovers.table.from'),
                  render: (r: any) => r.from_relay_id?.slice(0, 8) ?? '-',
                },
                {
                  key: 'to_relay_id',
                  label: t('enterprise.sla.failovers.table.to'),
                  render: (r: any) => r.to_relay_id?.slice(0, 8) ?? '-',
                },
                {
                  key: 'status',
                  label: t('enterprise.table.status'),
                  render: (r: any) => <StatusBadge status={r.status ?? 'unknown'} />,
                },
                {
                  key: 'auto_triggered',
                  label: t('enterprise.sla.failovers.table.auto'),
                  render: (r: any) => <YesNoChip value={!!r.auto_triggered} />,
                },
              ]}
              data={failoverEventsQuery.data?.failover_events ?? []}
            />
          )}
        </PixelPanel>
      </div>
    </div>
  );
}

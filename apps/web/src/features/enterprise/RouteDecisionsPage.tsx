import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import api from '../../api/client';
import { useT, useFormat } from '../../i18n';
import DataTable from '../../components/DataTable';
import Pagination from '../../components/Pagination';
import RiskBadge from '../../components/RiskBadge';
import LoadingState from '../../components/LoadingState';
import ErrorState from '../../components/ErrorState';
import { NeutralChip, PageTitle, PixelPanel, PixButton, YesNoChip, PIXEL_INPUT } from '../connections/pixel-ui';
import { cn } from '../../lib/utils';

/**
 * Translation keys for the selected_route_type column. Values not in the
 * backend's path-optimizer vocabulary fall back to the raw string.
 */
const ROUTE_TYPE_LABEL_KEYS: Record<string, string> = {
  central_relay: 'enterprise.decisions.routeType.central_relay',
  regional_relay: 'enterprise.decisions.routeType.regional_relay',
  personal_edge: 'enterprise.decisions.routeType.personal_edge',
  dedicated_channel: 'enterprise.decisions.routeType.dedicated_channel',
};

export default function RouteDecisionsPage() {
  const t = useT();
  const { formatDateTime } = useFormat();
  const [page, setPage] = useState(1);
  const [taskIdFilter, setTaskIdFilter] = useState('');
  const [appliedFilter, setAppliedFilter] = useState<string | undefined>(undefined);
  const limit = 20;

  const { data, isLoading, isError } = useQuery({
    queryKey: ['route-decisions', page, limit, appliedFilter],
    queryFn: () =>
      api
        .get('/v1/routes/decisions', {
          params: {
            offset: (page - 1) * limit,
            limit,
            task_id: appliedFilter || undefined,
          },
        })
        .then((r) => r.data),
  });

  const handleSearch = () => {
    setAppliedFilter(taskIdFilter || undefined);
    setPage(1);
  };

  if (isLoading) return <LoadingState />;
  if (isError) return <ErrorState message={t('enterprise.decisions.error.load')} />;

  return (
    <div>
      <PageTitle>{t('enterprise.decisions.title')}</PageTitle>

      <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center">
        <input
          type="text"
          value={taskIdFilter}
          onChange={(e) => setTaskIdFilter(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
          placeholder={t('enterprise.decisions.filter.taskIdPlaceholder')}
          className={cn(PIXEL_INPUT, 'w-full sm:w-72')}
        />
        <PixButton onClick={handleSearch}>{t('enterprise.action.search')}</PixButton>
        {appliedFilter && (
          <PixButton
            variant="ghost"
            onClick={() => {
              setTaskIdFilter('');
              setAppliedFilter(undefined);
              setPage(1);
            }}
          >
            {t('enterprise.action.clear')}
          </PixButton>
        )}
      </div>

      <PixelPanel>
        <DataTable
          className="border-0"
          columns={[
            { key: 'task_id', label: t('enterprise.decisions.table.taskId'), render: (r: any) => r.task_id?.slice(0, 8) ?? '-' },
            {
              key: 'selected_route_type',
              label: t('enterprise.decisions.table.routeType'),
              render: (r: any) => (
                <NeutralChip>
                  {r.selected_route_type && ROUTE_TYPE_LABEL_KEYS[r.selected_route_type]
                    ? t(ROUTE_TYPE_LABEL_KEYS[r.selected_route_type])
                    : r.selected_route_type || '-'}
                </NeutralChip>
              ),
            },
            { key: 'risk_level', label: t('enterprise.decisions.table.risk'), render: (r: any) => <RiskBadge level={r.risk_level ?? 'low'} /> },
            { key: 'fallback_from_route', label: t('enterprise.decisions.table.fallbackFrom'), render: (r: any) => r.fallback_from_route || '-' },
            { key: 'fallback_reason', label: t('enterprise.decisions.table.fallbackReason'), render: (r: any) => r.fallback_reason || '-' },
            {
              key: 'shadow_mode',
              label: t('enterprise.decisions.table.shadow'),
              render: (r: any) => <YesNoChip value={!!r.shadow_mode} />,
            },
            {
              key: 'decision_time_ms',
              label: t('enterprise.decisions.table.decisionTime'),
              render: (r: any) => (r.decision_time_ms != null ? `${r.decision_time_ms}` : '-'),
            },
            {
              key: 'created_at',
              label: t('enterprise.table.created'),
              render: (r: any) => (r.created_at ? formatDateTime(r.created_at) : '-'),
            },
          ]}
          data={data?.decisions ?? []}
        />
        <Pagination
          offset={(page - 1) * limit}
          limit={limit}
          total={data?.total ?? 0}
          onPageChange={(offset) => setPage(Math.floor(offset / limit) + 1)}
        />
      </PixelPanel>
    </div>
  );
}

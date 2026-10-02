import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api from '../../api/client';
import DataTable from '../../components/DataTable';
import StatusBadge from '../../components/StatusBadge';
import RiskBadge from '../../components/RiskBadge';
import LoadingState from '../../components/LoadingState';
import ErrorState from '../../components/ErrorState';
import { cn } from '../../lib/utils';
import { PIXEL_CHIP } from '../../lib/tokens';
import { useFormat, useT } from '../../i18n';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface PersonalScope {
  user_id: string;
  scope_name: string;
  default_relay_type: string;
  enable_edge_relay: boolean;
  enable_secure_channel: boolean;
  routing_strategy: 'fast' | 'normal' | 'reliable';
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

/**
 * Routing strategies the user can switch between at will. The active one is
 * stored on the PersonalScope (`routing_strategy`) and PATCHed by clicking
 * the mode strip below; the default_relay_type chip stays read-only.
 *
 * NOTE: any "local-first" / "edge preference" flavor in the copy below is
 * demonstrative presentation only. The backend scoring field
 * (`locality_score`) is a constant 0.5 this round, so local-first routing is
 * not actually activated by switching modes — see the project unknowns doc.
 * The fast/normal/reliable switch changes scoring weights only (fast zero
 * the 7 non-latency weights incl. security_score; the hard filter chain and
 * fail-closed negotiation are untouched).
 */
const ROUTING_MODES = [
  {
    key: 'fast',
    labelKey: 'routing.mode.fast',
    descriptionKey: 'routing.mode.fastDescription',
  },
  {
    key: 'normal',
    labelKey: 'routing.mode.normal',
    descriptionKey: 'routing.mode.normalDescription',
  },
  {
    key: 'reliable',
    labelKey: 'routing.mode.reliable',
    descriptionKey: 'routing.mode.reliableDescription',
  },
] as const;

// ---------------------------------------------------------------------------
// Pixel switch
// ---------------------------------------------------------------------------

/**
 * Hard-edged pixel toggle (2px step border, square knob, instant switch).
 * The ON track is the accent solid block with a #191a26 knob (5.36:1 in
 * both themes); the OFF track is the raised surface with a pixel-fg knob.
 * Role/aria contract is unchanged so the existing page tests keep passing.
 */
function PixelSwitch({
  checked,
  disabled,
  label,
  onToggle,
}: {
  checked: boolean;
  disabled: boolean;
  label: string;
  onToggle: () => void;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={label}
      onClick={onToggle}
      disabled={disabled}
      className={cn(
        'inline-flex h-[28px] w-[52px] cursor-pointer items-center border-2 border-pixel-line px-[2px] py-[2px] disabled:cursor-not-allowed',
        checked ? 'justify-end bg-pixel-accent' : 'justify-start bg-pixel-raised',
      )}
    >
      <span
        aria-hidden="true"
        className={cn(
          'h-[20px] w-[20px] border-2',
          checked ? 'border-[#191a26] bg-[#191a26]' : 'border-pixel-fg bg-pixel-fg',
        )}
      />
    </button>
  );
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function PersonalRoutingPage() {
  const t = useT();
  const { formatDateTime } = useFormat();
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
    mutationFn: (
      patch: {
        enable_edge_relay?: boolean;
        enable_secure_channel?: boolean;
        routing_strategy?: 'fast' | 'normal' | 'reliable';
      },
    ) => api.patch('/v1/personal/scope', patch).then((r) => r.data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['personal-scope'] });
    },
  });

  // --- Error states ---

  if (scopeQuery.isError) return <ErrorState message={t('routing.error.loadScope')} />;
  if (edgeRelaysQuery.isError) return <ErrorState message={t('routing.error.loadEdgeRelays')} />;
  if (decisionsQuery.isError) return <ErrorState message={t('routing.error.loadRouteDecisions')} />;

  // --- Derived state ---

  const scope = scopeQuery.data;
  const activeMode = scope ? scope.routing_strategy ?? 'normal' : 'normal';
  const edgeRelays = edgeRelaysQuery.data ?? [];

  return (
    <div>
      <h2 className="mb-6 font-display text-pixel-xl text-pixel-fg">{t('routing.page.title')}</h2>

      <div className="space-y-6">
        {/* Routing Scope Configuration */}
        <section className="bg-pixel-surface shadow-pixel-sm">
          <h3 className="px-4 pt-4 pb-3 font-display text-pixel-base uppercase tracking-pixel text-pixel-muted">
            {t('routing.section.scope')}
          </h3>
          {scopeQuery.isLoading ? (
            <LoadingState className="p-4" />
          ) : scope ? (
            <div className="space-y-4 px-4 pb-4">
              {/* Default relay type display: neutral chip, fixed contrast in both themes.
                  Read-only: the mode strip drives routing_strategy now; the edge/dedicated
                  default_relay_type branches are not reachable with real data. */}
              <div className="flex flex-wrap items-center justify-between gap-4">
                <span className="text-lg text-pixel-fg">{t('routing.field.defaultRelayType')}</span>
                <span
                  className={cn(
                    'inline-flex items-center px-2 py-0.5 font-mono text-sm leading-none',
                    PIXEL_CHIP.neutral,
                  )}
                >
                  {scope.default_relay_type}
                </span>
              </div>

              {/* Toggles */}
              <div className="flex flex-wrap items-center justify-between gap-4">
                <div className="min-w-0">
                  <span className="block text-lg text-pixel-fg">{t('routing.field.edgeRelay')}</span>
                  <p className="text-base text-pixel-muted">{t('routing.field.edgeRelayHint')}</p>
                </div>
                <PixelSwitch
                  checked={scope.enable_edge_relay}
                  disabled={scopeMutation.isPending}
                  label={t('routing.field.edgeRelay')}
                  onToggle={() =>
                    scopeMutation.mutate({ enable_edge_relay: !scope.enable_edge_relay })
                  }
                />
              </div>

              <div className="flex flex-wrap items-center justify-between gap-4">
                <div className="min-w-0">
                  <span className="block text-lg text-pixel-fg">{t('routing.field.secureChannel')}</span>
                  <p className="text-base text-pixel-muted">{t('routing.field.secureChannelHint')}</p>
                </div>
                <PixelSwitch
                  checked={scope.enable_secure_channel}
                  disabled={scopeMutation.isPending}
                  label={t('routing.field.secureChannel')}
                  onToggle={() =>
                    scopeMutation.mutate({ enable_secure_channel: !scope.enable_secure_channel })
                  }
                />
              </div>

              {/* Mutation error: LED red solid chip, 5.89:1 in both themes. */}
              {scopeMutation.isError && (
                <p
                  role="alert"
                  className="border-2 border-[#191a26] bg-pixel-led-red p-2 font-mono text-base text-[#f4f4fa]"
                >
                  {((scopeMutation.error as any)?.response?.data?.detail as string) ||
                    (scopeMutation.error as Error)?.message ||
                    t('routing.error.updateScope')}
                </p>
              )}
            </div>
          ) : null}
        </section>

        {/* Routing Mode Selection */}
        <section className="bg-pixel-surface shadow-pixel-sm">
          <h3 className="px-4 pt-4 pb-3 font-display text-pixel-base uppercase tracking-pixel text-pixel-muted">
            {t('routing.section.mode')}
          </h3>
          {scopeQuery.isLoading ? (
            <LoadingState className="p-4" />
          ) : (
            <div className="px-4 pb-4">
              <div className="flex border-2 border-pixel-line">
                {ROUTING_MODES.map((mode) => (
                  <button
                    key={mode.key}
                    type="button"
                    className={cn(
                      'flex-1 cursor-pointer border-r-2 border-pixel-line px-4 py-2 font-pixel text-pixel-sm last:border-r-0',
                      activeMode === mode.key
                        ? 'bg-pixel-accent text-[#191a26]'
                        : 'bg-pixel-surface text-pixel-fg',
                    )}
                    disabled={scopeMutation.isPending}
                    title={t('routing.mode.switchHint')}
                    onClick={() => scopeMutation.mutate({ routing_strategy: mode.key })}
                  >
                    {t(mode.labelKey)}
                  </button>
                ))}
              </div>
              <p className="mt-2 text-base text-pixel-muted">
                {t(ROUTING_MODES.find((m) => m.key === activeMode)?.descriptionKey ?? 'routing.mode.normalDescription')}
              </p>
            </div>
          )}
        </section>

        {/* Edge Relay Health */}
        <section className="bg-pixel-surface shadow-pixel-sm">
          <h3 className="px-4 pt-4 pb-3 font-display text-pixel-base uppercase tracking-pixel text-pixel-muted">
            {t('routing.section.edgeHealth')}
          </h3>
          {edgeRelaysQuery.isLoading ? (
            <LoadingState className="p-4" />
          ) : edgeRelays.length === 0 ? (
            <p className="px-4 pb-4 text-lg text-pixel-muted">
              {t('routing.empty.noEdgeRelays')}
            </p>
          ) : (
            /* Single column below 768px, two/three columns on tablet+ (4px grid). */
            <div className="grid grid-cols-1 gap-4 p-4 md:grid-cols-2 lg:grid-cols-3">
              {edgeRelays.map((relay) => (
                <div key={relay.id} className="border-2 border-pixel-line bg-pixel-raised p-4">
                  <div className="mb-3 flex items-center justify-between gap-2">
                    <span className="font-mono text-base text-pixel-fg">{relay.node_name}</span>
                    <StatusBadge status={relay.status} />
                  </div>
                  <dl className="space-y-1">
                    <div className="flex justify-between">
                      <dt className="text-base text-pixel-muted">{t('routing.relay.load')}</dt>
                      <dd className="font-mono text-base text-pixel-fg">
                        {relay.current_load != null ? `${Math.round(relay.current_load * 100)}%` : '-'}
                      </dd>
                    </div>
                    <div className="flex justify-between">
                      <dt className="text-base text-pixel-muted">{t('routing.relay.latency')}</dt>
                      <dd className="font-mono text-base text-pixel-fg">
                        {relay.avg_latency_ms != null ? `${relay.avg_latency_ms}ms` : '-'}
                      </dd>
                    </div>
                    <div className="flex justify-between">
                      <dt className="text-base text-pixel-muted">{t('routing.relay.successRate')}</dt>
                      <dd className="font-mono text-base text-pixel-fg">
                        {relay.success_rate != null ? `${Math.round(relay.success_rate * 100)}%` : '-'}
                      </dd>
                    </div>
                    <div className="flex justify-between">
                      <dt className="text-base text-pixel-muted">{t('routing.relay.healthy')}</dt>
                      <dd
                        className={cn(
                          'inline-flex items-center px-2 py-0.5 font-pixel text-sm leading-none',
                          relay.is_healthy ? PIXEL_CHIP.ok : PIXEL_CHIP.bad,
                        )}
                      >
                        {relay.is_healthy ? t('routing.fieldValue.yes') : t('routing.fieldValue.no')}
                      </dd>
                    </div>
                  </dl>
                </div>
              ))}
            </div>
          )}
        </section>

        {/* Recent Route Decisions */}
        <section className="bg-pixel-surface shadow-pixel-sm">
          <h3 className="px-4 pt-4 pb-3 font-display text-pixel-base uppercase tracking-pixel text-pixel-muted">
            {t('routing.section.recentDecisions')}
          </h3>
          {decisionsQuery.isLoading ? (
            <LoadingState className="p-4" />
          ) : (
            <DataTable
              columns={[
                {
                  key: 'task_id',
                  label: t('routing.table.taskId'),
                  render: (r: RouteDecision) => r.task_id?.slice(0, 8) ?? '-',
                },
                { key: 'selected_route_type', label: t('routing.table.routeType') },
                {
                  key: 'risk_level',
                  label: t('routing.table.risk'),
                  render: (r: RouteDecision) => <RiskBadge level={r.risk_level ?? 'low'} />,
                },
                {
                  key: 'fallback_from_route',
                  label: t('routing.table.fallbackFrom'),
                  render: (r: RouteDecision) => r.fallback_from_route || '-',
                },
                {
                  key: 'fallback_reason',
                  label: t('routing.table.fallbackReason'),
                  render: (r: RouteDecision) => r.fallback_reason || '-',
                },
                {
                  key: 'shadow_mode',
                  label: t('routing.table.shadow'),
                  render: (r: RouteDecision) => (
                    <span
                      className={cn(
                        'inline-flex items-center px-2 py-0.5 font-pixel text-sm leading-none',
                        r.shadow_mode ? PIXEL_CHIP.warn : PIXEL_CHIP.neutral,
                      )}
                    >
                      {r.shadow_mode ? t('routing.fieldValue.yes') : t('routing.fieldValue.no')}
                    </span>
                  ),
                },
                {
                  key: 'decision_time_ms',
                  label: t('routing.table.decisionTime'),
                  render: (r: RouteDecision) =>
                    r.decision_time_ms != null ? `${r.decision_time_ms}` : '-',
                },
                {
                  key: 'created_at',
                  label: t('routing.table.created'),
                  render: (r: RouteDecision) =>
                    r.created_at ? formatDateTime(r.created_at) : '-',
                },
              ]}
              data={decisionsQuery.data?.decisions ?? []}
            />
          )}
        </section>
      </div>
    </div>
  );
}

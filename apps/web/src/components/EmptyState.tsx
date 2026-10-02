import { Inbox } from 'lucide-react';
import { Link } from 'react-router-dom';
import { useT } from '../i18n';
import StationMaster from './pixel/StationMaster';
import { PIX_LINK_PRIMARY } from '../features/connections/pixel-ui';

/**
 * Empty-state panel.
 *
 * - `default` scene (backwards compatible): the original muted Inbox panel,
 *   driven by the `message` prop. All six legacy call sites
 *   (TaskDetailPage x2, AccessRequestsPage, AccessRequestDetailPage,
 *   OrgMembersPage x2) keep working with zero changes.
 * - `agents` / `tasks` scenes: story-driven pixel illustrations (an
 *   unstaffed duty desk / a still conveyor) with i18n title + subtitle and
 *   an optional primary link action. Scene art is drawn purely from the
 *   theme-following pixel palette (fg / muted / line / bg), so it stays
 *   visible in both themes; the scene copy lives in the agents / tasks
 *   namespaces of the pages that render these scenes.
 *
 * The scene container texture is a self-contained Tailwind arbitrary value
 * (alpha 0.12 <= 0.15) instead of an index.css utility: the scene must not
 * depend on another item's CSS landing order, and if the class is ever
 * missing the panel silently degrades to the plain surface color.
 */
export type EmptyStateScene = 'agents' | 'tasks' | 'default';

export interface EmptyStateAction {
  to: string;
  label: string;
}

const SCENE_TEXTURE =
  'bg-[repeating-linear-gradient(0deg,rgba(0,0,0,0.12)_0_1px,rgba(0,0,0,0)_1px_2px)]';

/**
 * agents-empty picture: an unstaffed duty desk.
 * Wall badge (fg slab), unlit duty lamp sign (line slab, dark cavity =
 * not lit; the border carries the shape, no LED color), desk and empty cup
 * (muted slabs with hard bg edges). The StationMaster sprite stands beside
 * the desk (read-only consumption, rendered by the caller of the scene).
 * Contrast: fg/surface 11.39:1 dark / 14.04:1 light, muted/surface
 * 6.84:1 / 6.46:1 - all pass AA.
 */
function DutyDeskScene({ ariaLabel }: { ariaLabel: string }) {
  return (
    <svg
      viewBox="0 0 72 48"
      shapeRendering="crispEdges"
      role="img"
      aria-label={ariaLabel}
      className="h-auto w-[144px] max-w-full"
    >
      {/* Wall hook */}
      <rect x="14" y="2" width="2" height="4" style={{ fill: 'var(--pixel-muted)' }} />
      {/* Empty badge on the wall */}
      <rect
        x="8"
        y="6"
        width="14"
        height="10"
        style={{ fill: 'var(--pixel-fg)', stroke: 'var(--pixel-bg)', strokeWidth: 2 }}
      />
      {/* Unlit duty lamp sign */}
      <rect
        x="30"
        y="4"
        width="20"
        height="10"
        style={{ fill: 'var(--pixel-line)', stroke: 'var(--pixel-bg)', strokeWidth: 2 }}
      />
      <rect x="38" y="7" width="4" height="4" style={{ fill: 'var(--pixel-bg)' }} />
      <rect x="39" y="14" width="2" height="3" style={{ fill: 'var(--pixel-muted)' }} />
      {/* Desk top + legs */}
      <rect
        x="4"
        y="28"
        width="64"
        height="6"
        style={{ fill: 'var(--pixel-muted)', stroke: 'var(--pixel-bg)', strokeWidth: 2 }}
      />
      <rect
        x="8"
        y="34"
        width="4"
        height="10"
        style={{ fill: 'var(--pixel-muted)', stroke: 'var(--pixel-bg)', strokeWidth: 2 }}
      />
      <rect
        x="60"
        y="34"
        width="4"
        height="10"
        style={{ fill: 'var(--pixel-muted)', stroke: 'var(--pixel-bg)', strokeWidth: 2 }}
      />
      {/* Empty cup with handle */}
      <rect
        x="50"
        y="22"
        width="7"
        height="6"
        style={{ fill: 'var(--pixel-muted)', stroke: 'var(--pixel-bg)', strokeWidth: 2 }}
      />
      <rect
        x="57"
        y="23"
        width="3"
        height="3"
        style={{ fill: 'none', stroke: 'var(--pixel-bg)', strokeWidth: 2 }}
      />
    </svg>
  );
}

/**
 * tasks-empty picture: a still conveyor.
 * Twin 2px rails (line), alternating muted sleepers, an empty parcel on the
 * belt (fg slab + bg edge + line sealing tape) and a tower base with an
 * unlit signal lamp (line fill + bg edge). The StationMaster sprite sits at
 * the conveyor end (read-only consumption, rendered by the caller).
 */
function ConveyorScene({ ariaLabel }: { ariaLabel: string }) {
  return (
    <svg
      viewBox="0 0 72 48"
      shapeRendering="crispEdges"
      role="img"
      aria-label={ariaLabel}
      className="h-auto w-[144px] max-w-full"
    >
      {/* Tower base at the conveyor end */}
      <rect
        x="4"
        y="18"
        width="10"
        height="14"
        style={{ fill: 'var(--pixel-muted)', stroke: 'var(--pixel-bg)', strokeWidth: 2 }}
      />
      {/* Unlit signal lamp */}
      <rect
        x="7"
        y="12"
        width="4"
        height="4"
        style={{ fill: 'var(--pixel-line)', stroke: 'var(--pixel-bg)', strokeWidth: 2 }}
      />
      {/* Twin rails */}
      <rect x="4" y="30" width="64" height="2" style={{ fill: 'var(--pixel-line)' }} />
      <rect x="4" y="36" width="64" height="2" style={{ fill: 'var(--pixel-line)' }} />
      {/* Sleepers: muted short segments */}
      {[8, 20, 32, 44, 56].map((x) => (
        <rect key={x} x={x} y="32" width="6" height="4" style={{ fill: 'var(--pixel-muted)' }} />
      ))}
      {/* Empty parcel with sealing tape */}
      <rect
        x="28"
        y="20"
        width="14"
        height="10"
        style={{ fill: 'var(--pixel-fg)', stroke: 'var(--pixel-bg)', strokeWidth: 2 }}
      />
      <rect x="34" y="20" width="2" height="10" style={{ fill: 'var(--pixel-line)' }} />
    </svg>
  );
}

export default function EmptyState({
  message,
  scene = 'default',
  action,
}: {
  /** Required for the `default` scene; ignored by the story scenes. */
  message?: string;
  scene?: EmptyStateScene;
  action?: EmptyStateAction;
}) {
  const t = useT();

  if (scene === 'agents' || scene === 'tasks') {
    const titleKey = scene === 'agents' ? 'agents.empty.title' : 'tasks.empty.title';
    const subtitleKey = scene === 'agents' ? 'agents.empty.subtitle' : 'tasks.empty.subtitle';
    const title = t(titleKey);
    return (
      <div
        className={
          'flex flex-col items-center justify-center gap-4 p-8 text-center sm:p-12 ' +
          'bg-pixel-surface border-2 border-pixel-line ' +
          SCENE_TEXTURE
        }
      >
        <div className="flex min-w-0 flex-wrap items-end justify-center gap-4">
          {scene === 'agents' ? (
            <DutyDeskScene ariaLabel={title} />
          ) : (
            <ConveyorScene ariaLabel={title} />
          )}
          {/*
            Read-only consumption of the StationMaster sprite (owned by the
            mascot item). pose="idle" is a static terminal frame: no hover,
            no timers, so nothing here is gated by prefers-reduced-motion.
          */}
          <StationMaster size={64} pose="idle" />
        </div>
        {/* No font-pixel on these lines: the copy is Chinese-first and must
            fall back to the system CJK stack honestly (see accessibility
            rule 6), PS2P has no Chinese glyphs. */}
        <p className="text-pixel-base font-semibold text-pixel-fg">{title}</p>
        <p className="max-w-md text-base text-pixel-muted">{t(subtitleKey)}</p>
        {action ? (
          <Link to={action.to} className={PIX_LINK_PRIMARY}>
            {action.label}
          </Link>
        ) : null}
      </div>
    );
  }

  // Self-contained panel so muted text keeps contrast on any page surface.
  return (
    <div className="flex flex-col items-center justify-center gap-3 p-12 bg-pixel-surface border-2 border-pixel-line">
      <Inbox className="w-10 h-10 text-pixel-muted" strokeWidth={2} aria-hidden="true" />
      <p className="text-base text-pixel-muted">{message}</p>
    </div>
  );
}

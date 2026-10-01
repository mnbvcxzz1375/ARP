import { NavLink } from 'react-router-dom';
import { X } from 'lucide-react';
import { useT } from '../../i18n';
import DocsBackLink from './DocsBackLink';
import {
  DOC_GROUP_ORDER,
  DOCS_ENTRIES,
  type DocEntry,
  type DocsGroupId,
} from './docsRegistry';

/**
 * Grouped docs sidebar. On <768px it renders as a fixed overlay panel
 * toggled by the "目录" button in DocsLayout; on md+ it is a static
 * column next to the content.
 */
export default function DocsSidebar({
  open,
  onClose,
}: {
  open: boolean;
  onClose: () => void;
}) {
  const t = useT();

  const entriesByGroup = new Map<DocsGroupId, DocEntry[]>();
  for (const group of DOC_GROUP_ORDER) entriesByGroup.set(group, []);
  for (const entry of DOCS_ENTRIES) {
    entriesByGroup.get(entry.group)?.push(entry);
  }

  return (
    <aside
      className={[
        // Mobile: fixed overlay panel, hidden unless toggled.
        // Desktop: sticky full-height column with its own scroll, so the
        // back link at the bottom stays pinned and reachable no matter
        // how long the main content is.
        'bg-pixel-surface border-r-2 border-pixel-line',
        open
          ? 'fixed inset-y-0 left-0 z-50 flex w-72 max-w-[85vw] flex-col overflow-hidden'
          : 'hidden',
        'md:sticky md:top-0 md:z-auto md:flex md:flex-col md:w-64 md:shrink-0 md:overflow-hidden md:[height:var(--app-vh,100dvh)]',
      ].join(' ')}
      aria-label={t('docs.sidebar.navAria')}
    >
      <div className="flex items-center justify-between border-b-2 border-pixel-line px-4 py-3 md:justify-center">
        <NavLink
          to="/docs/quickstart"
          className="font-display text-pixel-base text-pixel-fg chromatic hover:text-pixel-accent"
        >
          {t('docs.sidebar.title')}
          </NavLink>
        <button
          type="button"
          onClick={onClose}
          className="border-2 border-pixel-line bg-pixel-raised p-1 text-pixel-fg hover:bg-pixel-accent md:hidden"
          aria-label={t('docs.sidebar.close')}
        >
          <X className="h-4 w-4" strokeWidth={2} aria-hidden="true" />
        </button>
      </div>

      <nav className="min-h-0 flex-1 overflow-y-auto px-2 py-3" aria-label={t('docs.sidebar.navAria')}>
        {DOC_GROUP_ORDER.map((group) => {
          const entries = entriesByGroup.get(group) ?? [];
          if (entries.length === 0) return null;
          return (
            <div key={group} className="mb-4">
              <h2 className="px-2 py-1 font-pixel text-pixel-sm uppercase tracking-wide text-pixel-muted">
                {t(`docs.section.${group}`)}
              </h2>
              <ul>
                {entries.map((entry) => (
                  <li key={`${entry.group}-${entry.docId}`}>
                    <NavLink
                      to={`/docs/${entry.docId}`}
                      className={({ isActive }) =>
                        [
                          'block border-2 border-transparent px-2 py-1 font-body text-base',
                          isActive
                            ? 'border-pixel-line bg-pixel-raised text-pixel-fg'
                            : 'text-pixel-muted hover:bg-pixel-raised hover:text-pixel-fg',
                        ].join(' ')
                      }
                    >
                      {t(`docs.${entry.titleKey}`)}
                    </NavLink>
                  </li>
                ))}
              </ul>
            </div>
          );
        })}

        <div className="mb-4">
          <h2 className="px-2 py-1 font-pixel text-pixel-sm uppercase tracking-wide text-pixel-muted">
            {t('docs.section.apiReference')}
          </h2>
          <ul>
            <li>
              <NavLink
                to="/docs/api-reference"
                className={({ isActive }) =>
                  [
                    'block border-2 border-transparent px-2 py-1 font-body text-base',
                    isActive
                      ? 'border-pixel-line bg-pixel-raised text-pixel-fg'
                      : 'text-pixel-muted hover:bg-pixel-raised hover:text-pixel-fg',
                  ].join(' ')
                }
              >
                {t('docs.section.apiReference')}
              </NavLink>
            </li>
          </ul>
        </div>
      </nav>

      {/* Way out of the docs surface - pinned at the sidebar bottom so it
          stays reachable without scrolling, whatever the main content
          length. The mb clears the public fixed footer bar (~66px,
          z-40) which would otherwise overlay the link. */}
      <div className="shrink-0 border-t-2 border-pixel-line p-3 pb-[72px]">
        <DocsBackLink variant="link" />
      </div>
    </aside>
  );
}

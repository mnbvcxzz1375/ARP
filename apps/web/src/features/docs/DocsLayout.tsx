import { useEffect, useState } from 'react';
import { Outlet, useLocation } from 'react-router-dom';
import { Menu } from 'lucide-react';
import { useT } from '../../i18n';
import DocsBackLink from './DocsBackLink';
import DocsSidebar from './DocsSidebar';

/**
 * Public docs shell: grouped sidebar + markdown content.
 *
 * Layout follows the pixel design system: single accent color, hard 2px
 * borders, no curves. On <768px the sidebar collapses into a fixed overlay
 * opened by the "目录" button in the top bar.
 *
 * This route lives under PublicLayout, so it needs no sign-in.
 */
export default function DocsLayout() {
  const t = useT();
  const location = useLocation();
  const [sidebarOpen, setSidebarOpen] = useState(false);

  // Close the mobile overlay whenever the route changes.
  useEffect(() => {
    setSidebarOpen(false);
  }, [location.pathname]);

  return (
    <div className="flex min-h-screen flex-col bg-pixel-bg md:flex-row">
      {/* Mobile top bar: back navigation + contents toggle */}
      <div className="sticky top-0 z-30 flex items-center gap-3 border-b-2 border-pixel-line bg-pixel-surface px-4 py-2 md:hidden">
        <DocsBackLink variant="button" />
        <button
          type="button"
          onClick={() => setSidebarOpen(true)}
          className="flex min-h-[44px] items-center gap-2 border-2 border-pixel-line bg-pixel-raised px-3 py-1 font-pixel text-pixel-base text-pixel-fg hover:bg-pixel-accent"
          aria-label={t('docs.sidebar.contents')}
        >
          <Menu className="h-4 w-4" strokeWidth={2} aria-hidden="true" />
          {t('docs.sidebar.contents')}
        </button>
      </div>

      {/* Backdrop for the mobile overlay */}
      {sidebarOpen && (
        <button
          type="button"
          aria-label={t('docs.sidebar.close')}
          onClick={() => setSidebarOpen(false)}
          className="fixed inset-0 z-40 bg-black/50 md:hidden"
        />
      )}

      <DocsSidebar open={sidebarOpen} onClose={() => setSidebarOpen(false)} />

      <main
        className="min-w-0 flex-1 px-4 py-6 pb-16 md:px-8 md:pb-8"
        data-testid="docs-content"
      >
        <div className="mx-auto max-w-4xl">
          <Outlet />
        </div>
      </main>
    </div>
  );
}

import { Link, useNavigate } from 'react-router-dom';
import { useQueryClient } from '@tanstack/react-query';
import { ArrowLeft } from 'lucide-react';
import { useT } from '../../i18n';
import type { AuthUser } from '../../hooks/useAuth';
import { clearDocsOrigin, getDocsOrigin } from './docsEntryMemory';

/**
 * Back navigation for the public docs surface.
 *
 * Two problems this solves:
 *
 * 1. The docs site used to have no outgoing navigation at all: once a
 *    visitor opened /docs, every link on the page led deeper into
 *    docs, and the browser back button was the only way out.
 * 2. A plain history-back link only returns to the *previous* page -
 *    after in-docs navigation that is another docs page, not the
 *    console page the visitor came from. The entry origin (see
 *    docsEntryMemory) is preferred, so the trip lands on the exact
 *    page that led into the docs.
 *
 * Auth state is read NON-reactively on purpose. The docs subtree lives
 * under PublicLayout, which unmounts its Outlet while the /me probe is
 * in flight; a `useAuth()` observer mounted there would itself be
 * unmounted/remounted on every loading -> settled transition, and that
 * observer churn puts the auth query into an endless
 * pending:fetching loop (page stuck on the loading screen). The cache
 * read cannot subscribe, so it cannot churn; the destination is
 * computed once per mount, and a sign-in/out in another tab is a rare
 * edge that a full page load resolves anyway.
 */
export function docsBackDestination(isSignedIn: boolean | undefined): string {
  return isSignedIn ? '/app/overview' : '/login';
}

export default function DocsBackLink({ variant }: { variant: 'button' | 'link' }) {
  const t = useT();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const auth = queryClient.getQueryData<AuthUser>(['auth/me']);
  const isSignedIn = !!(auth && Array.isArray(auth.permissions) && auth.permissions.length > 0);

  const fallback = docsBackDestination(isSignedIn);
  const label = isSignedIn
    ? t('docs.sidebar.backToConsole')
    : t('docs.sidebar.backToLogin');

  const goBack = () => {
    // 1. The page that led into the docs (exact, not "previous page").
    const origin = getDocsOrigin();
    if (origin) {
      clearDocsOrigin();
      navigate(origin);
      return;
    }
    // 2. Single-level history back for direct in-app hops without a
    //    recorded origin. react-router tracks the entry index in history
    //    state; idx 0 means there is nothing to go back to.
    const state = window.history.state as { idx?: number } | null;
    const hasHistory = !!state && typeof state.idx === 'number' && state.idx > 0;
    if (hasHistory) {
      navigate(-1);
      return;
    }
    // 3. Direct visit (address bar / bookmark): deterministic way out.
    navigate(fallback);
  };

  if (variant === 'button') {
    return (
      <button
        type="button"
        onClick={goBack}
        className="flex min-h-[44px] items-center gap-2 border-2 border-pixel-line bg-pixel-raised px-3 py-1 font-pixel text-pixel-base text-pixel-fg hover:bg-pixel-accent"
        aria-label={t('docs.sidebar.backAria')}
      >
        <ArrowLeft className="h-4 w-4" strokeWidth={2} aria-hidden="true" />
        {t('docs.sidebar.back')}
      </button>
    );
  }

  // The sidebar link looks like a destination link (its label describes
  // the no-origin fallback) but behaves like a back button when an
  // origin or history exists: the click handler swaps the navigation,
  // so visitors land back on the exact console page they came from
  // instead of the console default.
  return (
    <Link
      to={fallback}
      onClick={(e) => {
        e.preventDefault();
        goBack();
      }}
      className="flex items-center gap-2 border-2 border-pixel-line bg-pixel-raised px-3 py-2 font-pixel text-pixel-base text-pixel-fg hover:bg-pixel-accent"
    >
      <ArrowLeft className="h-4 w-4" strokeWidth={2} aria-hidden="true" />
      {label}
    </Link>
  );
}

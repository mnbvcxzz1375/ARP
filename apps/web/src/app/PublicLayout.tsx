import { Outlet, Navigate, Link, useSearchParams, useLocation } from 'react-router-dom';
import { DEFAULT_LOGIN_REDIRECT, resolveNextTarget, useAuth } from '../hooks/useAuth';
import LoadingState from '../components/LoadingState';
import LanguageSwitcher from '../components/LanguageSwitcher';
import { useT } from '../i18n';
import { rememberDocsOrigin } from '../features/docs/docsEntryMemory';

/**
 * Public surface shell. Auth probe behavior: signed-in visitors are
 * redirected to a validated `next` deep link when present (guard contract:
 * /login?next=<encoded path>), otherwise to the personal console.
 *
 * The CRT overlay layers (fixed, pointer-events:none) give the public
 * pages the same Chromatic-screen signature as the console; they are
 * auto-disabled on mobile (<768px) and under prefers-reduced-motion.
 *
 * Footer: fixed bottom bar with the docs entry (namespace `docs`) and the
 * pixel LanguageSwitcher. Public pages (home / login / request-access /
 * docs) center their content in min-h-screen panels, so the bar is fixed
 * rather than in-flow to stay visible without pushing content below the
 * fold.
 */
export default function PublicLayout() {
  const { isLoading, isError, data } = useAuth();
  const [searchParams] = useSearchParams();
  const { pathname } = useLocation();
  const t = useT();
  if (isLoading) return <LoadingState />;
  // The docs sub-site stays readable for signed-in visitors too (the
  // docs.openai.com model): the bounce below exists to keep an authenticated
  // session out of auth-flow pages (/login, /request-access), not out of
  // reference material. DocsBackLink provides the way back to the console.
  const isDocsPath = pathname === '/docs' || pathname.startsWith('/docs/');
  if (!isError && data && pathname !== '/no-access' && !isDocsPath) {
    // Signed-in visitor on a public page: honor a validated `next` deep link
    // (e.g. /login?next=%2Fenterprise%2Frelay-nodes), else the console default.
    const nextTarget = resolveNextTarget(searchParams.get('next')) ?? DEFAULT_LOGIN_REDIRECT;
    return <Navigate to={nextTarget} replace />;
  }
  // `/no-access` is exempt from the authenticated bounce above: it is the
  // fail-closed destination the auth guards (RequireAuth/RequireAdmin in
  // App.tsx) send an authenticated session to when it lacks the required
  // permissions. Bouncing such a session onward to the console would put it
  // straight back into a guarded route (or a 401 -> /login slide), looping
  // the very redirect the guards exist to break. The page itself renders
  // for authenticated visitors; e2e/no-access.spec.ts pins this contract.
  // Unauthenticated visitors typing /no-access directly also see the page
  // (they take the `!data` path above, which renders the public surface).
  return (
    <>
      <div className="pixel-scanlines" aria-hidden="true" />
      <div className="pixel-rgb-stripes" aria-hidden="true" />
      <Outlet />
      <footer
        className="fixed bottom-0 inset-x-0 z-40 flex items-center justify-center gap-4 border-t-2 border-pixel-line bg-pixel-surface px-4 py-2"
        aria-label={t('shell.language.aria')}
      >
        <nav aria-label={t('docs.footer.entryAria')}>
          <Link
            to="/docs"
            onClick={() => rememberDocsOrigin()}
            className="font-pixel text-pixel-base text-pixel-muted underline hover:text-pixel-accent"
          >
            {t('docs.footer.entry')}
          </Link>
        </nav>
        <LanguageSwitcher />
      </footer>
    </>
  );
}

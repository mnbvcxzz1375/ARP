/**
 * Remembers the page a visitor came FROM when they entered the docs site.
 *
 * Problem being solved: "返回控制台" used `navigate(-1)`, which only
 * returns to the *previous* page — after any in-docs navigation (say
 * Quickstart -> Protocol -> CLI) that is another docs page, not the
 * console page the visitor originally clicked from.
 *
 * Strategy: every in-app entry point into /docs (shell footer link,
 * login / request-access cards, public footer link) records the current
 * path to sessionStorage (never overwriting when the current page is
 * itself a docs page). DocsBackLink then prefers the recorded origin
 * over history-back, so the trip returns to the actual entry page.
 * Direct visits (address bar, bookmark, external link) leave no origin
 * and fall back to navigate(-1), then to the console / sign-in page.
 *
 * sessionStorage, not localStorage: the origin is a per-tab navigation
 * fact, not a preference.
 */

const KEY = 'agentnet-docs-origin';

/** True when the path itself is inside the docs sub-site. */
function isDocsPath(pathname: string): boolean {
  return pathname === '/docs' || pathname.startsWith('/docs/');
}

/**
 * Record the entry origin. Call from every in-app link that navigates
 * INTO /docs. Silently no-ops when the current page is already a docs
 * page (the footer link is rendered on docs pages too) so a within-docs
 * click can never clobber the real origin.
 */
export function rememberDocsOrigin(): void {
  if (typeof window === 'undefined') return;
  if (isDocsPath(window.location.pathname)) return;
  try {
    window.sessionStorage.setItem(KEY, window.location.pathname + window.location.search);
  } catch {
    // sessionStorage unavailable (private mode etc.): fall back to
    // history-based back at click time.
  }
}

/**
 * The recorded entry origin, or null when the visitor came to the docs
 * site directly or the recorded origin itself points into /docs.
 */
export function getDocsOrigin(): string | null {
  if (typeof window === 'undefined') return null;
  try {
    const origin = window.sessionStorage.getItem(KEY);
    if (!origin || isDocsPath(origin)) return null;
    return origin;
  } catch {
    return null;
  }
}

/** Drop the recorded origin (after using it). */
export function clearDocsOrigin(): void {
  if (typeof window === 'undefined') return;
  try {
    window.sessionStorage.removeItem(KEY);
  } catch {
    // Ignore: worst case the stale origin is reused on the next entry.
  }
}

/**
 * Deep-link preservation E2E (shard Y — stage 2.5).
 *
 * Verifies the consumer side of the `next` query-parameter contract:
 *   1. An unauthenticated visit to a protected page lands on /login with the
 *      original path carried in the `next` parameter (guard side, shard X:
 *      /login?next=<encodeURIComponent'd path incl. search>).
 *   2. After a real API login on the page context (apiLogin style, copied
 *      from visual-regression.spec.ts), the signed-in visitor is sent to the
 *      `next` target — not to the personal console default.
 *
 * Prerequisites (same as authenticated.spec.ts):
 *   - API server running (default localhost:8000)
 *   - Web dev server running (default localhost:5173)
 *   - E2E_DASHBOARD_USERNAME / E2E_DASHBOARD_API_KEY env vars
 *     (seed_e2e_user.py seeds a super_admin, which can reach
 *     /enterprise/relay-nodes)
 */
import { test, expect } from '@playwright/test';

const API_BASE = process.env.API_BASE || 'http://localhost:8000';

const username = process.env.E2E_DASHBOARD_USERNAME;
const apiKey = process.env.E2E_DASHBOARD_API_KEY;

test.beforeAll(() => {
  const missing: string[] = [];
  if (!username) missing.push('E2E_DASHBOARD_USERNAME');
  if (!apiKey) missing.push('E2E_DASHBOARD_API_KEY');
  if (missing.length > 0) {
    throw new Error(
      `Missing required environment variables: ${missing.join(', ')}. ` +
        `Run scripts/seed_e2e_user.py against your database, then export ` +
        `the printed API key before running E2E tests.`,
    );
  }
});

/** Target route used for the deep-link scenarios. */
const PROTECTED_PATH = '/enterprise/relay-nodes';

/**
 * Perform a real API login on the current page context.
 * Uses page.request (shared with the page) so cookies are immediately
 * available. Same approach as visual-regression.spec.ts's apiLogin.
 */
async function apiLogin(page: import('@playwright/test').Page) {
  const response = await page.request.post(`${API_BASE}/v1/dashboard/auth/login`, {
    data: { username: username!, api_key: apiKey! },
  });

  if (!response.ok()) {
    throw new Error(
      `API login failed with HTTP ${response.status()} (${response.statusText()}). ` +
        `Verify E2E_DASHBOARD_USERNAME and E2E_DASHBOARD_API_KEY are correct.`,
    );
  }
}

test.describe('Deep-link preservation (login next + signed-in landing)', () => {
  test('unauthenticated protected visit redirects to /login?next=<path>', async ({ page }) => {
    await page.goto(PROTECTED_PATH);

    // Guard side (shard X): land on /login with the encoded original path.
    await expect(page).toHaveURL(/\/login/, { timeout: 10000 });
    const nextParam = new URL(page.url()).searchParams.get('next');
    expect(nextParam).not.toBeNull();
    expect(decodeURIComponent(nextParam!)).toBe(PROTECTED_PATH);
  });

  test('after login, the signed-in visitor lands on the next target', async ({ page }) => {
    // 1. Unauthenticated visit — guard sends us to /login?next=...
    await page.goto(PROTECTED_PATH);
    await expect(page).toHaveURL(/\/login/, { timeout: 10000 });
    const loginUrl = page.url();
    expect(new URL(loginUrl).searchParams.get('next')).not.toBeNull();

    // 2. Authenticate via the shared page context (apiLogin style).
    await apiLogin(page);

    // 3. Reload the login page: PublicLayout now sees an authenticated
    //    session and must follow the validated next target.
    await page.goto(loginUrl);
    await expect(page).toHaveURL(PROTECTED_PATH, { timeout: 10000 });

    // The relay-nodes page itself must render, not a redirect stub.
    await expect(page.locator('h2, .text-xl').first()).toContainText(/relay/i, {
      timeout: 10000,
    });
  });
});

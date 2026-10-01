import { test, expect } from '@playwright/test';

/**
 * Settings center e2e (pixel design system, /app/settings).
 *
 * Flow: sign in against the local backend -> open the settings page ->
 * assert both pixel panels render in English -> capture the page
 * screenshot -> switch the language to Chinese via the in-card
 * segmented control -> assert the settings copy flips to Chinese.
 *
 * Requires the same environment as authenticated.spec.ts:
 *   1. The API server running (default localhost:8000)
 *   2. The web dev server running (default localhost:5173)
 *   3. E2E_DASHBOARD_USERNAME / E2E_DASHBOARD_API_KEY exported
 *      (scripts/seed_e2e_user.py prints the raw key).
 */
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

/** Shared login helper — fills credentials and submits. */
async function login(page: import('@playwright/test').Page) {
  await page.goto('/login');
  await page.getByTestId('login-username').fill(username!);
  await page.getByTestId('login-api-key').fill(apiKey!);
  await page.click('button[type="submit"]');
}

test.describe('Settings page', () => {
  test('renders panels, switches to Chinese and screenshots', async ({ page }) => {
    // Intercept the preferences PATCH: this spec verifies the *frontend*
    // behavior of the language switch (optimistic apply, <html lang>,
    // localStorage, copy flip). The backend round-trip is covered by
    // apps/api/tests/test_user_preferences.py. Fulfilling the PATCH here
    // keeps the shared e2e user record untouched: with fullyParallel runs a
    // persisted 'zh' preference races other spec files (authenticated,
    // deep-link), whose pages then resolve zh and fail their English copy
    // assertions before this file's afterAll cleanup can run.
    await page.route('**/v1/dashboard/auth/me/preferences', async (route) => {
      if (route.request().method() !== 'PATCH') {
        await route.continue();
        return;
      }
      let payload: { locale?: 'en' | 'zh' | null } = {};
      try {
        payload = route.request().postDataJSON() ?? {};
      } catch {
        payload = {};
      }
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ locale: payload.locale ?? null, preferences: {} }),
      });
    });

    await login(page);
    await page.waitForURL(/\/(app|admin)/, { timeout: 10000 });

    await page.goto('/app/settings');

    // Both pixel panels are visible with English copy.
    await expect(page.getByTestId('settings-appearance-panel')).toBeVisible({ timeout: 10000 });
    await expect(page.getByTestId('settings-account-panel')).toBeVisible();
    await expect(page.getByRole('heading', { name: 'Settings', level: 2 })).toBeVisible();
    await expect(page.getByTestId('settings-logout')).toContainText('Sign Out');
    await expect(page.getByTestId('settings-api-keys-link')).toHaveAttribute(
      'href',
      '/app/api-keys',
    );

    // Screenshot artifact (relative to the playwright config root, apps/web).
    await page.screenshot({ path: 'e2e/screenshots/settings-page.png', fullPage: true });

    // Switch the language to Chinese via the in-card segmented control.
    await page.getByTestId('settings-language-zh').click();

    // The settings page copy flips to Chinese (settings namespace).
    await expect(page.getByRole('heading', { name: '设置', level: 2 })).toBeVisible();
    await expect(page.getByTestId('settings-appearance-panel')).toContainText('外观');
    await expect(page.getByTestId('settings-account-panel')).toContainText('账户');
    await expect(page.getByTestId('settings-logout')).toContainText('退出登录');
    await expect(page.locator('html')).toHaveAttribute('lang', 'zh');

    // The locale is applied locally (html lang + localStorage) here; the
    // backend PATCH round-trip (/me.locale echo) is covered by
    // apps/api/tests/test_user_preferences.py.
    const stored = await page.evaluate(() => window.localStorage.getItem('agentnet-locale'));
    expect(stored).toBe('zh');
  });
});

/**
 * Resolved origin for the suite cleanup call below. Only http/https and
 * only loopback hosts are ever accepted (the local test backend by
 * definition); anything else falls back to the documented default.
 */
const CLEANUP_API_BASE: string = (() => {
  const candidate = process.env.API_BASE ?? 'http://localhost:8000';
  const ALLOWED_HOSTS = new Set(['localhost', '127.0.0.1', '[::1]', '::1']);
  try {
    const url = new URL(candidate);
    if (
      (url.protocol === 'http:' || url.protocol === 'https:') &&
      ALLOWED_HOSTS.has(url.hostname)
    ) {
      return url.origin;
    }
  } catch {
    // invalid URL: fall through to the safe default below
  }
  return 'http://127.0.0.1:8000';
})();

/**
 * Cleanup after the locale-switch test: the test ends with the e2e user's
 * backend locale preference set to 'zh' (that persistence is exactly what
 * the last assertion verifies). Without a reset, the NEXT suite run
 * resolves the e2e user's locale to zh and the English assertions in this
 * file and authenticated.spec.ts fail. Restore the no-preference state
 * the seed script leaves behind. This never touches an assertion; it only
 * returns the shared user record to its pre-test state.
 */
test.afterAll(async () => {
  try {
    const loginRes = await fetch(`${CLEANUP_API_BASE}/v1/dashboard/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, api_key: apiKey }),
    });
    const setCookies: string[] = loginRes.headers.getSetCookie?.() ?? [];
    const sessionCookie = setCookies.find((c) => c.startsWith('agentnet_session='));
    const csrf = setCookies
      .find((c) => c.startsWith('agentnet_csrf='))
      ?.split('=')[1]
      ?.split(';')[0];
    if (!sessionCookie || !csrf) return;
    await fetch(`${CLEANUP_API_BASE}/v1/dashboard/auth/me/preferences`, {
      method: 'PATCH',
      headers: {
        'Content-Type': 'application/json',
        Cookie: sessionCookie.split(';')[0],
        'X-CSRF-Token': csrf,
      },
      body: JSON.stringify({ locale: null }),
    });
  } catch {
    // Best-effort state cleanup; it can never affect the assertions above.
  }
});

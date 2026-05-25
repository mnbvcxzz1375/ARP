/**
 * Visual regression testing for key pages.
 *
 * FIRST-RUN FLOW:
 *   This test uses Playwright's toHaveScreenshot() assertion.
 *   On first run, baseline snapshots will be generated in
 *   e2e/visual-regression.spec.ts-snapshots/. Commit these
 *   baselines to the repo as the reference for future runs.
 *
 *   To update baselines after intentional design changes:
 *     npx playwright test e2e/visual-regression.spec.ts --update-snapshots
 *
 *   Then review the new snapshots and commit them.
 *
 * PREREQUISITES:
 *   - Dev server running at BASE_URL (default http://localhost:5173)
 *   - For authenticated pages, set E2E_DASHBOARD_USERNAME and
 *     E2E_DASHBOARD_API_KEY env vars.
 *   - API_BASE (default http://127.0.0.1:8000) must point at the backend.
 *
 * AUTH STRATEGY:
 *   Authenticated visual tests use apiLogin(page) to perform a single real
 *   API login via page.request.post on the current page context. No
 *   storageState files are used. The entire suite performs exactly 2 logins
 *   (one per merged test) to avoid rate-limit hits.
 */
import { test, expect } from '@playwright/test';

const API_BASE = process.env.API_BASE || 'http://127.0.0.1:8000';
const AUTHENTICATED = !!process.env.E2E_DASHBOARD_USERNAME && !!process.env.E2E_DASHBOARD_API_KEY;

/**
 * Perform a real API login on the current page context.
 * Uses page.request (shared with the page) so cookies are immediately available.
 * Throws on failure so the test fails loudly.
 */
async function apiLogin(page: import('@playwright/test').Page) {
  const username = process.env.E2E_DASHBOARD_USERNAME!;
  const apiKey = process.env.E2E_DASHBOARD_API_KEY!;

  const response = await page.request.post(`${API_BASE}/v1/dashboard/auth/login`, {
    data: { username, api_key: apiKey },
  });

  if (!response.ok()) {
    throw new Error(
      `API login failed with HTTP ${response.status()} (${response.statusText()}). ` +
      `Verify E2E_DASHBOARD_USERNAME and E2E_DASHBOARD_API_KEY are correct.`,
    );
  }
}

// ---------------------------------------------------------------------------
// Public pages — no auth needed
// ---------------------------------------------------------------------------

test.describe('Visual regression — public pages', () => {
  test('home page', async ({ page }) => {
    await page.goto('/');
    await expect(page.getByText('AgentNet')).toBeVisible();
    await expect(page).toHaveScreenshot('home-page.png', { maxDiffPixelRatio: 0.01 });
  });

  test('login page', async ({ page }) => {
    await page.goto('/login');
    await expect(page.getByRole('button', { name: 'Sign In' })).toBeVisible();
    await expect(page).toHaveScreenshot('login-page.png', { maxDiffPixelRatio: 0.01 });
  });

  test('request access page', async ({ page }) => {
    await page.goto('/request-access');
    await expect(page.getByRole('heading', { name: 'Request Access' })).toBeVisible();
    await expect(page).toHaveScreenshot('request-access-page.png', { maxDiffPixelRatio: 0.01 });
  });

  test('request access enterprise mode', async ({ page }) => {
    await page.goto('/request-access?mode=enterprise');
    await expect(page.getByRole('heading', { name: 'Request Access' })).toBeVisible();
    await expect(page.getByLabel('Organization')).toBeVisible();
    await expect(page).toHaveScreenshot('request-access-enterprise.png', { maxDiffPixelRatio: 0.01 });
  });
});

// ---------------------------------------------------------------------------
// Responsive viewports — public pages, no auth
// ---------------------------------------------------------------------------

test.describe('Visual regression — responsive viewports', () => {
  const viewports = [
    { name: 'mobile', width: 375, height: 812 },
    { name: 'tablet', width: 768, height: 1024 },
  ];

  for (const vp of viewports) {
    test(`home page at ${vp.name}`, async ({ page }) => {
      await page.setViewportSize({ width: vp.width, height: vp.height });
      await page.goto('/');
      await expect(page.getByText('AgentNet')).toBeVisible();

      const scrollWidth = await page.evaluate(() => document.documentElement.scrollWidth);
      const clientWidth = await page.evaluate(() => document.documentElement.clientWidth);
      expect(scrollWidth).toBeLessThanOrEqual(clientWidth + 2);

      await expect(page).toHaveScreenshot(`home-${vp.name}.png`, { maxDiffPixelRatio: 0.02 });
    });

    test(`login page at ${vp.name}`, async ({ page }) => {
      await page.setViewportSize({ width: vp.width, height: vp.height });
      await page.goto('/login');
      await expect(page.getByRole('button', { name: 'Sign In' })).toBeVisible();

      const scrollWidth = await page.evaluate(() => document.documentElement.scrollWidth);
      const clientWidth = await page.evaluate(() => document.documentElement.clientWidth);
      expect(scrollWidth).toBeLessThanOrEqual(clientWidth + 2);

      await expect(page).toHaveScreenshot(`login-${vp.name}.png`, { maxDiffPixelRatio: 0.02 });
    });
  }
});

// ---------------------------------------------------------------------------
// Authenticated pages — single login, all screenshots in one test
// ---------------------------------------------------------------------------

test.describe('Visual regression — authenticated pages', () => {
  test.skip(!AUTHENTICATED, 'Requires E2E_DASHBOARD_USERNAME + E2E_DASHBOARD_API_KEY');

  test('authenticated page screenshots', async ({ page }) => {
    await apiLogin(page);

    const pages = [
      { path: '/app/overview', snapshot: 'app-overview.png' },
      { path: '/enterprise/overview', snapshot: 'enterprise-overview.png' },
      { path: '/enterprise/system', snapshot: 'enterprise-system.png' },
      { path: '/enterprise/network-scopes', snapshot: 'network-scopes.png' },
      { path: '/enterprise/network-zones', snapshot: 'network-zones.png' },
    ];

    for (const { path, snapshot } of pages) {
      await page.goto(path);
      await page.waitForLoadState('networkidle');
      await expect(page).toHaveScreenshot(snapshot, { maxDiffPixelRatio: 0.02 });
    }
  });
});

// ---------------------------------------------------------------------------
// Responsive authenticated overflow — single login, all checks in one test
// ---------------------------------------------------------------------------

test.describe('Visual regression — responsive authenticated overflow check', () => {
  test.skip(!AUTHENTICATED, 'Requires E2E_DASHBOARD_USERNAME + E2E_DASHBOARD_API_KEY');

  test('no overflow at mobile and tablet viewports', async ({ page }) => {
    await apiLogin(page);

    const authenticatedPages = [
      '/app/overview',
      '/enterprise/overview',
      '/enterprise/network-scopes',
      '/enterprise/network-zones',
    ];

    const viewports = [
      { name: 'mobile', width: 375, height: 812 },
      { name: 'tablet', width: 768, height: 1024 },
    ];

    for (const vp of viewports) {
      await page.setViewportSize({ width: vp.width, height: vp.height });

      for (const pagePath of authenticatedPages) {
        await page.goto(pagePath);
        await page.waitForLoadState('networkidle');

        const scrollWidth = await page.evaluate(() => document.documentElement.scrollWidth);
        const clientWidth = await page.evaluate(() => document.documentElement.clientWidth);
        expect(scrollWidth).toBeLessThanOrEqual(
          clientWidth + 2,
          `Overflow on ${pagePath} at ${vp.name} viewport (${scrollWidth}px > ${clientWidth}px)`,
        );
      }
    }
  });
});

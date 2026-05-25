/**
 * Authenticated E2E test suite for the AgentNet dashboard.
 *
 * This test exercises the real UI flow after authenticating against the
 * local backend. It requires:
 *   1. The API server running (default localhost:8000)
 *   2. The web dev server running (default localhost:5173)
 *   3. Environment variables set:
 *      - E2E_DASHBOARD_USERNAME  (e.g. "e2e_admin")
 *      - E2E_DASHBOARD_API_KEY   (raw API key from seed_e2e_user.py)
 *
 * If any requirement is missing, tests fail with an actionable message
 * rather than producing fake positive results.
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

/** Shared login helper — fills credentials and submits. */
async function login(page: import('@playwright/test').Page) {
  await page.goto('/login');
  await page.getByTestId('login-username').fill(username!);
  await page.getByTestId('login-api-key').fill(apiKey!);
  await page.click('button[type="submit"]');
}

test.describe('Authenticated dashboard flow', () => {
  test('login page renders and accepts credentials', async ({ page }) => {
    await page.goto('/login');

    // Login form should be visible via accessible labels
    await expect(page.getByLabel('Username')).toBeVisible({ timeout: 10000 });
    await expect(page.getByLabel('API Key')).toBeVisible();

    // Fill via testid
    await page.getByTestId('login-username').fill(username!);
    await page.getByTestId('login-api-key').fill(apiKey!);

    // Submit
    await page.click('button[type="submit"]');

    // Should redirect away from login — either to /app or /admin
    await page.waitForURL(/\/(app|admin)/, { timeout: 10000 }).catch(async () => {
      const errorEl = page.locator('.text-red-600');
      const errorText = (await errorEl.isVisible()) ? await errorEl.textContent() : 'No error message visible';
      throw new Error(
        `Login did not redirect to dashboard. Check if user "${username}" exists ` +
        `with a valid API key in the database. Error: ${errorText}`,
      );
    });
  });

  test('dashboard shows navigation after login', async ({ page }) => {
    await login(page);
    await page.waitForURL(/\/(app|admin)/, { timeout: 10000 });

    // Navigation sidebar should be visible
    const nav = page.locator('nav').first();
    await expect(nav).toBeVisible({ timeout: 5000 });
  });

  test('admin enterprise pages are accessible', async ({ page }) => {
    await login(page);
    await page.waitForURL(/\/(app|admin)/, { timeout: 10000 });

    // Navigate to enterprise access requests
    await page.goto('/enterprise/access-requests');
    await expect(page.locator('h2, .text-xl')).toContainText('Access Request', {
      timeout: 8000,
    });

    // Navigate to network scopes
    await page.goto('/enterprise/network-scopes');
    await expect(page.locator('h2, .text-xl')).toContainText('Network Scope', {
      timeout: 8000,
    });

    // Navigate to network zones
    await page.goto('/enterprise/network-zones');
    await expect(page.locator('h2, .text-xl')).toContainText('Network Zone', {
      timeout: 8000,
    });
  });

  test('access request detail page shows 404 for invalid ID', async ({ page }) => {
    await login(page);
    await page.waitForURL(/\/(app|admin)/, { timeout: 10000 });

    // Navigate to a non-existent access request
    await page.goto('/enterprise/access-requests/00000000-0000-0000-0000-000000000000');

    // Should show error / not found state
    await expect(page.locator('text=/not found|failed to load/i')).toBeVisible({
      timeout: 8000,
    });
  });

  test('unauthenticated access redirects to login', async ({ page }) => {
    // Try to access protected page without login
    await page.goto('/enterprise/access-requests');

    // Should be redirected to login — wait for the redirect to complete
    await expect(page).toHaveURL(/\/login/, { timeout: 10000 });
  });
});

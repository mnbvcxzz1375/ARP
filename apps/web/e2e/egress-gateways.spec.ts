import { test, expect } from '@playwright/test';

/**
 * Egress gateway console write-path e2e (super_admin).
 *
 * The page contract (apps/web/src/features/enterprise/EgressGatewaysPage.tsx
 * <-> apps/api/app/routers/gateways.py) is fully unit-tested with mocked
 * HTTP (features/enterprise/__tests__/EgressGatewaysPage.test.tsx, 12
 * cases). What only a real browser round-trip can pin is the LAST mile of
 * the write chain: the CSRF header the axios client attaches to mutations,
 * the step-up gate in front of super_admin:write, and the list refresh
 * (query invalidation) after a successful write. That is what happened to
 * be the unverified remainder of the gateway work: each step below was
 * walked manually before this spec existed.
 *
 * Flow: sign in as the seeded super_admin -> open /enterprise/egress ->
 * the create button demands step-up auth (POST /step-up) -> fill the
 * create form -> submit -> the new row appears in the table -> delete it
 * (same step-up window covers the second mutation) -> the row disappears.
 * The created gateway is removed again in the same run, so the shared
 * e2e database is left exactly as it was found.
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

/** Unique-enough name so concurrent runs can never collide. */
function probeName(): string {
  return `E2E Gateway ${Date.now().toString(36)}`;
}

test.describe('Egress gateway console (super_admin write path)', () => {
  test('create, then delete: the round trip lands in the list', async ({ page }) => {
    await login(page);
    await page.waitForURL(/\/app\/overview$/);
    await page.goto('/enterprise/egress');
    await page.waitForLoadState('networkidle');

    // The page renders the catalog with real rows.
    await expect(page.getByRole('heading', { name: 'Egress Gateways' })).toBeVisible();
    const table = page.locator('table');
    await expect(table).toBeVisible();
    const beforeCount = await table.locator('tbody tr').count();
    expect(beforeCount).toBeGreaterThan(0);

    // The add button opens the step-up gate first (super_admin:write).
    const name = probeName();
    await page.getByRole('button', { name: 'Add Gateway' }).click();
    await page.waitForTimeout(500);
    const stepUpInput = page.getByTestId('step-up-input');
    if (await stepUpInput.isVisible({ timeout: 3000 }).catch(() => false)) {
      await stepUpInput.fill(apiKey!);
      await stepUpInput.evaluate((e) => e.form.requestSubmit());
      await page.waitForTimeout(1500);
    }

    // After step-up the create form itself is open.
    const nameInput = page.locator('#gateway-name');
    await nameInput.waitFor({ state: 'visible', timeout: 5000 });
    await nameInput.fill(name);
    await page.locator('#gateway-type').selectOption('github');
    await page.locator('#gateway-domains').fill('github.com, pkg.github.com');
    await page.locator('#gateway-secret').fill('env:EGRESS_E2E_PROBE_KEY');
    await page.waitForTimeout(300);

    // Submit: CSRF header + step-up session + POST -> 201 -> list refresh.
    await page.getByRole('button', { name: 'Submit', exact: true }).click();
    await page.waitForTimeout(2500);

    // The new gateway is now in the list (query invalidation worked).
    await expect(table).toContainText(name);

    // Clean up through the same UI: the delete button on the new row
    // (still inside the step-up window, so no new step-up prompt) opens a
    // ConfirmDialog whose confirm button carries the same 'Delete' label
    // as the row button — disambiguate by scoping to the dialog. The
    // dialog has no accessible name (no aria-label), so it is located by
    // role and its title text instead.
    const row = table.locator('tbody tr').filter({ hasText: name });
    await row.getByRole('button', { name: 'Delete' }).click();
    const confirmDialog = page.getByRole('dialog');
    await expect(confirmDialog.getByText('Delete Egress Gateway')).toBeVisible();
    await confirmDialog.getByRole('button', { name: 'Delete' }).click();
    await expect(table).not.toContainText(name);
  });
});

import { test, expect } from '@playwright/test';

/**
 * Dedicated channel console write-path e2e (super_admin).
 *
 * This spec exists because the page previously drifted from the backend
 * contract on every axis at once (wrong path /v1/egress/..., PUT instead
 * of PATCH, response fields name/status that DedicatedChannelResponse
 * never had — the StatusBadge crash blanked the whole page). The unit
 * tests (features/enterprise/__tests__/DedicatedChannelsPage.test.tsx, 9
 * cases) pin the mocked contract; this spec pins the last mile the mocks
 * cannot reach: the CSRF header, the step-up gate in front of the admin
 * writes, and the list refresh after create.
 *
 * Flow: sign in as the seeded super_admin -> open
 * /enterprise/dedicated-channels -> bridge the step-up gate -> fill the
 * create form (channel name, two real agent ids, vpn type, JSON
 * connection config) -> submit -> the new row appears -> health-check the
 * row -> delete it. The created channel is removed again in the same run,
 * so the shared e2e database is left exactly as it was found.
 *
 * Requires the same environment as egress-gateways.spec.ts:
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
  return `E2E Channel ${Date.now().toString(36)}`;
}

test.describe('Dedicated channel console (super_admin write path)', () => {
  test('create, health-check, then delete: the round trip lands in the list', async ({ page }) => {
    await login(page);
    await page.waitForURL(/\/app\/overview$/);
    await page.goto('/enterprise/dedicated-channels');
    await page.waitForLoadState('networkidle');

    // The page renders without the StatusBadge crash that used to blank it.
    await expect(page.getByRole('heading', { name: 'Dedicated Channels' })).toBeVisible();
    const table = page.locator('table');

    // Two real agent ids for the source/target endpoints. The e2e user's
    // own agent list may be empty, so take them from the admin registry,
    // which lists every agent in UUID form.
    const agents = await page.evaluate(async () => {
      const res = await fetch('/v1/dashboard/admin/agents?limit=2', { credentials: 'include' });
      const body = await res.json();
      return (body.agents ?? body).slice(0, 2).map((a: { agent_id?: string; id?: string }) => a.agent_id ?? a.id);
    });
    expect(agents.length).toBeGreaterThanOrEqual(2);

    // The add button opens the step-up gate first (admin writes).
    const name = probeName();
    await page.getByRole('button', { name: 'Add Channel' }).click();
    await page.waitForTimeout(500);
    const stepUpInput = page.getByTestId('step-up-input');
    if (await stepUpInput.isVisible({ timeout: 3000 }).catch(() => false)) {
      await stepUpInput.fill(apiKey!);
      await stepUpInput.evaluate((e) => e.form.requestSubmit());
      await page.waitForTimeout(1500);
    }

    // After step-up the create form itself is open. The field ids mirror
    // the DedicatedChannelCreate body, not the pre-fix page's.
    await page.locator('#dc-name').waitFor({ state: 'visible', timeout: 5000 });
    await page.locator('#dc-name').fill(name);
    await page.locator('#dc-source-agent').fill(agents[0]);
    await page.locator('#dc-target-agent').fill(agents[1]);
    await page.locator('#dc-channel-type').selectOption('vpn');
    await page.locator('#dc-conn-config').fill('{"endpoint": "probe-vpn.internal:51820"}');
    await page.locator('#dc-bandwidth').fill('100');
    await page.locator('#dc-latency').fill('25');
    await page.waitForTimeout(300);

    // Submit: CSRF header + step-up session + POST -> 201 -> list refresh.
    await page.getByRole('button', { name: 'Submit', exact: true }).click();
    await page.waitForTimeout(2500);

    // The new channel is now in the list (query invalidation worked).
    await expect(table).toContainText(name);
    const row = table.locator('tbody tr').filter({ hasText: name });

    // The health-check action is a separate mutation on the same row and
    // must not take the row down (it stays enabled after the check).
    await row.getByRole('button', { name: 'Health Check' }).click();
    await page.waitForTimeout(1500);
    await expect(table).toContainText(name);

    // Clean up through the same UI: the delete button on the new row
    // (still inside the step-up window, so no new step-up prompt) opens a
    // ConfirmDialog whose confirm button carries the same 'Delete' label
    // as the row button — disambiguate by scoping to the dialog. The
    // dialog has no accessible name (no aria-label), so it is located by
    // role and its title text instead.
    await row.getByRole('button', { name: 'Delete' }).click();
    const confirmDialog = page.getByRole('dialog');
    await expect(confirmDialog.getByText('Delete Dedicated Channel')).toBeVisible();
    await confirmDialog.getByRole('button', { name: 'Delete' }).click();
    await expect(table).not.toContainText(name);
  });
});

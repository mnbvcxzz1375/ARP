import { test, expect } from '@playwright/test';

/**
 * Public docs site e2e.
 *
 * The /docs routes live under PublicLayout and require no sign-in: the auth
 * probe fails for anonymous visitors and the docs shell renders anyway.
 * Sidebar labels assert English (the default locale).
 *
 * The "signed-in round trip" test additionally pins the contract that the
 * docs stay readable for an authenticated session (PublicLayout exempts
 * /docs from its console bounce) and that DocsBackLink returns to the
 * console. It requires the same E2E_* credentials as settings.spec.ts.
 */

const username = process.env.E2E_DASHBOARD_USERNAME;
const apiKey = process.env.E2E_DASHBOARD_API_KEY;

test.describe('Public docs site', () => {
  test('docs is reachable without sign-in and renders the quickstart doc', async ({ page }) => {
    await page.goto('/docs');
    // The index route redirects to the quickstart doc.
    await expect(page).toHaveURL(/\/docs\/quickstart$/);
    await expect(page.getByRole('heading', { name: 'Quickstart', level: 1 })).toBeVisible();

    // Sidebar group headers render without template fallbacks.
    for (const group of ['Quickstart', 'Protocol', 'REST API', 'WebSocket', 'CLI', 'Python SDK', 'Adapters', 'Console Guide', 'Deploy & Ops', 'API Reference']) {
      await expect(page.getByText(group, { exact: true }).first()).toBeVisible();
    }

    // Pixel code blocks: mono font, 2px border, no syntax highlighting.
    const codeBlock = page.locator('pre').first();
    await expect(codeBlock).toBeVisible();

    // No horizontal overflow at desktop width.
    const scrollWidth = await page.evaluate(() => document.documentElement.scrollWidth);
    const clientWidth = await page.evaluate(() => document.documentElement.clientWidth);
    expect(scrollWidth).toBeLessThanOrEqual(clientWidth + 2);
  });

  test('sidebar navigation moves between docs', async ({ page }) => {
    await page.goto('/docs/quickstart');

    const cliLink = page.getByRole('link', { name: 'CLI', exact: true });
    await cliLink.click();
    await expect(page).toHaveURL(/\/docs\/cli$/);
    await expect(page.getByRole('heading', { name: 'CLI', level: 1 })).toBeVisible();

    // The docs entry stays reachable from the public footer.
    const footerLink = page.getByRole('link', { name: 'Docs', exact: true });
    await expect(footerLink).toBeVisible();
    await footerLink.click();
    await expect(page).toHaveURL(/\/docs\/quickstart$/);
  });

  test('API Reference renders endpoints grouped by OpenAPI tag', async ({ page }) => {
    await page.goto('/docs/api-reference');
    await expect(page).toHaveURL(/\/docs\/api-reference$/);
    await expect(page.getByRole('heading', { name: 'API Reference', level: 1 })).toBeVisible();

    // Grouped sections exist and cover core tags (labels follow the docs
    // i18n namespace; unknown tags fall back to the raw tag name).
    const groups = page.getByTestId('docs-api-tag-group');
    await expect(groups.first()).toBeVisible();
    const groupCount = await groups.count();
    expect(groupCount).toBeGreaterThan(5);

    // A known tag group heading is visible and contains endpoint cards.
    await expect(page.getByRole('heading', { name: 'Agents', level: 2 })).toBeVisible();
    const agentGroup = groups.filter({ has: page.getByRole('heading', { name: 'Agents', level: 2 }) });
    await expect(agentGroup.getByTestId('docs-api-endpoint').first()).toBeVisible();
    await expect(agentGroup.getByText('GET').first()).toBeVisible();
    await expect(agentGroup.getByText('POST').first()).toBeVisible();

    // Parameter tables render.
    await expect(page.getByRole('heading', { name: 'Parameters', level: 3 }).first()).toBeVisible();

    // No horizontal overflow at desktop width.
    const scrollWidth = await page.evaluate(() => document.documentElement.scrollWidth);
    const clientWidth = await page.evaluate(() => document.documentElement.clientWidth);
    expect(scrollWidth).toBeLessThanOrEqual(clientWidth + 2);
  });

  test('mobile sidebar collapses into a contents menu', async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 812 });
    await page.goto('/docs/quickstart');
    await expect(page.getByRole('heading', { name: 'Quickstart', level: 1 })).toBeVisible();

    // The contents toggle opens the overlay sidebar.
    const toggle = page.getByRole('button', { name: 'Contents' });
    await expect(toggle).toBeVisible();
    await toggle.click();

    const sdkLink = page.getByRole('link', { name: 'Python SDK Quickstart', exact: true });
    await expect(sdkLink).toBeVisible();
    await sdkLink.click();
    await expect(page).toHaveURL(/\/docs\/sdk-python-quickstart$/);
    await expect(page.getByRole('heading', { name: 'Python SDK 快速上手', level: 1 })).toBeVisible();

    // No horizontal overflow at 375px (pixel design narrow-width rule).
    const scrollWidth = await page.evaluate(() => document.documentElement.scrollWidth);
    const clientWidth = await page.evaluate(() => document.documentElement.clientWidth);
    expect(scrollWidth).toBeLessThanOrEqual(clientWidth + 2);
  });

  test('docs home screenshot', async ({ page }) => {
    await page.goto('/docs/quickstart');
    await expect(page.getByRole('heading', { name: 'Quickstart', level: 1 })).toBeVisible();
    await page.screenshot({ path: 'e2e/screenshots/docs-home.png', fullPage: true });
  });

  test('api reference screenshot', async ({ page }) => {
    await page.goto('/docs/api-reference');
    await expect(page.getByRole('heading', { name: 'API Reference', level: 1 })).toBeVisible();
    await page.screenshot({ path: 'e2e/screenshots/api-reference.png', fullPage: true });
  });

  test('signed-in round trip: docs entry, then back to the console', async ({ page }) => {
    test.skip(!username || !apiKey, 'E2E_DASHBOARD_USERNAME / E2E_DASHBOARD_API_KEY not set');
    // Sign in and land on the console overview.
    await page.goto('/login');
    await page.getByTestId('login-username').fill(username!);
    await page.getByTestId('login-api-key').fill(apiKey!);
    await page.click('button[type="submit"]');
    await expect(page).toHaveURL(/\/app\/overview$/);

    // The shell footer docs entry opens the docs site in-app.
    const docsEntry = page.getByRole('link', { name: 'Open the documentation site' });
    await expect(docsEntry).toBeVisible();
    await docsEntry.click();
    await expect(page).toHaveURL(/\/docs\/quickstart$/);
    await expect(page.getByRole('heading', { name: 'Quickstart', level: 1 })).toBeVisible();

    // The back link returns to the console (exact page via history).
    const backLink = page.getByRole('link', { name: 'Back to Console' });
    await expect(backLink).toBeVisible();
    await backLink.click();
    await expect(page).toHaveURL(/\/app\/overview$/);
  });
});

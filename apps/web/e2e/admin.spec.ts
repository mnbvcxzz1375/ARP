import { test, expect } from '@playwright/test';

test.describe('Admin page access control', () => {
  test('admin pages redirect to login when unauthenticated', async ({ page }) => {
    await page.goto('/admin/overview');
    // /admin/* aliases redirect into /enterprise/*, whose guard (fail-closed
    // on /me.permissions) sends unauthenticated visitors to /login carrying
    // the destination path in `next` (deep-link contract, e2e/deep-link.spec.ts).
    await expect(page).toHaveURL(/\/login(\?|$)/);
  });

  test('system health page redirects when unauthenticated', async ({ page }) => {
    await page.goto('/admin/system');
    await expect(page).toHaveURL(/\/login(\?|$)/);
  });
});

import { test, expect } from '@playwright/test';

test.describe('Admin page access control', () => {
  test('admin pages redirect to login when unauthenticated', async ({ page }) => {
    await page.goto('/admin/overview');
    await expect(page).toHaveURL(/\/login$/);
  });

  test('system health page redirects when unauthenticated', async ({ page }) => {
    await page.goto('/admin/system');
    await expect(page).toHaveURL(/\/login$/);
  });
});

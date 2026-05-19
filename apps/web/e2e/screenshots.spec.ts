import { test, expect } from '@playwright/test';

test.describe('Page screenshots (production build)', () => {
  test('login page screenshot', async ({ page }) => {
    await page.goto('/login');
    await expect(page.getByText('AgentNet')).toBeVisible();
    await page.screenshot({ path: 'e2e/screenshots/login-page.png', fullPage: true });
  });

  test('login page mobile screenshot', async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 812 });
    await page.goto('/login');
    await page.screenshot({ path: 'e2e/screenshots/login-page-mobile.png', fullPage: true });
  });
});

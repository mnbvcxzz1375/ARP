import { test, expect } from '@playwright/test';

test.describe('Dashboard smoke tests', () => {
  test('login page loads', async ({ page }) => {
    await page.goto('/login');
    await expect(page.getByText('AgentNet')).toBeVisible();
    await expect(page.getByText('Sign in to your dashboard')).toBeVisible();
  });

  test('unauthenticated redirects to login', async ({ page }) => {
    await page.goto('/app/overview');
    await page.waitForURL('**/login');
    await expect(page.getByText('Sign in')).toBeVisible();
  });

  test('app routing works', async ({ page }) => {
    await page.goto('/');
    await page.waitForURL('**/login');
    // App redirects /* to /app/overview, which redirects to /login if unauth
    const url = page.url();
    expect(url).toContain('login');
  });
});

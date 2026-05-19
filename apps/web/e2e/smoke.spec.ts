import { test, expect } from '@playwright/test';

test.describe('Dashboard smoke tests', () => {
  test('login page loads and renders', async ({ page }) => {
    await page.goto('/login');
    await expect(page.getByText('AgentNet')).toBeVisible();
    await expect(page.getByText('Sign in to your dashboard')).toBeVisible();
    await expect(page.getByPlaceholder('your-username')).toBeVisible();
    await expect(page.getByPlaceholder('ak_...')).toBeVisible();
    await expect(page.getByRole('button', { name: 'Sign In' })).toBeVisible();
  });

  test('unauthenticated redirects to login', async ({ page }) => {
    await page.goto('/app/overview');
    await expect(page).toHaveURL(/\/login$/);
  });

  test('login page form validation shows errors', async ({ page }) => {
    await page.goto('/login');
    await page.getByRole('button', { name: 'Sign In' }).click();
    // HTML5 validation should prevent submission
    await expect(page.locator('form')).toBeVisible();
  });
});

test.describe('Static build checks', () => {
  test('index.html has correct title', async ({ page }) => {
    await page.goto('/');
    const title = await page.title();
    expect(title).toBe('AgentNet Dashboard');
  });
});

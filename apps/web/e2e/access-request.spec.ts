import { test, expect } from '@playwright/test';

test.describe('Public access request flow', () => {
  test('public home page shows access paths', async ({ page }) => {
    await page.goto('/');
    await expect(page.getByText('Sign In')).toBeVisible();
    await expect(page.getByText('Request Personal Access')).toBeVisible();
    await expect(page.getByText('Request Enterprise Access')).toBeVisible();
  });

  test('request access page loads with form fields', async ({ page }) => {
    await page.goto('/request-access');
    await expect(page.getByText('Request Access')).toBeVisible();
    await expect(page.getByLabel('Name')).toBeVisible();
    await expect(page.getByLabel('Email')).toBeVisible();
    await expect(page.getByLabel('Use Case')).toBeVisible();
  });

  test('request access page pre-selects enterprise mode from URL', async ({ page }) => {
    await page.goto('/request-access?mode=enterprise');
    const enterpriseBtn = page.getByText('Enterprise');
    await expect(enterpriseBtn).toBeVisible();
  });

  test('login page has link to request access', async ({ page }) => {
    await page.goto('/login');
    await expect(page.getByText(/need access/i)).toBeVisible();
  });

  test('submitted page without valid state shows unable to confirm', async ({ page }) => {
    await page.goto('/request-access/submitted?request_id=test-123');
    await expect(page.getByText('Unable to Confirm Access Request')).toBeVisible();
    await expect(page.getByText('Return to Request Form')).toBeVisible();
    await expect(page.getByText('Request Submitted')).not.toBeVisible();
  });
});

test.describe('No emoji in UI', () => {
  test('public pages have no emoji', async ({ page }) => {
    await page.goto('/');
    const body = await page.textContent('body');
    const emojiRegex = /[\u{1F300}-\u{1F9FF}\u{2600}-\u{26FF}\u{2700}-\u{27BF}]/u;
    expect(emojiRegex.test(body || '')).toBe(false);
  });

  test('login page has no emoji', async ({ page }) => {
    await page.goto('/login');
    const body = await page.textContent('body');
    const emojiRegex = /[\u{1F300}-\u{1F9FF}\u{2600}-\u{26FF}\u{2700}-\u{27BF}]/u;
    expect(emojiRegex.test(body || '')).toBe(false);
  });
});

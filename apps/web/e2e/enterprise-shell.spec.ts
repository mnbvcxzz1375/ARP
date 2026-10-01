import { test, expect } from '@playwright/test';

test.describe('Enterprise console routes', () => {
  test('enterprise pages redirect to login when unauthenticated', async ({ page }) => {
    await page.goto('/enterprise/overview');
    await expect(page).toHaveURL(/\/login(\?|$)/);
  });

  test('enterprise relay-nodes redirects when unauthenticated', async ({ page }) => {
    await page.goto('/enterprise/relay-nodes');
    await expect(page).toHaveURL(/\/login(\?|$)/);
  });

  test('enterprise route-policies redirects when unauthenticated', async ({ page }) => {
    await page.goto('/enterprise/route-policies');
    await expect(page).toHaveURL(/\/login(\?|$)/);
  });

  test('enterprise egress redirects when unauthenticated', async ({ page }) => {
    await page.goto('/enterprise/egress');
    await expect(page).toHaveURL(/\/login(\?|$)/);
  });

  test('enterprise sla redirects when unauthenticated', async ({ page }) => {
    await page.goto('/enterprise/sla');
    await expect(page).toHaveURL(/\/login(\?|$)/);
  });

  test('enterprise access-requests redirects when unauthenticated', async ({ page }) => {
    await page.goto('/enterprise/access-requests');
    await expect(page).toHaveURL(/\/login(\?|$)/);
  });
});

test.describe('Personal console routes', () => {
  test('personal overview redirects when unauthenticated', async ({ page }) => {
    await page.goto('/app/overview');
    await expect(page).toHaveURL(/\/login(\?|$)/);
  });

  test('personal routing redirects when unauthenticated', async ({ page }) => {
    await page.goto('/app/routing');
    await expect(page).toHaveURL(/\/login(\?|$)/);
  });
});

test.describe('Public pages', () => {
  test('root redirects to public home', async ({ page }) => {
    await page.goto('/');
    await expect(page.getByText('AgentNet')).toBeVisible();
  });

  test('request access page renders form', async ({ page }) => {
    await page.goto('/request-access');
    await expect(page.getByText('Request Access')).toBeVisible();
    await expect(page.getByLabel('Name')).toBeVisible();
    await expect(page.getByLabel('Email')).toBeVisible();
  });

  test('request access submitted page without state shows unable to confirm', async ({ page }) => {
    await page.goto('/request-access/submitted?request_id=ar-test');
    await expect(page.getByText('Unable to Confirm Access Request')).toBeVisible();
    await expect(page.getByText('Return to Request Form')).toBeVisible();
    await expect(page.getByText('Request Submitted')).not.toBeVisible();
  });
});

test.describe('No emoji in any public page', () => {
  const emojiRegex = /[\u{1F300}-\u{1F9FF}\u{2600}-\u{26FF}\u{2700}-\u{27BF}]/u;

  test('home page has no emoji', async ({ page }) => {
    await page.goto('/');
    const body = await page.textContent('body');
    expect(emojiRegex.test(body || '')).toBe(false);
  });

  test('login page has no emoji', async ({ page }) => {
    await page.goto('/login');
    const body = await page.textContent('body');
    expect(emojiRegex.test(body || '')).toBe(false);
  });

  test('request access page has no emoji', async ({ page }) => {
    await page.goto('/request-access');
    const body = await page.textContent('body');
    expect(emojiRegex.test(body || '')).toBe(false);
  });

  test('submitted page has no emoji', async ({ page }) => {
    await page.goto('/request-access/submitted?request_id=test');
    const body = await page.textContent('body');
    expect(emojiRegex.test(body || '')).toBe(false);
  });
});
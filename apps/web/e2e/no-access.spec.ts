import { test, expect } from '@playwright/test';

/**
 * Regression: an authenticated session whose /me.permissions lack the
 * global-scope entries the enterprise console requires must land on the
 * public no-access page. Sending such a session to /login?next=... loops,
 * because PublicLayout bounces an authenticated visitor straight back to
 * `next`.
 */
const LIMITED_ME = {
  user_id: '00000000-0000-0000-0000-000000000002',
  username: 'limited_user',
  role: 'user',
  permissions: ['agent:read:own', 'task:read:own'],
  csrf_required: true,
  session_expires_at: '2030-01-01T00:00:00+00:00',
  step_up_until: null,
};

test('authenticated without global permissions lands on /no-access', async ({ page }) => {
  await page.route('**/v1/dashboard/auth/me', (route) =>
    route.fulfill({ json: LIMITED_ME }),
  );

  await page.goto('/enterprise/overview');
  await expect(page).toHaveURL(/\/no-access$/);
  await expect(page.getByRole('heading', { name: 'No Access', level: 1 })).toBeVisible();

  // The legacy alias must behave the same way (not a login loop).
  await page.goto('/admin/users');
  await expect(page).toHaveURL(/\/no-access$/);
});

test('authenticated with no permissions at all also lands on /no-access', async ({ page }) => {
  await page.route('**/v1/dashboard/auth/me', (route) =>
    route.fulfill({ json: { ...LIMITED_ME, permissions: [] } }),
  );

  await page.goto('/app/overview');
  await expect(page).toHaveURL(/\/no-access$/);
});

import { test, expect } from '@playwright/test';

/**
 * The console sidebar is drag/keyboard resizable when expanded (the pixel
 * design system ships a 10px strip centered on the sidebar's right
 * border). Keyboard: focus + ArrowLeft/ArrowRight. The width persists in
 * localStorage and survives reload.
 */
const username = process.env.E2E_DASHBOARD_USERNAME;
const apiKey = process.env.E2E_DASHBOARD_API_KEY;

test.describe('sidebar resize', () => {
  test.skip(!username || !apiKey, 'E2E_DASHBOARD_USERNAME / E2E_DASHBOARD_API_KEY not set');

  test.beforeEach(async ({ page }) => {
    await page.addInitScript(() => localStorage.removeItem('agentnet.sidebarWidth'));
    await page.goto('/login');
    await page.getByTestId('login-username').fill(username!);
    await page.getByTestId('login-api-key').fill(apiKey!);
    await page.click('button[type="submit"]');
    await expect(page).toHaveURL(/\/app\/overview/);
  });

  test('arrow keys widen and narrow the sidebar and persist across reload', async ({ page }) => {
    const handle = page.getByRole('separator', { name: 'Resize sidebar width' });
    await expect(handle).toBeVisible();

    const width = async () => (await handle.getAttribute('aria-valuenow')) ?? '';
    await expect.poll(width).toBe('168'); // archipelago overview default

    // Widen twice (16px each), narrow once: 168 + 16 = 184 + 16 = 200 - 16 = 184.
    await handle.focus();
    await page.keyboard.press('ArrowRight');
    await expect.poll(width).toBe('184');
    await page.keyboard.press('ArrowRight');
    await expect.poll(width).toBe('200');
    await page.keyboard.press('ArrowLeft');
    await expect.poll(width).toBe('184');

    // Clamped at the floor: default minus one step below the minimum.
    await page.keyboard.press('ArrowLeft');
    await page.keyboard.press('ArrowLeft');
    await page.keyboard.press('ArrowLeft');
    await expect.poll(width).toBe('168');

    // Persisted: reload restores the clamped width without dragging again.
    await page.reload();
    await expect(page.getByRole('separator', { name: 'Resize sidebar width' })).toBeVisible();
    await expect
      .poll(async () => (await handle.getAttribute('aria-valuenow')) ?? '')
      .toBe('168');
  });

  test('dragging the handle changes the sidebar column width', async ({ page }) => {
    const handle = page.getByRole('separator', { name: 'Resize sidebar width' });
    await expect(handle).toBeVisible();

    // The grid's first column follows --shell-sidebar-w, which the drag
    // updates: press at the handle, drag to clientX=300, release.
    const box = (await handle.boundingBox())!;
    const y = box.y + box.height / 2;
    await page.mouse.move(box.x + 5, y);
    await page.mouse.down();
    await page.mouse.move(300, y, { steps: 8 });
    await page.mouse.up();

    await expect
      .poll(async () => (await handle.getAttribute('aria-valuenow')) ?? '')
      .toBe('300');
  });
});

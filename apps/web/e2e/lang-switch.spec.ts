import { test, expect } from '@playwright/test';

/**
 * Language switch e2e (pixel LanguageSwitcher on the public surface).
 *
 * Flow: English login page -> switch to Chinese via the segmented chip ->
 * Chinese copy appears ("登录") and persists across reload -> switch back
 * to English and the copy recovers. Verifies the localStorage key, the
 * <html lang> attribute, and produces both login screenshots.
 *
 * Screenshot paths are relative to the playwright config root (apps/web),
 * matching the convention in e2e/screenshots.spec.ts.
 */
const EN_SCREENSHOT = 'e2e/screenshots/lang-en-login.png';
const ZH_SCREENSHOT = 'e2e/screenshots/lang-zh-login.png';

test('switching locale on the login page round-trips and persists', async ({ page }) => {
  await page.goto('/login');

  // English (default) state.
  await expect(page.getByRole('button', { name: 'Sign In', exact: true })).toBeVisible();
  await expect(page.locator('html')).toHaveAttribute('lang', 'en');
  await page.screenshot({ path: EN_SCREENSHOT, fullPage: true });

  // Switch to Chinese via the segmented chip.
  await page.getByTestId('language-option-zh').click();

  // Chinese copy replaces the English strings.
  await expect(page.getByRole('button', { name: '登录' })).toBeVisible();
  await expect(page.getByText('登录到控制台')).toBeVisible();

  // Persistence contract: localStorage + <html lang>.
  await expect(page.locator('html')).toHaveAttribute('lang', 'zh');
  const stored = await page.evaluate(() => window.localStorage.getItem('agentnet-locale'));
  expect(stored).toBe('zh');

  await page.screenshot({ path: ZH_SCREENSHOT, fullPage: true });

  // Persistence survives a full reload (no backend preference set).
  await page.reload();
  await expect(page.getByRole('button', { name: '登录' })).toBeVisible();
  await expect(page.locator('html')).toHaveAttribute('lang', 'zh');

  // Switch back to English.
  await page.getByTestId('language-option-en').click();
  await expect(page.getByRole('button', { name: 'Sign In', exact: true })).toBeVisible();
  await expect(page.locator('html')).toHaveAttribute('lang', 'en');
});

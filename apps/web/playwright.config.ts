import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './e2e',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: 'html',
  use: {
    baseURL: process.env.BASE_URL || 'http://localhost:5173',
    // The suite asserts English copy throughout; pin the context locale so
    // the app resolves 'en' deterministically regardless of the host
    // browser/OS language (a zh-CN host would otherwise render zh and break
    // every English assertion).
    locale: 'en-US',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
  },
  projects: [
    { name: 'chromium', use: { ...devices['Desktop Chrome'] } },
  ],
  webServer: process.env.CI ? {
    command: 'npm run build && npx vite preview --port 4173',
    port: 4173,
    cwd: 'apps/web',
    reuseExistingServer: true,
  } : undefined,
});

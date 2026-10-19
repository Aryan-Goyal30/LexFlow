import { defineConfig, devices } from '@playwright/test';
import { API_PORT, APP_PORT } from './e2e/support/backend';

/**
 * End-to-end tests: a real browser, the Vite dev server, the real API and a real
 * PostgreSQL database. Global setup recreates a separate `lexflow_e2e` database
 * with the sample data and starts the API on 127.0.0.1:8001; Vite (port 5174)
 * forwards /api there. The development database is never touched.
 *
 *   npm run e2e
 */
export default defineConfig({
  testDir: 'e2e',
  // The tests share one database and one API process, which a test restarts.
  workers: 1,
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: 0,
  reporter: process.env.CI ? [['list'], ['html', { open: 'never' }]] : 'list',
  globalSetup: './e2e/global-setup.ts',
  globalTeardown: './e2e/global-teardown.ts',
  use: {
    baseURL: `http://localhost:${APP_PORT}`,
    trace: 'retain-on-failure',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  webServer: {
    command: `npx vite --port ${APP_PORT} --strictPort`,
    url: `http://localhost:${APP_PORT}`,
    reuseExistingServer: false,
    timeout: 60_000,
    env: {
      LEXFLOW_API_PROXY_TARGET: `http://127.0.0.1:${API_PORT}`,
      BROWSER: 'none', // don't open a browser window
    },
  },
});

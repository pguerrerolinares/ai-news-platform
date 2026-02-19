import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './e2e',
  timeout: 20_000,
  expect: {
    timeout: 5_000,
    toHaveScreenshot: { maxDiffPixels: 50, threshold: 0.05 },
  },
  fullyParallel: false,
  retries: 0,
  reporter: [['list'], ['html', { open: 'never', outputFolder: 'playwright-report' }]],
  use: {
    baseURL: 'http://localhost:4200',
    screenshot: 'only-on-failure',
    trace: 'on-first-retry',
  },
  projects: [
    // Functional tests (existing)
    { name: 'chromium', testMatch: /.*\.spec\.ts/, testIgnore: /visual-|screenshot-docs/, use: { ...devices['Desktop Chrome'] } },
    // Screenshot docs — standalone project (viewports defined in spec)
    { name: 'screendocs', testMatch: /screenshot-docs\.spec\.ts/, use: { ...devices['Desktop Chrome'] } },
    // Visual regression — desktop dark
    {
      name: 'desktop-dark',
      testMatch: /visual-.*\.spec\.ts/,
      use: { ...devices['Desktop Chrome'], viewport: { width: 1280, height: 800 } },
    },
    // Visual regression — desktop light
    {
      name: 'desktop-light',
      testMatch: /visual-.*\.spec\.ts/,
      use: { ...devices['Desktop Chrome'], viewport: { width: 1280, height: 800 } },
    },
    // Visual regression — mobile dark
    {
      name: 'mobile',
      testMatch: /visual-.*\.spec\.ts/,
      use: { ...devices['Pixel 5'] },
    },
  ],
  webServer: {
    command: 'npm run mock',
    url: 'http://localhost:4200',
    reuseExistingServer: true,
    timeout: 60_000,
  },
});

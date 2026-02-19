/**
 * screenshot-docs.spec.ts
 *
 * Genera screenshots de diseño para documentación visual.
 * No hace comparación (no usa toHaveScreenshot) — solo guarda PNGs.
 *
 * Ejecutar: npm run e2e:screendocs
 * Output:   docs/screenshots/{pages,components,mobile}/
 */
import * as path from 'path';
import { test } from '@playwright/test';
import { authenticateWithTheme } from './helpers/auth';
import { freezeAnimations } from './helpers/freeze-animations';

const DOCS_DIR = path.join(__dirname, '..', '..', 'docs', 'screenshots');

async function shot(page: import('@playwright/test').Page, subfolder: string, name: string) {
  await page.screenshot({
    path: path.join(DOCS_DIR, subfolder, `${name}.png`),
    fullPage: false,
  });
}

async function shotFull(page: import('@playwright/test').Page, subfolder: string, name: string) {
  await page.screenshot({
    path: path.join(DOCS_DIR, subfolder, `${name}.png`),
    fullPage: true,
  });
}

// === DESKTOP DARK ===
test.describe('Docs — Desktop Dark', () => {
  test.use({ viewport: { width: 1280, height: 800 } });

  test.beforeEach(async ({ page }) => {
    await authenticateWithTheme(page, 'dark');
  });

  test('pages', async ({ page }) => {
    // Dashboard
    await page.goto('/dashboard');
    await page.waitForSelector('.stats-bar');
    await page.waitForSelector('app-news-item-card');
    await freezeAnimations(page);
    await shotFull(page, 'pages', 'dashboard-dark');

    // Archive
    await page.goto('/archive');
    await page.waitForSelector('.stats-bar', { timeout: 8000 });
    await freezeAnimations(page);
    await shotFull(page, 'pages', 'archive-dark');

    // Search empty
    await page.goto('/search');
    await page.waitForSelector('.search-empty-state');
    await freezeAnimations(page);
    await shotFull(page, 'pages', 'search-empty-dark');

    // Search results
    await page.locator('input[name="query"]').fill('LLM');
    await page.getByRole('button', { name: 'Buscar' }).click();
    await page.waitForSelector('app-news-item-card', { timeout: 5000 });
    await page.waitForLoadState('networkidle');
    await freezeAnimations(page);
    await shotFull(page, 'pages', 'search-results-dark');

    // Analytics
    await page.goto('/analytics');
    await page.waitForSelector('highcharts-chart svg', { timeout: 10000 });
    await page.waitForSelector('highcharts-chart svg .highcharts-series-group', { timeout: 10000 });
    await freezeAnimations(page);
    await shotFull(page, 'pages', 'analytics-dark');

    // Chat
    await page.goto('/chat');
    await page.waitForSelector('.empty-state');
    await freezeAnimations(page);
    await shotFull(page, 'pages', 'chat-dark');
  });

  test('components', async ({ page }) => {
    // Navbar
    await page.goto('/dashboard');
    await page.waitForSelector('.navbar');
    await freezeAnimations(page);
    await shot(page, 'components', 'navbar-dark');

    // Stats bar
    await page.waitForSelector('.stats-bar');
    await shot(page, 'components', 'stats-bar-dark');

    // News card
    await page.waitForSelector('app-news-item-card');
    await shot(page, 'components', 'news-card-dark');

    // mat-select abierto
    await page.goto('/chat');
    await page.waitForSelector('mat-select');
    await freezeAnimations(page);
    await page.locator('mat-select').first().click();
    await page.waitForSelector('.mat-mdc-select-panel', { timeout: 3000 });
    await page.locator('.mat-mdc-select-panel').screenshot({
      path: path.join(DOCS_DIR, 'components', 'mat-select-open-dark.png'),
    });
    await page.keyboard.press('Escape');

    // mat-datepicker abierto
    await page.goto('/archive');
    await page.waitForSelector('.stats-bar', { timeout: 8000 });
    await freezeAnimations(page);
    await page.locator('mat-datepicker-toggle button').first().click();
    await page.waitForSelector('.mat-datepicker-content', { timeout: 3000 });
    await shot(page, 'components', 'mat-datepicker-open-dark');
    await page.keyboard.press('Escape');

    // Suggestion chips
    await page.goto('/chat');
    await page.waitForSelector('.suggestions');
    await freezeAnimations(page);
    await page.locator('.suggestions').screenshot({
      path: path.join(DOCS_DIR, 'components', 'suggestion-chips-dark.png'),
    });
  });
});

// === DESKTOP LIGHT ===
test.describe('Docs — Desktop Light', () => {
  test.use({ viewport: { width: 1280, height: 800 } });

  test.beforeEach(async ({ page }) => {
    await authenticateWithTheme(page, 'light');
  });

  test('pages', async ({ page }) => {
    await page.goto('/dashboard');
    await page.waitForSelector('.stats-bar');
    await page.waitForSelector('app-news-item-card');
    await freezeAnimations(page);
    await shotFull(page, 'pages', 'dashboard-light');

    await page.goto('/archive');
    await page.waitForSelector('.stats-bar', { timeout: 8000 });
    await freezeAnimations(page);
    await shotFull(page, 'pages', 'archive-light');

    await page.goto('/search');
    await page.waitForSelector('.search-empty-state');
    await freezeAnimations(page);
    await shotFull(page, 'pages', 'search-empty-light');

    await page.goto('/analytics');
    await page.waitForSelector('highcharts-chart svg', { timeout: 10000 });
    await page.waitForSelector('highcharts-chart svg .highcharts-series-group', { timeout: 10000 });
    await freezeAnimations(page);
    await shotFull(page, 'pages', 'analytics-light');

    await page.goto('/chat');
    await page.waitForSelector('.empty-state');
    await freezeAnimations(page);
    await shotFull(page, 'pages', 'chat-light');
  });

  test('components', async ({ page }) => {
    await page.goto('/dashboard');
    await page.waitForSelector('.navbar');
    await freezeAnimations(page);
    await shot(page, 'components', 'navbar-light');

    await page.waitForSelector('.stats-bar');
    await shot(page, 'components', 'stats-bar-light');

    await page.waitForSelector('app-news-item-card');
    await shot(page, 'components', 'news-card-light');

    await page.goto('/chat');
    await page.waitForSelector('mat-select');
    await freezeAnimations(page);
    await page.locator('mat-select').first().click();
    await page.waitForSelector('.mat-mdc-select-panel', { timeout: 3000 });
    await page.locator('.mat-mdc-select-panel').screenshot({
      path: path.join(DOCS_DIR, 'components', 'mat-select-open-light.png'),
    });
    await page.keyboard.press('Escape');

    await page.goto('/archive');
    await page.waitForSelector('.stats-bar', { timeout: 8000 });
    await freezeAnimations(page);
    await page.locator('mat-datepicker-toggle button').first().click();
    await page.waitForSelector('.mat-datepicker-content', { timeout: 3000 });
    await shot(page, 'components', 'mat-datepicker-open-light');
    await page.keyboard.press('Escape');

    await page.goto('/chat');
    await page.waitForSelector('.suggestions');
    await freezeAnimations(page);
    await page.locator('.suggestions').screenshot({
      path: path.join(DOCS_DIR, 'components', 'suggestion-chips-light.png'),
    });
  });
});

// === MOBILE (390px) ===
test.describe('Docs — Mobile Dark', () => {
  test.use({ viewport: { width: 390, height: 844 } });

  test.beforeEach(async ({ page }) => {
    await authenticateWithTheme(page, 'dark');
  });

  test('pages', async ({ page }) => {
    await page.goto('/dashboard');
    await page.waitForSelector('.stats-bar');
    await page.waitForSelector('app-news-item-card');
    await freezeAnimations(page);
    await shotFull(page, 'mobile', 'dashboard-dark');

    await page.goto('/archive');
    await page.waitForSelector('.stats-bar', { timeout: 8000 });
    await freezeAnimations(page);
    await shotFull(page, 'mobile', 'archive-dark');

    await page.goto('/search');
    await page.waitForSelector('.search-empty-state');
    await freezeAnimations(page);
    await shotFull(page, 'mobile', 'search-dark');

    await page.goto('/analytics');
    await page.waitForSelector('highcharts-chart svg', { timeout: 10000 });
    await page.waitForSelector('highcharts-chart svg .highcharts-series-group', { timeout: 10000 });
    await freezeAnimations(page);
    await shotFull(page, 'mobile', 'analytics-dark');

    await page.goto('/chat');
    await page.waitForSelector('.empty-state');
    await freezeAnimations(page);
    await shotFull(page, 'mobile', 'chat-dark');
  });

  test('mobile menu abierto', async ({ page }) => {
    await page.goto('/dashboard');
    await page.waitForSelector('.hamburger');
    await freezeAnimations(page);
    await page.locator('.hamburger').click();
    await page.waitForSelector('.nav-links.open', { timeout: 2000 });
    await shot(page, 'mobile', 'navbar-menu-open');
  });
});

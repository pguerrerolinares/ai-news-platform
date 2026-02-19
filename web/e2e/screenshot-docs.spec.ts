/**
 * screenshot-docs.spec.ts
 *
 * Genera screenshots de diseño para documentación visual.
 * No hace comparación (no usa toHaveScreenshot) — solo guarda PNGs.
 *
 * Cobertura completa: desktop dark/light + mobile dark/light
 * para pages y components con manejo correcto de scroll.
 *
 * Ejecutar: npm run e2e:screendocs
 * Output:   docs/screenshots/{pages,components,mobile}/
 */
import * as path from 'path';
import { test, Page } from '@playwright/test';
import { authenticateWithTheme } from './helpers/auth';
import { freezeAnimations } from './helpers/freeze-animations';

const DOCS_DIR = path.join(__dirname, '..', '..', 'docs', 'screenshots');

async function shot(page: Page, subfolder: string, name: string) {
  await page.screenshot({
    path: path.join(DOCS_DIR, subfolder, `${name}.png`),
    fullPage: false,
  });
}

async function shotFull(page: Page, subfolder: string, name: string) {
  await page.screenshot({
    path: path.join(DOCS_DIR, subfolder, `${name}.png`),
    fullPage: true,
  });
}

/** Scroll al fondo para forzar render de elementos lazy, luego volver arriba */
async function ensureFullRender(page: Page): Promise<void> {
  await page.evaluate(async () => {
    const delay = (ms: number) => new Promise(r => setTimeout(r, ms));
    const body = document.body;
    const step = Math.max(window.innerHeight / 2, 300);
    for (let y = 0; y < body.scrollHeight; y += step) {
      window.scrollTo(0, y);
      await delay(100);
    }
    window.scrollTo(0, 0);
    await delay(150);
  });
}

/** Captura un elemento concreto haciendo scroll a él primero */
async function shotElement(
  page: Page,
  selector: string,
  subfolder: string,
  name: string,
): Promise<void> {
  const el = page.locator(selector).first();
  await el.scrollIntoViewIfNeeded();
  await el.screenshot({
    path: path.join(DOCS_DIR, subfolder, `${name}.png`),
  });
}

// ─────────────────────────────────────────────
// Shared test sequences to avoid duplication
// ─────────────────────────────────────────────

async function capturePages(
  page: Page,
  subfolder: string,
  suffix: string,
) {
  // Dashboard
  await page.goto('/dashboard');
  await page.waitForSelector('.stats-bar');
  await page.waitForSelector('app-news-item-card');
  await freezeAnimations(page);
  await ensureFullRender(page);
  await shotFull(page, subfolder, `dashboard-${suffix}`);

  // Archive
  await page.goto('/archive');
  await page.waitForSelector('.stats-bar', { timeout: 8000 });
  await page.waitForSelector('app-news-item-card');
  await freezeAnimations(page);
  await ensureFullRender(page);
  await shotFull(page, subfolder, `archive-${suffix}`);

  // Search empty
  await page.goto('/search');
  await page.waitForSelector('.search-empty-state');
  await freezeAnimations(page);
  await shotFull(page, subfolder, `search-empty-${suffix}`);

  // Search results
  await page.locator('input[name="query"]').fill('LLM');
  await page.getByRole('button', { name: 'Buscar' }).click();
  await page.waitForSelector('app-news-item-card', { timeout: 5000 });
  await page.waitForLoadState('networkidle');
  await freezeAnimations(page);
  await ensureFullRender(page);
  await shotFull(page, subfolder, `search-results-${suffix}`);

  // Analytics
  await page.goto('/analytics');
  await page.waitForSelector('highcharts-chart svg', { timeout: 10000 });
  await page.waitForSelector('highcharts-chart svg .highcharts-series-group', { timeout: 10000 });
  await freezeAnimations(page);
  await ensureFullRender(page);
  await shotFull(page, subfolder, `analytics-${suffix}`);

  // Chat
  await page.goto('/chat');
  await page.waitForSelector('.empty-state');
  await freezeAnimations(page);
  await shotFull(page, subfolder, `chat-${suffix}`);
}

async function captureComponents(
  page: Page,
  subfolder: string,
  suffix: string,
) {
  // Navbar
  await page.goto('/dashboard');
  await page.waitForSelector('.navbar');
  await freezeAnimations(page);
  await shotElement(page, '.navbar', subfolder, `navbar-${suffix}`);

  // Stats bar
  await page.waitForSelector('.stats-bar');
  await shotElement(page, '.stats-bar', subfolder, `stats-bar-${suffix}`);

  // News card
  await page.waitForSelector('app-news-item-card');
  await shotElement(page, 'app-news-item-card', subfolder, `news-card-${suffix}`);

  // mat-select abierto
  await page.goto('/chat');
  await page.waitForSelector('mat-select');
  await freezeAnimations(page);
  await page.locator('mat-select').first().click();
  await page.waitForSelector('.mat-mdc-select-panel', { timeout: 3000 });
  await page.locator('.mat-mdc-select-panel').screenshot({
    path: path.join(DOCS_DIR, subfolder, `mat-select-open-${suffix}.png`),
  });
  await page.keyboard.press('Escape');

  // mat-datepicker abierto
  await page.goto('/archive');
  await page.waitForSelector('.stats-bar', { timeout: 8000 });
  await freezeAnimations(page);
  await page.locator('mat-datepicker-toggle button').first().click();
  await page.waitForSelector('.mat-datepicker-content', { timeout: 3000 });
  await shot(page, subfolder, `mat-datepicker-open-${suffix}`);
  await page.keyboard.press('Escape');

  // Suggestion chips
  await page.goto('/chat');
  await page.waitForSelector('.suggestions');
  await freezeAnimations(page);
  await page.locator('.suggestions').screenshot({
    path: path.join(DOCS_DIR, subfolder, `suggestion-chips-${suffix}.png`),
  });
}

// ─────────────────────────────────────────────
// DESKTOP DARK
// ─────────────────────────────────────────────
test.describe('Docs — Desktop Dark', () => {
  test.use({ viewport: { width: 1280, height: 800 } });

  test.beforeEach(async ({ page }) => {
    await authenticateWithTheme(page, 'dark');
  });

  test('pages', async ({ page }) => {
    await capturePages(page, 'pages', 'dark');
  });

  test('components', async ({ page }) => {
    await captureComponents(page, 'components', 'dark');
  });
});

// ─────────────────────────────────────────────
// DESKTOP LIGHT
// ─────────────────────────────────────────────
test.describe('Docs — Desktop Light', () => {
  test.use({ viewport: { width: 1280, height: 800 } });

  test.beforeEach(async ({ page }) => {
    await authenticateWithTheme(page, 'light');
  });

  test('pages', async ({ page }) => {
    await capturePages(page, 'pages', 'light');
  });

  test('components', async ({ page }) => {
    await captureComponents(page, 'components', 'light');
  });
});

// ─────────────────────────────────────────────
// MOBILE DARK (390x844)
// ─────────────────────────────────────────────
test.describe('Docs — Mobile Dark', () => {
  test.use({ viewport: { width: 390, height: 844 } });

  test.beforeEach(async ({ page }) => {
    await authenticateWithTheme(page, 'dark');
  });

  test('pages', async ({ page }) => {
    await capturePages(page, 'mobile', 'dark');
  });

  test('components', async ({ page }) => {
    await captureComponents(page, 'mobile', 'dark');
  });

  test('mobile menu abierto', async ({ page }) => {
    await page.goto('/dashboard');
    await page.waitForSelector('.hamburger');
    await freezeAnimations(page);
    await page.locator('.hamburger').click();
    await page.waitForSelector('.nav-links.open', { timeout: 2000 });
    await shot(page, 'mobile', 'navbar-menu-open-dark');
  });
});

// ─────────────────────────────────────────────
// MOBILE LIGHT (390x844)
// ─────────────────────────────────────────────
test.describe('Docs — Mobile Light', () => {
  test.use({ viewport: { width: 390, height: 844 } });

  test.beforeEach(async ({ page }) => {
    await authenticateWithTheme(page, 'light');
  });

  test('pages', async ({ page }) => {
    await capturePages(page, 'mobile', 'light');
  });

  test('components', async ({ page }) => {
    await captureComponents(page, 'mobile', 'light');
  });

  test('mobile menu abierto', async ({ page }) => {
    await page.goto('/dashboard');
    await page.waitForSelector('.hamburger');
    await freezeAnimations(page);
    await page.locator('.hamburger').click();
    await page.waitForSelector('.nav-links.open', { timeout: 2000 });
    await shot(page, 'mobile', 'navbar-menu-open-light');
  });
});

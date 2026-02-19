import { test, expect } from '@playwright/test';
import { authenticateWithTheme } from './helpers/auth';
import { freezeAnimations } from './helpers/freeze-animations';

// El proyecto Playwright determina el tema a usar
function getTheme(projectName: string): 'dark' | 'light' {
  return projectName === 'desktop-light' ? 'light' : 'dark';
}

test.describe('Visual — Páginas completas', () => {
  test.beforeEach(async ({ page }, testInfo) => {
    const theme = getTheme(testInfo.project.name);
    await authenticateWithTheme(page, theme);
  });

  test('Dashboard', async ({ page }, testInfo) => {
    const theme = getTheme(testInfo.project.name);
    await page.goto('/dashboard');
    await page.waitForSelector('.stats-bar');
    await page.waitForSelector('app-news-item-card');
    await freezeAnimations(page);
    await expect(page).toHaveScreenshot(`dashboard-${theme}.png`, { fullPage: true });
  });

  test('Archive', async ({ page }, testInfo) => {
    const theme = getTheme(testInfo.project.name);
    await page.goto('/archive');
    await page.waitForSelector('.stats-bar', { timeout: 8000 });
    await page.waitForSelector('app-news-item-card');
    await freezeAnimations(page);
    await expect(page).toHaveScreenshot(`archive-${theme}.png`, { fullPage: true });
  });

  test('Search — empty state', async ({ page }, testInfo) => {
    const theme = getTheme(testInfo.project.name);
    await page.goto('/search');
    await page.waitForSelector('.search-empty-state');
    await freezeAnimations(page);
    await expect(page).toHaveScreenshot(`search-empty-${theme}.png`, { fullPage: true });
  });

  test('Search — con resultados', async ({ page }, testInfo) => {
    const theme = getTheme(testInfo.project.name);
    await page.goto('/search');
    await page.locator('input[name="query"]').fill('LLM');
    await page.getByRole('button', { name: 'Buscar' }).click();
    await page.waitForSelector('app-news-item-card', { timeout: 5000 });
    await page.waitForLoadState('networkidle');
    await freezeAnimations(page);
    await expect(page).toHaveScreenshot(`search-results-${theme}.png`, { fullPage: true, maxDiffPixels: 5000 });
  });

  test('Analytics', async ({ page }, testInfo) => {
    const theme = getTheme(testInfo.project.name);
    await page.goto('/analytics');
    await page.waitForSelector('.chart-grid', { timeout: 10000 });
    await page.waitForSelector('highcharts-chart svg', { timeout: 10000 });
    await page.waitForTimeout(500);
    await freezeAnimations(page);
    await expect(page).toHaveScreenshot(`analytics-${theme}.png`, { fullPage: true });
  });

  test('Chat — empty state', async ({ page }, testInfo) => {
    const theme = getTheme(testInfo.project.name);
    await page.goto('/chat');
    await page.waitForSelector('.empty-state');
    await freezeAnimations(page);
    await expect(page).toHaveScreenshot(`chat-${theme}.png`, { fullPage: true });
  });
});

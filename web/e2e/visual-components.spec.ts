import { test, expect } from '@playwright/test';
import { authenticateWithTheme } from './helpers/auth';
import { freezeAnimations } from './helpers/freeze-animations';

function getTheme(projectName: string): 'dark' | 'light' {
  return projectName === 'desktop-light' ? 'light' : 'dark';
}

test.describe('Visual — Componentes críticos', () => {
  test.beforeEach(async ({ page }, testInfo) => {
    const theme = getTheme(testInfo.project.name);
    await authenticateWithTheme(page, theme);
  });

  test('Navbar', async ({ page }, testInfo) => {
    const theme = getTheme(testInfo.project.name);
    await page.goto('/dashboard');
    await page.waitForSelector('.navbar');
    await freezeAnimations(page);
    await expect(page.locator('.navbar')).toHaveScreenshot(`navbar-${theme}.png`);
  });

  test('Stats bar', async ({ page }, testInfo) => {
    const theme = getTheme(testInfo.project.name);
    await page.goto('/dashboard');
    await page.waitForSelector('.stats-bar');
    await freezeAnimations(page);
    await expect(page.locator('.stats-bar')).toHaveScreenshot(`stats-bar-${theme}.png`);
  });

  test('News card', async ({ page }, testInfo) => {
    const theme = getTheme(testInfo.project.name);
    await page.goto('/dashboard');
    await page.waitForSelector('app-news-item-card');
    await freezeAnimations(page);
    await expect(page.locator('app-news-item-card').first()).toHaveScreenshot(`news-card-${theme}.png`);
  });

  test('mat-select abierto', async ({ page }, testInfo) => {
    const theme = getTheme(testInfo.project.name);
    await page.goto('/chat');
    await page.waitForSelector('mat-select');
    await freezeAnimations(page);
    await page.locator('mat-select').first().click();
    await page.waitForSelector('.mat-mdc-select-panel', { timeout: 3000 });
    await expect(page).toHaveScreenshot(`mat-select-open-${theme}.png`);
  });

  test('mat-datepicker abierto', async ({ page }, testInfo) => {
    const theme = getTheme(testInfo.project.name);
    await page.goto('/archive');
    await page.waitForSelector('.stats-bar', { timeout: 8000 });
    await freezeAnimations(page);
    await page.locator('mat-datepicker-toggle button').first().click();
    await page.waitForSelector('.mat-datepicker-content', { timeout: 3000 });
    await expect(page).toHaveScreenshot(`mat-datepicker-open-${theme}.png`);
  });

  test('Suggestion chips', async ({ page }, testInfo) => {
    const theme = getTheme(testInfo.project.name);
    await page.goto('/chat');
    await page.waitForSelector('.suggestions');
    await freezeAnimations(page);
    await expect(page.locator('.suggestions')).toHaveScreenshot(`suggestion-chips-${theme}.png`);
  });

  test('Mobile menu abierto', async ({ page }, testInfo) => {
    if (testInfo.project.name !== 'mobile') {
      test.skip();
      return;
    }
    await page.goto('/dashboard');
    await page.waitForSelector('.hamburger');
    await freezeAnimations(page);
    await page.locator('.hamburger').click();
    await page.waitForSelector('.nav-links.open', { timeout: 2000 });
    await expect(page.locator('.navbar')).toHaveScreenshot('mobile-menu-open.png');
  });
});

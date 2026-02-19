import { test, expect } from '@playwright/test';
import { authenticate } from './helpers/auth';

test.describe('Archive', () => {
  test.beforeEach(async ({ page }) => {
    await authenticate(page);
    await page.goto('/archive');
  });

  test('auto-carga el briefing de hoy al entrar', async ({ page }) => {
    await expect(page.locator('.stats-bar')).toBeVisible({ timeout: 8000 });
    await expect(page.locator('app-news-item-card').first()).toBeVisible({ timeout: 8000 });
  });

  test('stats bar labels tienen acentos correctos', async ({ page }) => {
    await page.waitForSelector('.stats-bar');
    await expect(page.locator('.stat-label').filter({ hasText: 'Extraídas' })).toBeVisible();
    await expect(page.locator('.stat-label').filter({ hasText: 'Duración' })).toBeVisible();
  });

  test('título de distribución por tema tiene tilde', async ({ page }) => {
    await page.waitForSelector('.topic-summary');
    await expect(page.locator('.topic-summary h3')).toContainText('Distribución por tema');
  });

  test('el toggle del datepicker abre el calendario', async ({ page }) => {
    await page.waitForSelector('.stats-bar');
    const toggle = page.locator('mat-datepicker-toggle button').first();
    await expect(toggle).toBeVisible();
    await toggle.click();
    await expect(page.locator('.mat-datepicker-content')).toBeVisible({ timeout: 3000 });
    await page.keyboard.press('Escape');
  });
});

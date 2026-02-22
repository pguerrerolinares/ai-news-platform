import { test, expect } from '@playwright/test';
import { authenticate } from './helpers/auth';

test.describe('Archive', () => {
  test.beforeEach(async ({ page }) => {
    await authenticate(page);
    await page.goto('/archive');
  });

  test('auto-carga el briefing de hoy al entrar', async ({ page }) => {
    await expect(page.locator('.stat-module')).toBeVisible({ timeout: 8000 });
    await expect(page.locator('app-news-item-card').first()).toBeVisible({ timeout: 8000 });
  });

  test('stats bar labels tienen acentos correctos', async ({ page }) => {
    await page.waitForSelector('.stat-module');
    await expect(page.locator('.stat-label').filter({ hasText: 'Extraídas' })).toBeVisible();
    await expect(page.locator('.stat-label').filter({ hasText: 'Duración' })).toBeVisible();
  });

  test('topic chips se muestran correctamente', async ({ page }) => {
    await page.waitForSelector('.topic-row', { timeout: 8000 });
    await expect(page.locator('.topic-chip').first()).toBeVisible();
  });

  test('el toggle del datepicker abre el calendario', async ({ page }) => {
    await page.waitForSelector('.stat-module');
    const toggle = page.locator('mat-datepicker-toggle button').first();
    await expect(toggle).toBeVisible();
    await toggle.click();
    await expect(page.locator('.mat-datepicker-content')).toBeVisible({ timeout: 3000 });
    await page.keyboard.press('Escape');
  });
});

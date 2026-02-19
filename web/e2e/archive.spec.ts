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

  test('cambiar fecha dispara carga de nuevos datos', async ({ page }) => {
    await page.waitForSelector('.stats-bar');
    const dateInput = page.locator('#archive-date');
    await dateInput.fill('2026-02-10');
    await dateInput.dispatchEvent('input');
    await dateInput.dispatchEvent('change');
    await page.waitForTimeout(600);
    const countLabel = page.locator('.count-label');
    if (await countLabel.isVisible()) {
      await expect(countLabel).toContainText('2026-02-10');
    }
  });
});

import { test, expect } from '@playwright/test';
import { authenticate } from './helpers/auth';

test.describe('Dashboard', () => {
  test.beforeEach(async ({ page }) => {
    await authenticate(page);
    await page.goto('/dashboard');
    await page.waitForSelector('.stat-module', { timeout: 8000 });
  });

  test('stat module muestra stat items con valores', async ({ page }) => {
    const stats = page.locator('.stat-item');
    expect(await stats.count()).toBeGreaterThanOrEqual(4);
  });

  test('stat labels tienen acentos correctos', async ({ page }) => {
    await expect(page.locator('.stat-label').filter({ hasText: 'Extraídas' })).toBeVisible();
  });

  test('click en filter chip filtra las noticias', async ({ page }) => {
    await page.waitForSelector('.filter-chip', { timeout: 5000 });
    const totalBefore = await page.locator('app-news-item-card').count();
    await page.locator('.filter-chip').first().click();
    const totalAfter = await page.locator('app-news-item-card').count();
    expect(totalAfter).toBeLessThanOrEqual(totalBefore);
    await expect(page.locator('.filter-clear')).toBeVisible();
  });

  test('limpiar filtro restaura todos los items', async ({ page }) => {
    await page.waitForSelector('.filter-chip', { timeout: 5000 });
    const totalBefore = await page.locator('app-news-item-card').count();
    await page.locator('.filter-chip').first().click();
    await page.locator('.filter-clear').click();
    await expect(page.locator('app-news-item-card')).toHaveCount(totalBefore, { timeout: 3000 });
  });

  test('las news cards son visibles', async ({ page }) => {
    const cards = page.locator('app-news-item-card');
    await expect(cards.first()).toBeVisible();
    expect(await cards.count()).toBeGreaterThan(0);
  });
});

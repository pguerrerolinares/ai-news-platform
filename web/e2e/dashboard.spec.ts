import { test, expect } from '@playwright/test';
import { authenticate } from './helpers/auth';

test.describe('Dashboard', () => {
  test.beforeEach(async ({ page }) => {
    await authenticate(page);
    await page.goto('/dashboard');
    await page.waitForSelector('.stats-bar', { timeout: 8000 });
  });

  test('stats bar muestra 5 stats con valores', async ({ page }) => {
    const stats = page.locator('.stat');
    await expect(stats).toHaveCount(5);
  });

  test('stats bar labels tienen acentos correctos', async ({ page }) => {
    await expect(page.locator('.stat-label').filter({ hasText: 'Extraídas' })).toBeVisible();
    await expect(page.locator('.stat-label').filter({ hasText: 'Duración' })).toBeVisible();
  });

  test('distribucion por tema muestra título con tilde', async ({ page }) => {
    await expect(page.locator('.topic-summary h3')).toContainText('Distribución por tema');
  });

  test('click en topic chip filtra las noticias', async ({ page }) => {
    const totalBefore = await page.locator('app-news-item-card').count();
    await page.locator('.topic-chip').first().click();
    const totalAfter = await page.locator('app-news-item-card').count();
    expect(totalAfter).toBeLessThanOrEqual(totalBefore);
    await expect(page.locator('.clear-filter')).toBeVisible();
  });

  test('limpiar filtro restaura todos los items', async ({ page }) => {
    const totalBefore = await page.locator('app-news-item-card').count();
    await page.locator('.topic-chip').first().click();
    await page.locator('.clear-filter').click();
    await expect(page.locator('app-news-item-card')).toHaveCount(totalBefore, { timeout: 3000 });
  });

  test('las news cards son visibles', async ({ page }) => {
    const cards = page.locator('app-news-item-card');
    await expect(cards.first()).toBeVisible();
    expect(await cards.count()).toBeGreaterThan(0);
  });
});

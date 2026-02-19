import { test, expect } from '@playwright/test';
import { authenticate } from './helpers/auth';

test.describe('Analytics', () => {
  test.beforeEach(async ({ page }) => {
    await authenticate(page);
    await page.goto('/analytics');
    await page.waitForSelector('.chart-grid', { timeout: 10000 });
  });

  test('muestra 3 chart cards', async ({ page }) => {
    await expect(page.locator('.chart-card')).toHaveCount(3);
  });

  test('primer chart tiene título correcto con acentos', async ({ page }) => {
    await expect(page.locator('.chart-card h3').first()).toContainText('Items por día (últimos 14 días)');
  });

  test('segundo chart tiene título Distribución con tilde', async ({ page }) => {
    await expect(page.locator('.chart-card h3').nth(1)).toContainText('Distribución por tema');
  });

  test('los charts renderizan SVG de Highcharts', async ({ page }) => {
    const svgs = page.locator('highcharts-chart svg');
    await expect(svgs.first()).toBeVisible({ timeout: 10000 });
    expect(await svgs.count()).toBe(3);
  });

  test('dark/light toggle actualiza clase html y charts siguen visibles', async ({ page }) => {
    const html = page.locator('html');
    const wasDark = await html.evaluate(el => el.classList.contains('dark'));
    await page.locator('.theme-toggle').click();
    const isDark = await html.evaluate(el => el.classList.contains('dark'));
    expect(isDark).not.toBe(wasDark);
    await expect(page.locator('highcharts-chart svg').first()).toBeVisible();
  });
});

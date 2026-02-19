import { test, expect } from '@playwright/test';
import { authenticate } from './helpers/auth';

test.describe('Search', () => {
  test.beforeEach(async ({ page }) => {
    await authenticate(page);
    await page.goto('/search');
  });

  test('muestra empty state al cargar sin búsqueda', async ({ page }) => {
    await expect(page.locator('.search-empty-state')).toBeVisible();
    await expect(page.locator('.search-empty-title')).toContainText('Busca entre las noticias archivadas');
    await expect(page.locator('.search-suggestions .quick-chip').first()).toBeVisible();
  });

  test('buscar "LLM" retorna resultados y oculta empty state', async ({ page }) => {
    await page.locator('input[name="query"]').fill('LLM');
    await page.getByRole('button', { name: 'Buscar' }).click();
    await expect(page.locator('.search-empty-state')).not.toBeVisible();
    await expect(page.locator('.count-label')).toBeVisible({ timeout: 5000 });
    expect(await page.locator('app-news-item-card').count()).toBeGreaterThan(0);
  });

  test('buscar término sin resultados muestra mensaje adecuado', async ({ page }) => {
    await page.locator('input[name="query"]').fill('xyzterminoinexistente999');
    await page.getByRole('button', { name: 'Buscar' }).click();
    await expect(page.locator('.empty')).toBeVisible({ timeout: 5000 });
    await expect(page.locator('app-news-item-card')).toHaveCount(0);
  });

  test('botón Buscar deshabilitado cuando query vacío', async ({ page }) => {
    await expect(page.getByRole('button', { name: 'Buscar' })).toBeDisabled();
  });
});

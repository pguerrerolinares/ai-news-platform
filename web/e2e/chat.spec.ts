import { test, expect } from '@playwright/test';
import { authenticate } from './helpers/auth';

test.describe('Chat', () => {
  test.beforeEach(async ({ page }) => {
    await authenticate(page);
    await page.goto('/chat');
    await expect(page.locator('.empty-state')).toBeVisible();
  });

  test('muestra 4 suggestion chips', async ({ page }) => {
    await expect(page.locator('.suggestion-chip')).toHaveCount(4);
  });

  test('los chips no tienen texto truncado', async ({ page }) => {
    const chips = page.locator('.suggestion-chip');
    const count = await chips.count();
    for (let i = 0; i < count; i++) {
      const isTruncated = await chips.nth(i).evaluate(
        el => el.scrollWidth > el.offsetWidth + 2
      );
      expect(isTruncated).toBe(false);
    }
  });

  test('click en suggestion chip envía el mensaje', async ({ page }) => {
    await page.locator('.suggestion-chip').first().click();
    await expect(page.locator('.empty-state')).not.toBeVisible({ timeout: 3000 });
    await expect(page.locator('.message.user')).toBeVisible({ timeout: 3000 });
  });

  test('botón Enviar deshabilitado cuando input vacío', async ({ page }) => {
    await expect(page.getByRole('button', { name: 'Enviar' })).toBeDisabled();
  });

  test('input habilitado cuando no hay streaming', async ({ page }) => {
    await expect(page.locator('input[name="question"]')).toBeEnabled();
  });
});

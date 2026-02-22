import { test, expect } from '@playwright/test';
import { authenticate } from './helpers/auth';

test.describe('Login', () => {
  test('página /login renderiza el formulario correctamente', async ({ page }) => {
    // En mock mode, APP_INITIALIZER auto-autentica siempre.
    // Probamos que la página login es accesible y muestra el formulario.
    await page.goto('/login');
    await expect(page.locator('h1')).toContainText('AI NEWS');
    await expect(page.locator('#password')).toBeVisible();
    await expect(page.getByRole('button', { name: 'Ingresar' })).toBeVisible();
  });

  test('login con cualquier password redirige a dashboard', async ({ page }) => {
    await page.goto('/login');
    await page.locator('#password').fill('cualquier-password');
    await page.getByRole('button', { name: 'Ingresar' }).click();
    await expect(page).toHaveURL(/dashboard/);
    await expect(page.locator('.stat-module')).toBeVisible();
  });
});

test.describe('Navegación', () => {
  test.beforeEach(async ({ page }) => {
    await authenticate(page);
  });

  test('todos los links del nav cargan la página correcta', async ({ page }) => {
    await page.goto('/dashboard');

    await page.getByRole('link', { name: 'Archivo' }).click();
    await expect(page).toHaveURL(/archive/);

    await page.getByRole('link', { name: 'Buscar' }).click();
    await expect(page).toHaveURL(/search/);

    await page.getByRole('link', { name: 'Analytics' }).click();
    await expect(page).toHaveURL(/analytics/);

    await page.getByRole('link', { name: 'Chat' }).click();
    await expect(page).toHaveURL(/chat/);

    await page.getByRole('link', { name: 'Dashboard' }).click();
    await expect(page).toHaveURL(/dashboard/);
  });

  test('dark/light mode toggle cambia clase en html', async ({ page }) => {
    await page.goto('/dashboard');
    const html = page.locator('html');
    const hasDark = await html.evaluate(el => el.classList.contains('dark'));

    await page.locator('.theme-toggle').click();
    const afterToggle = await html.evaluate(el => el.classList.contains('dark'));
    expect(afterToggle).not.toBe(hasDark);
  });
});

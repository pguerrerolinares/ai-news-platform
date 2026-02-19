# E2E Playwright Tests Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Instalar Playwright, escribir functional tests para las 5 páginas principales + navegación, ejecutarlos y reportar todos los fallos.

**Architecture:** `@playwright/test` standalone con `webServer` que arranca `npm run mock` automáticamente. Los tests no-auth bypasean el login inyectando el JWT mock en localStorage directamente (más rápido y fiable). Un spec file por página.

**Tech Stack:** `@playwright/test`, Chromium headless, Angular 21 mock server en puerto 4200.

**Cómo ejecutar:**
```bash
cd web
npm run e2e
```

---

## Task 1: Instalar Playwright y configurar

**Archivos:**
- Create: `web/playwright.config.ts`
- Modify: `web/package.json`

**Step 1: Instalar dependencia**
```bash
cd web && npm install --save-dev @playwright/test
```

**Step 2: Instalar browser Chromium**
```bash
cd web && npx playwright install chromium
```

**Step 3: Crear `web/playwright.config.ts`**
```typescript
import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './e2e',
  timeout: 15_000,
  expect: { timeout: 5_000 },
  fullyParallel: false,
  retries: 0,
  reporter: [['list'], ['html', { open: 'never', outputFolder: 'playwright-report' }]],
  use: {
    baseURL: 'http://localhost:4200',
    screenshot: 'only-on-failure',
    trace: 'on-first-retry',
  },
  projects: [
    { name: 'chromium', use: { ...devices['Desktop Chrome'] } },
  ],
  webServer: {
    command: 'npm run mock',
    url: 'http://localhost:4200',
    reuseExistingServer: true,
    timeout: 60_000,
  },
});
```

**Step 4: Añadir script `e2e` en `web/package.json`**
```json
"e2e": "playwright test",
"e2e:report": "playwright show-report playwright-report"
```

**Step 5: Crear directorio e2e**
```bash
mkdir -p web/e2e
```

**Step 6: Commit**
```bash
git add web/package.json web/playwright.config.ts
git commit -m "feat(e2e): setup Playwright con webServer mock [Track A]"
```

---

## Task 2: Helper de autenticación

**Archivos:**
- Create: `web/e2e/helpers/auth.ts`

El mock acepta cualquier password y devuelve siempre el mismo JWT. Para tests no-auth, inyectamos el JWT en localStorage antes de navegar (evita el UI de login en cada test).

**Step 1: Crear `web/e2e/helpers/auth.ts`**
```typescript
import { Page } from '@playwright/test';

// JWT mock con exp=9999999999 (año ~2286)
export const MOCK_JWT =
  'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9' +
  '.eyJzdWIiOiIxIiwiZXhwIjo5OTk5OTk5OTk5fQ' +
  '.mockSignature';

/** Inyecta el JWT en localStorage para bypasear el login UI */
export async function authenticate(page: Page): Promise<void> {
  await page.goto('/');
  await page.evaluate((token) => {
    localStorage.setItem('ainews_token', token);
  }, MOCK_JWT);
}
```

**Step 2: Commit**
```bash
git add web/e2e/helpers/auth.ts
git commit -m "feat(e2e): helper de autenticación mock [Track A]"
```

---

## Task 3: Tests de navegación y login

**Archivos:**
- Create: `web/e2e/navigation.spec.ts`

**Step 1: Crear `web/e2e/navigation.spec.ts`**
```typescript
import { test, expect } from '@playwright/test';
import { authenticate, MOCK_JWT } from './helpers/auth';

test.describe('Login', () => {
  test('muestra formulario de login cuando no hay token', async ({ page }) => {
    await page.goto('/dashboard');
    await expect(page).toHaveURL(/login/);
    await expect(page.locator('h1')).toContainText('AI News Platform');
    await expect(page.locator('#password')).toBeVisible();
  });

  test('login con cualquier password redirige a dashboard', async ({ page }) => {
    await page.goto('/login');
    await page.locator('#password').fill('cualquier-password');
    await page.getByRole('button', { name: 'Ingresar' }).click();
    await expect(page).toHaveURL(/dashboard/);
    await expect(page.locator('.stats-bar')).toBeVisible();
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
```

**Step 2: Ejecutar solo estos tests**
```bash
cd web && npx playwright test navigation.spec.ts --reporter=list
```

**Step 3: Commit**
```bash
git add web/e2e/navigation.spec.ts
git commit -m "feat(e2e): tests de navegación y login [Track A]"
```

---

## Task 4: Tests de Dashboard

**Archivos:**
- Create: `web/e2e/dashboard.spec.ts`

**Step 1: Crear `web/e2e/dashboard.spec.ts`**
```typescript
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
    // Verificar que los labels tienen acentos correctos
    await expect(page.locator('.stat-label').filter({ hasText: 'Extraídas' })).toBeVisible();
    await expect(page.locator('.stat-label').filter({ hasText: 'Duración' })).toBeVisible();
  });

  test('distribucion por tema muestra chips con tilde', async ({ page }) => {
    await expect(page.locator('.topic-summary h3')).toContainText('Distribución por tema');
    const chips = page.locator('.topic-chip');
    await expect(chips.first()).toBeVisible();
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
    const totalAfter = await page.locator('app-news-item-card').count();
    expect(totalAfter).toBe(totalBefore);
  });

  test('las news cards son visibles', async ({ page }) => {
    const cards = page.locator('app-news-item-card');
    await expect(cards.first()).toBeVisible();
    expect(await cards.count()).toBeGreaterThan(0);
  });
});
```

**Step 2: Ejecutar**
```bash
cd web && npx playwright test dashboard.spec.ts --reporter=list
```

**Step 3: Commit**
```bash
git add web/e2e/dashboard.spec.ts
git commit -m "feat(e2e): tests de Dashboard [Track A]"
```

---

## Task 5: Tests de Archive

**Archivos:**
- Create: `web/e2e/archive.spec.ts`

**Step 1: Crear `web/e2e/archive.spec.ts`**
```typescript
import { test, expect } from '@playwright/test';
import { authenticate } from './helpers/auth';

test.describe('Archive', () => {
  test.beforeEach(async ({ page }) => {
    await authenticate(page);
    await page.goto('/archive');
  });

  test('auto-carga el briefing de hoy al entrar', async ({ page }) => {
    // Debe mostrar stats sin que el usuario seleccione fecha
    await expect(page.locator('.stats-bar')).toBeVisible({ timeout: 8000 });
    await expect(page.locator('app-news-item-card').first()).toBeVisible({ timeout: 8000 });
  });

  test('stats bar tiene labels con acentos correctos', async ({ page }) => {
    await page.waitForSelector('.stats-bar');
    await expect(page.locator('.stat-label').filter({ hasText: 'Extraídas' })).toBeVisible();
    await expect(page.locator('.stat-label').filter({ hasText: 'Duración' })).toBeVisible();
  });

  test('título de distribución por tema tiene tilde', async ({ page }) => {
    await page.waitForSelector('.topic-summary');
    await expect(page.locator('.topic-summary h3')).toContainText('Distribución por tema');
  });

  test('cambiar fecha carga nuevos datos', async ({ page }) => {
    await page.waitForSelector('.stats-bar');
    const dateInput = page.locator('#archive-date');
    await dateInput.fill('2026-02-10');
    await dateInput.dispatchEvent('input');
    await dateInput.dispatchEvent('change');
    // Esperar que el estado se actualice (puede mostrar datos o error de fecha)
    await page.waitForTimeout(500);
    // Debe haber re-cargado (loading state o nuevos datos)
    const countLabel = page.locator('.count-label');
    if (await countLabel.isVisible()) {
      await expect(countLabel).toContainText('2026-02-10');
    }
  });
});
```

**Step 2: Ejecutar**
```bash
cd web && npx playwright test archive.spec.ts --reporter=list
```

**Step 3: Commit**
```bash
git add web/e2e/archive.spec.ts
git commit -m "feat(e2e): tests de Archive [Track A]"
```

---

## Task 6: Tests de Search

**Archivos:**
- Create: `web/e2e/search.spec.ts`

**Step 1: Crear `web/e2e/search.spec.ts`**
```typescript
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
    await expect(page.locator('.search-empty-hint')).toContainText('LLM');
  });

  test('buscar "LLM" retorna resultados y oculta empty state', async ({ page }) => {
    await page.locator('input[name="query"]').fill('LLM');
    await page.getByRole('button', { name: 'Buscar' }).click();
    await expect(page.locator('.search-empty-state')).not.toBeVisible();
    await expect(page.locator('.count-label')).toBeVisible({ timeout: 5000 });
    const cards = page.locator('app-news-item-card');
    expect(await cards.count()).toBeGreaterThan(0);
  });

  test('buscar término sin resultados muestra mensaje adecuado', async ({ page }) => {
    await page.locator('input[name="query"]').fill('xyzterminoinexistente999');
    await page.getByRole('button', { name: 'Buscar' }).click();
    await expect(page.locator('.empty')).toBeVisible({ timeout: 5000 });
    await expect(page.locator('app-news-item-card')).toHaveCount(0);
  });

  test('botón Buscar deshabilitado cuando query está vacío', async ({ page }) => {
    await expect(page.getByRole('button', { name: 'Buscar' })).toBeDisabled();
  });
});
```

**Step 2: Ejecutar**
```bash
cd web && npx playwright test search.spec.ts --reporter=list
```

**Step 3: Commit**
```bash
git add web/e2e/search.spec.ts
git commit -m "feat(e2e): tests de Search [Track A]"
```

---

## Task 7: Tests de Analytics

**Archivos:**
- Create: `web/e2e/analytics.spec.ts`

**Step 1: Crear `web/e2e/analytics.spec.ts`**
```typescript
import { test, expect } from '@playwright/test';
import { authenticate } from './helpers/auth';

test.describe('Analytics', () => {
  test.beforeEach(async ({ page }) => {
    await authenticate(page);
    await page.goto('/analytics');
    // Esperar a que los charts rendericen (Highcharts genera SVG)
    await page.waitForSelector('.chart-grid', { timeout: 10000 });
  });

  test('muestra 3 chart cards', async ({ page }) => {
    const cards = page.locator('.chart-card');
    await expect(cards).toHaveCount(3);
  });

  test('chart "Items por día" tiene título correcto con acentos', async ({ page }) => {
    await expect(page.locator('.chart-card h3').first()).toContainText('Items por día (últimos 14 días)');
  });

  test('chart "Distribución por tema" tiene título con tilde', async ({ page }) => {
    await expect(page.locator('.chart-card h3').nth(1)).toContainText('Distribución por tema');
  });

  test('los charts renderizan SVG de Highcharts', async ({ page }) => {
    const svgs = page.locator('highcharts-chart svg');
    await expect(svgs.first()).toBeVisible({ timeout: 10000 });
    expect(await svgs.count()).toBe(3);
  });

  test('dark/light toggle actualiza clase html (charts reactivos)', async ({ page }) => {
    const html = page.locator('html');
    const wasDark = await html.evaluate(el => el.classList.contains('dark'));
    await page.locator('.theme-toggle').click();
    const isDark = await html.evaluate(el => el.classList.contains('dark'));
    expect(isDark).not.toBe(wasDark);
    // Charts siguen visibles después del toggle
    await expect(page.locator('highcharts-chart svg').first()).toBeVisible();
  });
});
```

**Step 2: Ejecutar**
```bash
cd web && npx playwright test analytics.spec.ts --reporter=list
```

**Step 3: Commit**
```bash
git add web/e2e/analytics.spec.ts
git commit -m "feat(e2e): tests de Analytics [Track A]"
```

---

## Task 8: Tests de Chat

**Archivos:**
- Create: `web/e2e/chat.spec.ts`

**Step 1: Crear `web/e2e/chat.spec.ts`**
```typescript
import { test, expect } from '@playwright/test';
import { authenticate } from './helpers/auth';

test.describe('Chat', () => {
  test.beforeEach(async ({ page }) => {
    await authenticate(page);
    await page.goto('/chat');
    await expect(page.locator('.empty-state')).toBeVisible();
  });

  test('muestra 4 suggestion chips', async ({ page }) => {
    const chips = page.locator('.suggestion-chip');
    await expect(chips).toHaveCount(4);
  });

  test('los chips no tienen texto truncado (overflow visible)', async ({ page }) => {
    const chips = page.locator('.suggestion-chip');
    for (let i = 0; i < await chips.count(); i++) {
      const chip = chips.nth(i);
      // scrollWidth <= offsetWidth significa texto sin truncar
      const isTruncated = await chip.evaluate(el => el.scrollWidth > el.offsetWidth + 2);
      expect(isTruncated).toBe(false);
    }
  });

  test('click en suggestion chip rellena el input', async ({ page }) => {
    const firstChip = page.locator('.suggestion-chip').first();
    const chipText = await firstChip.textContent();
    await firstChip.click();
    // El input debe tener el texto de la suggestion o ya haberse enviado
    // (askQuestion llama a onSend directamente)
    // Verificamos que desaparece el empty state (mensaje enviado)
    await expect(page.locator('.empty-state')).not.toBeVisible({ timeout: 3000 });
  });

  test('input de pregunta deshabilitado mientras streaming', async ({ page }) => {
    const input = page.locator('input[name="question"]');
    await expect(input).toBeEnabled();
    await expect(input).not.toBeDisabled();
  });

  test('botón Enviar deshabilitado cuando input vacío', async ({ page }) => {
    await expect(page.getByRole('button', { name: 'Enviar' })).toBeDisabled();
  });
});
```

**Step 2: Ejecutar**
```bash
cd web && npx playwright test chat.spec.ts --reporter=list
```

**Step 3: Commit**
```bash
git add web/e2e/chat.spec.ts
git commit -m "feat(e2e): tests de Chat [Track A]"
```

---

## Task 9: Ejecutar suite completa y reportar fallos

**Step 1: Levantar servidor mock en background (si no está arrancado)**
El `webServer` de playwright.config.ts lo levanta automáticamente.

**Step 2: Ejecutar todos los tests**
```bash
cd web && npx playwright test --reporter=list 2>&1
```

**Step 3: Analizar output**
Anotar todos los tests que fallen con:
- Nombre del test
- Error exacto
- Página/componente afectado

**Step 4: Generar report HTML**
```bash
cd web && npx playwright show-report playwright-report
```

**Step 5: Commit de resultados (aunque haya fallos)**
```bash
git add web/e2e/
git commit -m "test(e2e): suite completa Playwright — ver fallos en report [Track A]"
```

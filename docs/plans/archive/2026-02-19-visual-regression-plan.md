# Visual Regression Tests Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Añadir suite de visual regression tests con Playwright que detecte bugs de layout (overlaps, colores incorrectos, estados rotos) tomando screenshots en desktop dark, desktop light y mobile para páginas completas y componentes críticos en estado interactivo.

**Architecture:** Tres proyectos Playwright nuevos (`desktop-dark`, `desktop-light`, `mobile`) en `playwright.config.ts`. Dos spec files nuevos: `visual-pages.spec.ts` (screenshots de páginas completas) y `visual-components.spec.ts` (screenshots de componentes abiertos/hover). Helper `freeze-animations.ts` inyecta CSS que desactiva animaciones antes de cada screenshot. Baselines PNG generados en primera run, comparados en runs sucesivas con `maxDiffPixels: 50`.

**Tech Stack:** `@playwright/test` (ya instalado), `toHaveScreenshot()`, viewports 1280×800 y 390×844, Angular mock server en puerto 4200.

**Cómo ejecutar:**
```bash
cd web
npm run e2e:visual          # Genera baselines (1ª vez) o compara
npm run e2e:visual:update   # Actualiza baselines
```

---

## Task 1: Actualizar playwright.config.ts con 3 proyectos visuales

**Archivos:**
- Modify: `web/playwright.config.ts`

**Step 1: Añadir los 3 proyectos visuales**

Reemplazar el array `projects` existente en `web/playwright.config.ts`:

```typescript
import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './e2e',
  timeout: 20_000,
  expect: {
    timeout: 5_000,
    toHaveScreenshot: { maxDiffPixels: 50, threshold: 0.05 },
  },
  fullyParallel: false,
  retries: 0,
  reporter: [['list'], ['html', { open: 'never', outputFolder: 'playwright-report' }]],
  use: {
    baseURL: 'http://localhost:4200',
    screenshot: 'only-on-failure',
    trace: 'on-first-retry',
  },
  projects: [
    // Functional tests (existing)
    { name: 'chromium', testMatch: /(?<!visual-).*\.spec\.ts/, use: { ...devices['Desktop Chrome'] } },
    // Visual regression — desktop dark
    {
      name: 'desktop-dark',
      testMatch: /visual-.*\.spec\.ts/,
      use: { ...devices['Desktop Chrome'], viewport: { width: 1280, height: 800 } },
    },
    // Visual regression — desktop light
    {
      name: 'desktop-light',
      testMatch: /visual-.*\.spec\.ts/,
      use: { ...devices['Desktop Chrome'], viewport: { width: 1280, height: 800 } },
    },
    // Visual regression — mobile dark
    {
      name: 'mobile',
      testMatch: /visual-.*\.spec\.ts/,
      use: { ...devices['Pixel 5'] },
    },
  ],
  webServer: {
    command: 'npm run mock',
    url: 'http://localhost:4200',
    reuseExistingServer: true,
    timeout: 60_000,
  },
});
```

**Step 2: Añadir scripts en `web/package.json`**

```json
"e2e:visual": "playwright test --project=desktop-dark --project=desktop-light --project=mobile",
"e2e:visual:update": "playwright test --update-snapshots --project=desktop-dark --project=desktop-light --project=mobile"
```

**Step 3: Verificar que config es válido**
```bash
cd web && npx playwright test --list 2>&1 | head -20
```
Debe listar tests de los proyectos visual y chromium.

**Step 4: Commit**
```bash
git add web/playwright.config.ts web/package.json
git commit -m "feat(e2e): añadir 3 proyectos Playwright para visual regression [Track A]"
```

---

## Task 2: Helper freeze-animations + setup-theme

**Archivos:**
- Create: `web/e2e/helpers/freeze-animations.ts`
- Modify: `web/e2e/helpers/auth.ts`

**Step 1: Crear `web/e2e/helpers/freeze-animations.ts`**

```typescript
import { Page } from '@playwright/test';

/** Inyecta CSS que congela todas las animaciones y transiciones */
export async function freezeAnimations(page: Page): Promise<void> {
  await page.addStyleTag({
    content: `
      *, *::before, *::after {
        animation-duration: 0ms !important;
        animation-delay: 0ms !important;
        transition-duration: 0ms !important;
        transition-delay: 0ms !important;
      }
    `,
  });
}
```

**Step 2: Añadir helper `setupTheme` en `web/e2e/helpers/auth.ts`**

```typescript
import { Page } from '@playwright/test';

export const MOCK_JWT =
  'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9' +
  '.eyJzdWIiOiIxIiwiZXhwIjo5OTk5OTk5OTk5fQ' +
  '.mockSignature';

export async function authenticate(page: Page): Promise<void> {
  await page.goto('/');
  await page.evaluate((token) => {
    localStorage.setItem('ainews_token', token);
  }, MOCK_JWT);
}

/** Autentica Y establece el tema antes de cargar la app */
export async function authenticateWithTheme(
  page: Page,
  theme: 'dark' | 'light'
): Promise<void> {
  await page.goto('/');
  await page.evaluate(
    ({ token, theme }) => {
      localStorage.setItem('ainews_token', token);
      localStorage.setItem('theme', theme);
    },
    { token: MOCK_JWT, theme }
  );
}
```

**Step 3: Commit**
```bash
git add web/e2e/helpers/
git commit -m "feat(e2e): helpers freeze-animations y authenticateWithTheme [Track A]"
```

---

## Task 3: visual-pages.spec.ts — screenshots de páginas completas

**Archivos:**
- Create: `web/e2e/visual-pages.spec.ts`

**Step 1: Crear `web/e2e/visual-pages.spec.ts`**

```typescript
import { test, expect } from '@playwright/test';
import { authenticateWithTheme } from './helpers/auth';
import { freezeAnimations } from './helpers/freeze-animations';

// El proyecto determina el tema
function getTheme(projectName: string): 'dark' | 'light' {
  return projectName === 'desktop-light' ? 'light' : 'dark';
}

test.describe('Visual — Páginas completas', () => {
  test.beforeEach(async ({ page }, testInfo) => {
    const theme = getTheme(testInfo.project.name);
    await authenticateWithTheme(page, theme);
  });

  test('Dashboard', async ({ page }, testInfo) => {
    const theme = getTheme(testInfo.project.name);
    await page.goto('/dashboard');
    await page.waitForSelector('.stats-bar');
    await page.waitForSelector('app-news-item-card');
    await freezeAnimations(page);
    await expect(page).toHaveScreenshot(`dashboard-${theme}.png`, { fullPage: true });
  });

  test('Archive', async ({ page }, testInfo) => {
    const theme = getTheme(testInfo.project.name);
    await page.goto('/archive');
    await page.waitForSelector('.stats-bar', { timeout: 8000 });
    await page.waitForSelector('app-news-item-card');
    await freezeAnimations(page);
    await expect(page).toHaveScreenshot(`archive-${theme}.png`, { fullPage: true });
  });

  test('Search — empty state', async ({ page }, testInfo) => {
    const theme = getTheme(testInfo.project.name);
    await page.goto('/search');
    await page.waitForSelector('.search-empty-state');
    await freezeAnimations(page);
    await expect(page).toHaveScreenshot(`search-empty-${theme}.png`, { fullPage: true });
  });

  test('Search — con resultados', async ({ page }, testInfo) => {
    const theme = getTheme(testInfo.project.name);
    await page.goto('/search');
    await page.locator('input[name="query"]').fill('LLM');
    await page.getByRole('button', { name: 'Buscar' }).click();
    await page.waitForSelector('app-news-item-card', { timeout: 5000 });
    await freezeAnimations(page);
    await expect(page).toHaveScreenshot(`search-results-${theme}.png`, { fullPage: true });
  });

  test('Analytics', async ({ page }, testInfo) => {
    const theme = getTheme(testInfo.project.name);
    await page.goto('/analytics');
    await page.waitForSelector('.chart-grid', { timeout: 10000 });
    await page.waitForSelector('highcharts-chart svg', { timeout: 10000 });
    await page.waitForTimeout(500); // Highcharts necesita tiempo extra para renderizar SVG
    await freezeAnimations(page);
    await expect(page).toHaveScreenshot(`analytics-${theme}.png`, { fullPage: true });
  });

  test('Chat — empty state', async ({ page }, testInfo) => {
    const theme = getTheme(testInfo.project.name);
    await page.goto('/chat');
    await page.waitForSelector('.empty-state');
    await freezeAnimations(page);
    await expect(page).toHaveScreenshot(`chat-${theme}.png`, { fullPage: true });
  });
});
```

**Step 2: Commit**
```bash
git add web/e2e/visual-pages.spec.ts
git commit -m "feat(e2e): visual-pages spec — screenshots de páginas completas [Track A]"
```

---

## Task 4: visual-components.spec.ts — screenshots de componentes críticos

**Archivos:**
- Create: `web/e2e/visual-components.spec.ts`

**Step 1: Crear `web/e2e/visual-components.spec.ts`**

```typescript
import { test, expect } from '@playwright/test';
import { authenticateWithTheme } from './helpers/auth';
import { freezeAnimations } from './helpers/freeze-animations';

function getTheme(projectName: string): 'dark' | 'light' {
  return projectName === 'desktop-light' ? 'light' : 'dark';
}

test.describe('Visual — Componentes críticos', () => {
  test.beforeEach(async ({ page }, testInfo) => {
    const theme = getTheme(testInfo.project.name);
    await authenticateWithTheme(page, theme);
  });

  test('Navbar desktop', async ({ page }, testInfo) => {
    const theme = getTheme(testInfo.project.name);
    await page.goto('/dashboard');
    await page.waitForSelector('.navbar');
    await freezeAnimations(page);
    const navbar = page.locator('.navbar');
    await expect(navbar).toHaveScreenshot(`navbar-${theme}.png`);
  });

  test('Stats bar', async ({ page }, testInfo) => {
    const theme = getTheme(testInfo.project.name);
    await page.goto('/dashboard');
    await page.waitForSelector('.stats-bar');
    await freezeAnimations(page);
    const statsBar = page.locator('.stats-bar');
    await expect(statsBar).toHaveScreenshot(`stats-bar-${theme}.png`);
  });

  test('News card', async ({ page }, testInfo) => {
    const theme = getTheme(testInfo.project.name);
    await page.goto('/dashboard');
    await page.waitForSelector('app-news-item-card');
    await freezeAnimations(page);
    const firstCard = page.locator('app-news-item-card').first();
    await expect(firstCard).toHaveScreenshot(`news-card-${theme}.png`);
  });

  test('mat-select abierto — Dashboard topic filter', async ({ page }, testInfo) => {
    const theme = getTheme(testInfo.project.name);
    await page.goto('/dashboard');
    await page.waitForSelector('.topic-summary');
    await freezeAnimations(page);
    // Abrir el select de tema en Chat para capturar el panel abierto
    await page.goto('/chat');
    await page.waitForSelector('mat-select');
    await freezeAnimations(page);
    await page.locator('mat-select').first().click();
    await page.waitForSelector('.mat-mdc-select-panel', { timeout: 3000 });
    await page.waitForLoadState('networkidle');
    // Screenshot del área que incluye el trigger + panel
    await expect(page).toHaveScreenshot(`mat-select-open-${theme}.png`, {
      clip: await page.locator('mat-form-field').first().boundingBox().then(b => ({
        x: (b?.x ?? 0) - 8,
        y: (b?.y ?? 0) - 8,
        width: 300,
        height: 320,
      })),
    });
  });

  test('mat-datepicker abierto — Archive', async ({ page }, testInfo) => {
    const theme = getTheme(testInfo.project.name);
    await page.goto('/archive');
    await page.waitForSelector('.stats-bar', { timeout: 8000 });
    await freezeAnimations(page);
    await page.locator('mat-datepicker-toggle button').first().click();
    await page.waitForSelector('.mat-datepicker-content', { timeout: 3000 });
    await page.waitForLoadState('networkidle');
    await expect(page).toHaveScreenshot(`mat-datepicker-open-${theme}.png`, {
      fullPage: false,
    });
  });

  test('Suggestion chips — Chat', async ({ page }, testInfo) => {
    const theme = getTheme(testInfo.project.name);
    await page.goto('/chat');
    await page.waitForSelector('.suggestions');
    await freezeAnimations(page);
    const suggestions = page.locator('.suggestions');
    await expect(suggestions).toHaveScreenshot(`suggestion-chips-${theme}.png`);
  });

  test('Mobile hamburger menu abierto', async ({ page }, testInfo) => {
    // Solo relevante en mobile (390px)
    if (testInfo.project.name !== 'mobile') {
      test.skip();
      return;
    }
    await page.goto('/dashboard');
    await page.waitForSelector('.hamburger');
    await freezeAnimations(page);
    await page.locator('.hamburger').click();
    await page.waitForSelector('.nav-links.open', { timeout: 2000 });
    const navbar = page.locator('.navbar');
    await expect(navbar).toHaveScreenshot('mobile-menu-open.png');
  });
});
```

**Step 2: Commit**
```bash
git add web/e2e/visual-components.spec.ts
git commit -m "feat(e2e): visual-components spec — componentes en estado crítico [Track A]"
```

---

## Task 5: Generar baselines y verificar

**Step 1: Generar baselines (primera run)**
```bash
cd web && npm run e2e:visual:update 2>&1
```
Debe crear ~50 PNGs en `web/e2e/visual-pages.spec.ts-snapshots/` y `web/e2e/visual-components.spec.ts-snapshots/`.

**Step 2: Verificar que los PNGs se crearon**
```bash
find web/e2e -name "*.png" | wc -l
```
Debe ser >= 30.

**Step 3: Ver los screenshots generados**
```bash
ls -la web/e2e/visual-pages.spec.ts-snapshots/
ls -la web/e2e/visual-components.spec.ts-snapshots/
```

**Step 4: Ejecutar suite completa para confirmar que pasan**
```bash
cd web && npm run e2e:visual 2>&1 | tail -20
```
Debe mostrar todos los tests pasando.

**Step 5: Ejecutar también la suite funcional para verificar no hay regresiones**
```bash
cd web && npx playwright test --project=chromium --reporter=list 2>&1 | tail -5
```
Debe mostrar: `28 passed`.

**Step 6: Añadir PNGs de baseline al repo**
```bash
git add web/e2e/
git commit -m "test(e2e): baselines de visual regression — desktop dark/light + mobile [Track A]"
```

---

## Verificación final

```bash
cd web
# Suite funcional (28 tests)
npx playwright test --project=chromium --reporter=list

# Suite visual (páginas + componentes × 3 proyectos)
npm run e2e:visual

# Ver report HTML
npx playwright show-report playwright-report
```

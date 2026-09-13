# Visual Regression Tests Design

**Date:** 2026-02-19
**Goal:** Detectar regresiones visuales y bugs de UI (overlaps, colores incorrectos, layout roto) mediante screenshots automáticos en Playwright.

## Architecture

Playwright `toHaveScreenshot()` — genera baselines PNG en primera ejecución y compara en las siguientes. Threshold: `maxDiffPixels: 50`, `threshold: 0.05`.

## Spec Files

- `e2e/visual-pages.spec.ts` — screenshot completo de cada página
- `e2e/visual-components.spec.ts` — screenshot de componentes en estados críticos (dropdown abierto, hover)

## Coverage

**Páginas** (full-page screenshot × 3 proyectos):
- Dashboard, Archive, Search (empty + results), Analytics, Chat

**Componentes** (element screenshot × 3 proyectos):
- mat-select abierto, mat-datepicker abierto, stats bar, news card, suggestion chips, navbar desktop + mobile menu

## Proyectos Playwright

| Proyecto | Viewport | Tema |
|----------|----------|------|
| `desktop-dark` | 1280×800 | dark |
| `desktop-light` | 1280×800 | light |
| `mobile` | 390×844 | dark |

## Helpers

- `freeze-animations.ts` — inyecta CSS que pone `animation-duration: 0ms; transition-duration: 0ms` globalmente
- Para states interactivos: `waitForSelector` + `waitForLoadState('networkidle')` después de abrir el elemento

## Scripts

```json
"e2e:visual": "playwright test --project=desktop-dark --project=desktop-light --project=mobile visual",
"e2e:visual:update": "playwright test --update-snapshots --project=desktop-dark --project=desktop-light --project=mobile visual"
```

## Total de snapshots esperados

~50 PNGs (5 páginas × 2 estados × 3 proyectos + 6 componentes × 3 proyectos)

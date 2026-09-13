# E2E Tests Design — Playwright Functional Tests

**Date:** 2026-02-19
**Goal:** Set up Playwright E2E tests to detect UI regressions and functional failures across all pages of the Angular frontend.

## Stack

- **Framework:** `@playwright/test` standalone
- **Browser:** Chromium headless
- **Target:** `npm run mock` (port 4200, no backend required)
- **Location:** `web/e2e/`

## Coverage

| Page | Flows tested |
|------|-------------|
| Dashboard | Stats bar visible, topic chip filters news, clear filter, nav links |
| Archive | Auto-loads today on init, date change loads data, topic filter |
| Search | Empty state visible before search, search returns results, no-results state |
| Analytics | 3 charts render, light/dark mode toggle updates chart colors |
| Chat | 4 suggestion chips visible + not truncated, click fills input |
| Navigation | All nav links work, mobile menu open/close |

## Config

- `playwright.config.ts` in `web/` — `webServer` starts `npm run mock` automatically
- Screenshots and traces on failure
- One `.spec.ts` file per page in `web/e2e/`
- `package.json` script: `"e2e": "playwright test"`

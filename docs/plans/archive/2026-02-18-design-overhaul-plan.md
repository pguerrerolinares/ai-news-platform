# Design Overhaul Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Transform the frontend from generic SaaS to Minimal Luxury aesthetic (Raycast-inspired) with a design system foundation.

**Architecture:** Design System First — create SCSS partials with tokens/mixins/animations, then apply to all 7 components. CSS custom properties for runtime dark/light switching. View Transitions API for route animations. Zero TS logic changes.

**Tech Stack:** Angular 21, Angular Material M3, SCSS partials, CSS custom properties, View Transitions API, Plus Jakarta Sans + JetBrains Mono via Google Fonts CDN.

**Design doc:** `docs/plans/2026-02-18-design-overhaul-design.md`

---

## E2E Constraints Cheatsheet

These MUST be preserved in every component. Reference before editing any template.

**IDs:** `#password`, `#archive-date`, `#topic-select`, `#date-from`, `#date-to`

**Classes:** `.navbar`, `.stats-bar`, `.topic-badge`, `.topic-chip`, `.search-input`, `.search-btn`, `.chat-input`, `.send-btn`, `.topic-filter`, `.empty-state`, `.suggestion-chip`, `.message.user`, `.message.assistant`, `.source-link`

**Data attrs:** `[data-source='hackernews']`, `[data-source='reddit']`, `[data-source='arxiv']`

**Other:** `app-news-item-card`, `article` wrapping cards, `button[type='submit']` on login, `h1` with "AI News Platform" on login, all nav `a[href='/...']` links, `text=Salir` on logout, all Spanish UI strings.

---

### Task 1: Create `_tokens.scss`

**Files:**
- Create: `web/src/styles/_tokens.scss`

**Step 1: Create the tokens partial**

```scss
// web/src/styles/_tokens.scss
// Design tokens as CSS custom properties for runtime dark/light switching.
// Components reference these via var(--token-name) in inline styles.

// Light mode (default in :root for html:not(.dark))
:root {
  // Surfaces
  --bg-base: #FAFAFA;
  --bg-surface: #FFFFFF;
  --bg-elevated: #F4F4F5;
  --bg-hover: #E4E4E7;

  // Accent
  --accent: #4F46E5;
  --accent-dim: #4338CA;
  --accent-glow: rgba(79, 70, 229, 0.1);

  // Text
  --text-primary: #09090B;
  --text-secondary: #52525B;
  --text-muted: #A1A1AA;

  // Borders
  --border: rgba(0, 0, 0, 0.06);
  --border-hover: rgba(0, 0, 0, 0.10);
  --border-accent: rgba(79, 70, 229, 0.25);

  // Semantic
  --error: #EF4444;
  --error-subtle: rgba(239, 68, 68, 0.1);
  --success: #10B981;
  --warning: #F59E0B;

  // Shadows
  --shadow-sm: 0 1px 2px rgba(0, 0, 0, 0.04);
  --shadow-md: 0 4px 12px rgba(0, 0, 0, 0.06);
  --shadow-lg: 0 8px 24px rgba(0, 0, 0, 0.08);
  --shadow-glow: 0 0 0 3px var(--accent-glow);
}

// Dark mode (primary experience — .dark on <html>)
.dark {
  --bg-base: #0C0C0E;
  --bg-surface: #141418;
  --bg-elevated: #1C1C22;
  --bg-hover: #24242C;

  --accent: #6366F1;
  --accent-dim: #4F46E5;
  --accent-glow: rgba(99, 102, 241, 0.15);

  --text-primary: #F4F4F5;
  --text-secondary: #A1A1AA;
  --text-muted: #52525B;

  --border: rgba(255, 255, 255, 0.06);
  --border-hover: rgba(255, 255, 255, 0.10);
  --border-accent: rgba(99, 102, 241, 0.3);

  --error: #EF4444;
  --error-subtle: rgba(239, 68, 68, 0.1);
  --success: #10B981;
  --warning: #F59E0B;

  --shadow-sm: 0 1px 2px rgba(0, 0, 0, 0.2);
  --shadow-md: 0 4px 12px rgba(0, 0, 0, 0.3);
  --shadow-lg: 0 8px 24px rgba(0, 0, 0, 0.4);
  --shadow-glow: 0 0 0 3px var(--accent-glow);
}
```

**Step 2: Commit**

```bash
git add web/src/styles/_tokens.scss
git commit -m "feat(m8): add design tokens partial [Track A]"
```

---

### Task 2: Create `_typography.scss`

**Files:**
- Create: `web/src/styles/_typography.scss`

**Step 1: Create the typography partial**

```scss
// web/src/styles/_typography.scss
// Font families and type scale tokens.

:root {
  // Font families
  --font-heading: 'Plus Jakarta Sans', sans-serif;
  --font-body: 'Plus Jakarta Sans', sans-serif;
  --font-mono: 'JetBrains Mono', monospace;

  // Type scale
  --text-xs: 0.6875rem;     // 11px — labels, metadata
  --text-sm: 0.8125rem;     // 13px — chips, nav, small body
  --text-base: 0.9375rem;   // 15px — body default
  --text-lg: 1.125rem;      // 18px — card titles
  --text-xl: 1.5rem;        // 24px — page headings
  --text-2xl: 2rem;         // 32px — login title
  --text-display: 2.5rem;   // 40px — display

  // Line heights paired to scale
  --leading-tight: 1.25;
  --leading-snug: 1.35;
  --leading-normal: 1.5;
  --leading-relaxed: 1.65;

  // Letter spacing
  --tracking-tight: -0.025em;
  --tracking-normal: 0;
  --tracking-wide: 0.02em;
  --tracking-wider: 0.06em;
}
```

**Step 2: Commit**

```bash
git add web/src/styles/_typography.scss
git commit -m "feat(m8): add typography partial [Track A]"
```

---

### Task 3: Create `_animations.scss`

**Files:**
- Create: `web/src/styles/_animations.scss`

**Step 1: Create the animations partial**

```scss
// web/src/styles/_animations.scss
// Keyframes, animation classes, and View Transitions CSS.

// === Keyframes ===

@keyframes fade-in {
  from {
    opacity: 0;
    transform: translateY(12px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@keyframes fade-in-subtle {
  from { opacity: 0; }
  to { opacity: 1; }
}

@keyframes skeleton-shimmer {
  0% { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}

@keyframes blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0; }
}

@keyframes scale-in {
  from {
    opacity: 0;
    transform: scale(0.96);
  }
  to {
    opacity: 1;
    transform: scale(1);
  }
}

// === View Transitions (route animations) ===

@keyframes vt-fade-out {
  to { opacity: 0; }
}

@keyframes vt-fade-slide-in {
  from {
    opacity: 0;
    transform: translateY(6px);
  }
}

::view-transition-old(root) {
  animation: 150ms ease-in vt-fade-out;
}

::view-transition-new(root) {
  animation: 300ms ease-out vt-fade-slide-in;
}

// === Utility Classes ===

.fade-in {
  animation: fade-in 0.4s ease-out both;
}

.scale-in {
  animation: scale-in 0.4s ease-out both;
}

.skeleton {
  background: linear-gradient(
    90deg,
    var(--bg-surface) 25%,
    var(--bg-hover) 50%,
    var(--bg-surface) 75%
  );
  background-size: 200% 100%;
  animation: skeleton-shimmer 1.5s ease-in-out infinite;
  border-radius: 6px;
}
```

**Step 2: Commit**

```bash
git add web/src/styles/_animations.scss
git commit -m "feat(m8): add animations partial with view transitions [Track A]"
```

---

### Task 4: Create `_surfaces.scss`

**Files:**
- Create: `web/src/styles/_surfaces.scss`

**Step 1: Create the surfaces partial — Material overrides + shared surface styles**

```scss
// web/src/styles/_surfaces.scss
// Material component overrides and shared surface classes.

// === Material Component Overrides ===

// MatCard
.mat-mdc-card {
  --mdc-elevated-card-container-color: var(--bg-elevated);
  --mdc-outlined-card-container-color: var(--bg-elevated);
  --mdc-outlined-card-outline-color: var(--border);
  border: 1px solid var(--border) !important;
  border-radius: 14px !important;
  box-shadow: none !important;
  transition: border-color 0.2s ease, box-shadow 0.2s ease, transform 0.2s ease,
    background 0.2s ease;
}

// MatToolbar
.mat-toolbar {
  --mat-toolbar-container-background-color: transparent;
  --mat-toolbar-container-text-color: var(--text-primary);
}

// MatFormField — outline
.mat-mdc-form-field {
  --mdc-outlined-text-field-outline-color: var(--border);
  --mdc-outlined-text-field-hover-outline-color: var(--border-hover);
  --mdc-outlined-text-field-focus-outline-color: var(--accent);
  --mdc-outlined-text-field-input-text-color: var(--text-primary);
  --mdc-outlined-text-field-label-text-color: var(--text-muted);
  --mdc-outlined-text-field-focus-label-text-color: var(--accent);
  --mdc-outlined-text-field-input-text-font: var(--font-body);
  --mdc-outlined-text-field-label-text-font: var(--font-body);
  --mat-form-field-container-text-font: var(--font-body);
  --mat-form-field-subscript-text-font: var(--font-body);

  .mdc-text-field--outlined {
    --mdc-outlined-text-field-container-shape: 10px;
  }
}

.mat-mdc-input-element::placeholder {
  color: var(--text-muted) !important;
}

// MatSelect
.mat-mdc-select {
  --mat-select-trigger-text-font: var(--font-body);
  --mat-select-trigger-text-color: var(--text-primary);
}

// MatChip
.mat-mdc-chip {
  --mdc-chip-elevated-container-color: var(--bg-elevated);
  --mdc-chip-label-text-color: var(--text-secondary);
  --mdc-chip-outline-color: var(--border);
  --mdc-chip-label-text-font: var(--font-body);
}

// MatProgressBar
.mat-mdc-progress-bar {
  --mdc-linear-progress-active-indicator-color: var(--accent);
  --mdc-linear-progress-track-color: var(--bg-hover);
  border-radius: 4px;
}

// === Inverted Submit Button ===

.dark .submit-btn.mat-mdc-unelevated-button {
  --mdc-filled-button-container-color: var(--accent);
  --mdc-filled-button-label-text-color: #fff;
}
html:not(.dark) .submit-btn.mat-mdc-unelevated-button {
  --mdc-filled-button-container-color: var(--accent);
  --mdc-filled-button-label-text-color: #fff;
}
.submit-btn.mat-mdc-unelevated-button {
  border-radius: 10px;
  font-family: var(--font-body);
  font-weight: 600;
  letter-spacing: var(--tracking-normal);
  transition: filter 0.15s ease, transform 0.1s ease;
}
.submit-btn.mat-mdc-unelevated-button:hover:not(:disabled) {
  filter: brightness(1.12);
}
.submit-btn.mat-mdc-unelevated-button:active:not(:disabled) {
  transform: scale(0.98);
}
.submit-btn.mat-mdc-unelevated-button:disabled {
  opacity: 0.4;
}

// === Stats Bar (shared: dashboard + archive) ===

.stats-bar {
  display: flex;
  gap: 0;
  padding: 0;
  background: var(--bg-elevated);
  border: 1px solid var(--border);
  border-radius: 14px;
  margin-bottom: 24px;
  overflow: hidden;
}
.stat {
  display: flex;
  flex-direction: column;
  align-items: center;
  flex: 1;
  padding: 18px 12px;
  border-right: 1px solid var(--border);
  animation: fade-in 0.4s ease-out both;
}
.stat:last-child { border-right: none; }
// Stagger stats
@for $i from 1 through 6 {
  .stat:nth-child(#{$i}) {
    animation-delay: #{($i - 1) * 80}ms;
  }
}
.stat-value {
  font-family: var(--font-mono);
  font-size: var(--text-xl);
  font-weight: 700;
  color: var(--text-primary);
  letter-spacing: var(--tracking-tight);
  font-variant-numeric: tabular-nums;
  line-height: var(--leading-tight);
}
.stat-label {
  font-size: var(--text-xs);
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: var(--tracking-wider);
  margin-top: 4px;
  font-weight: 500;
}

// === Utility: .card ===

.card {
  background: var(--bg-elevated);
  border: 1px solid var(--border);
  border-radius: 14px;
}
```

**Step 2: Commit**

```bash
git add web/src/styles/_surfaces.scss
git commit -m "feat(m8): add surfaces partial with Material overrides [Track A]"
```

---

### Task 5: Create `_layout.scss`

**Files:**
- Create: `web/src/styles/_layout.scss`

**Step 1: Create the layout partial**

```scss
// web/src/styles/_layout.scss
// Global layout utilities, scrollbar, focus ring, transitions.

// === Focus Visible ===

:focus-visible {
  outline: none;
  box-shadow: var(--shadow-glow);
}

// === Global transitions ===

a, button, input, select, textarea {
  transition: all 0.15s ease;
}

// === Scrollbar ===

::-webkit-scrollbar {
  width: 6px;
  height: 6px;
}

::-webkit-scrollbar-track {
  background: transparent;
}

::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.08);
  border-radius: 3px;
}

::-webkit-scrollbar-thumb:hover {
  background: rgba(255, 255, 255, 0.14);
}

html:not(.dark) ::-webkit-scrollbar-thumb {
  background: rgba(0, 0, 0, 0.1);
}

html:not(.dark) ::-webkit-scrollbar-thumb:hover {
  background: rgba(0, 0, 0, 0.2);
}

// === Responsive ===

@media (max-width: 640px) {
  .stat { padding: 14px 8px; }
  .stat-value { font-size: 1.25rem; }
}
```

**Step 2: Commit**

```bash
git add web/src/styles/_layout.scss
git commit -m "feat(m8): add layout partial [Track A]"
```

---

### Task 6: Rewrite entry stylesheet + update config

**Files:**
- Create: `web/src/styles/styles.scss` (new entry point)
- Delete: `web/src/styles.scss` (old entry)
- Modify: `web/angular.json:54` (styles path)
- Modify: `web/src/index.html:11` (Google Fonts URL)

**Step 1: Create the new entry stylesheet**

```scss
// web/src/styles/styles.scss
// Entry point — imports all partials + Material M3 theme + base reset.

@use '@angular/material' as mat;
@use './tokens';
@use './typography';
@use './animations';
@use './surfaces';
@use './layout';

// === Angular Material M3 Theme ===

html.dark {
  @include mat.theme((
    color: (
      primary: mat.$violet-palette,
      tertiary: mat.$violet-palette,
      theme-type: dark,
    ),
    typography: Plus Jakarta Sans,
    density: 0,
  ));

  @include mat.theme-overrides((
    surface: #141418,
    surface-container: #141418,
    surface-container-low: #0e0e12,
    surface-container-high: #1C1C22,
    surface-container-highest: #24242C,
    surface-dim: #0C0C0E,
    on-surface: #F4F4F5,
    on-surface-variant: #A1A1AA,
    outline: rgba(255, 255, 255, 0.10),
    outline-variant: rgba(255, 255, 255, 0.06),
  ));
}

html:not(.dark) {
  @include mat.theme((
    color: (
      primary: mat.$violet-palette,
      tertiary: mat.$violet-palette,
      theme-type: light,
    ),
    typography: Plus Jakarta Sans,
    density: 0,
  ));

  @include mat.theme-overrides((
    surface: #FFFFFF,
    surface-container: #FFFFFF,
    surface-container-low: #FAFAFA,
    surface-container-high: #F4F4F5,
    surface-container-highest: #E4E4E7,
    surface-dim: #F4F4F5,
    on-surface: #09090B,
    on-surface-variant: #52525B,
    outline: rgba(0, 0, 0, 0.10),
    outline-variant: rgba(0, 0, 0, 0.06),
  ));
}

// === Reset & Base ===

*, *::before, *::after {
  box-sizing: border-box;
}

html {
  transition: background-color 0.4s, color 0.3s;
}

html, body {
  margin: 0;
  padding: 0;
  background: var(--bg-base);
  color: var(--text-secondary);
  font-family: var(--font-body);
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  line-height: var(--leading-normal);
}
```

**Step 2: Delete old styles.scss**

```bash
rm web/src/styles.scss
```

**Step 3: Update angular.json styles path**

In `web/angular.json`, change line 55:
```json
// OLD:
"styles": ["src/styles.scss"]
// NEW:
"styles": ["src/styles/styles.scss"]
```

**Step 4: Update index.html — replace fonts**

In `web/src/index.html`, replace the Google Fonts `<link>` (line 11):
```html
<!-- OLD: -->
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@400;500&family=Space+Grotesk:wght@600;700&display=swap" rel="stylesheet">
<!-- NEW: -->
<link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;700;800&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
```

**Step 5: Verify build compiles**

```bash
cd web && npx ng build 2>&1 | head -20
```

Expected: Build succeeds with no SCSS errors. If errors, fix imports/paths.

**Step 6: Commit**

```bash
git add web/src/styles/ web/angular.json web/src/index.html
git rm web/src/styles.scss
git commit -m "feat(m8): restructure stylesheet entry + update fonts to Plus Jakarta Sans [Track A]"
```

---

### Task 7: Add route transitions

**Files:**
- Modify: `web/src/app/app.config.ts:2,12` (add withViewTransitions import + usage)

**Step 1: Update app.config.ts**

Add `withViewTransitions` to the import from `@angular/router` and pass it to `provideRouter`:

```typescript
import { ApplicationConfig, provideBrowserGlobalErrorListeners } from '@angular/core';
import { provideRouter, withViewTransitions } from '@angular/router';
import { provideHttpClient, withInterceptors } from '@angular/common/http';
import { provideAnimationsAsync } from '@angular/platform-browser/animations/async';
import { provideHighcharts } from 'highcharts-angular';
import { routes } from './app.routes';
import { authInterceptor } from './interceptors/auth.interceptor';

export const appConfig: ApplicationConfig = {
  providers: [
    provideBrowserGlobalErrorListeners(),
    provideRouter(routes, withViewTransitions()),
    provideHttpClient(withInterceptors([authInterceptor])),
    provideAnimationsAsync(),
    provideHighcharts(),
  ],
};
```

**Step 2: Verify build**

```bash
cd web && npx ng build 2>&1 | head -20
```

**Step 3: Commit**

```bash
git add web/src/app/app.config.ts
git commit -m "feat(m8): add View Transitions API for route animations"
```

---

### Task 8: Redesign App Shell (navbar)

**Files:**
- Modify: `web/src/app/app.ts` (styles section only, minimal template change)

**Step 1: Replace the styles block in app.ts**

Keep template identical (all E2E selectors preserved: `.navbar`, nav links with `routerLink`, `text=Salir`, `text=AI News Platform`). Only update the `styles` array:

```scss
:host {
  display: block;
  font-family: var(--font-body);
  color: var(--text-secondary);
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}

.navbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 28px;
  height: 52px;
  background: color-mix(in srgb, var(--bg-surface) 80%, transparent);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  border-bottom: 1px solid var(--border);
  position: sticky;
  top: 0;
  z-index: 100;
}

.nav-brand {
  font-family: var(--font-heading);
  font-weight: 800;
  font-size: var(--text-base);
  letter-spacing: var(--tracking-tight);
  color: var(--text-primary);
}

.nav-links {
  display: flex;
  align-items: center;
  gap: 2px;
}

.nav-links a.mat-mdc-button {
  color: var(--text-muted);
  font-size: var(--text-sm);
  font-weight: 500;
  padding: 6px 14px;
  min-width: auto;
  letter-spacing: var(--tracking-normal);
  position: relative;
  --mdc-text-button-label-text-color: var(--text-muted);
  --mdc-text-button-hover-label-text-color: var(--text-primary);
}

.nav-links a.mat-mdc-button::after {
  content: '';
  position: absolute;
  bottom: 4px;
  left: 50%;
  transform: translateX(-50%);
  width: 0;
  height: 2px;
  border-radius: 1px;
  background: var(--accent);
  transition: width 0.2s ease;
}

.nav-links a.mat-mdc-button:hover {
  color: var(--text-primary);
}

.nav-links a.mat-mdc-button:hover::after {
  width: 16px;
}

.nav-links a.mat-mdc-button.active {
  color: var(--text-primary);
  font-weight: 600;
  --mdc-text-button-label-text-color: var(--text-primary);
}

.nav-links a.mat-mdc-button.active::after {
  width: 20px;
}

.theme-toggle {
  color: var(--text-muted);
  margin-left: 4px;
  --mdc-icon-button-icon-color: var(--text-muted);
  transition: color 0.15s ease, transform 0.3s ease;
}

.theme-toggle:hover {
  color: var(--text-primary);
  --mdc-icon-button-icon-color: var(--text-primary);
  transform: rotate(15deg);
}

.logout-btn {
  color: var(--text-muted);
  font-size: var(--text-sm);
  font-weight: 500;
  margin-left: 4px;
  --mdc-text-button-label-text-color: var(--text-muted);
  --mdc-text-button-hover-label-text-color: var(--text-primary);
}

.logout-btn:hover {
  color: var(--text-primary);
}

.hamburger {
  display: none;
  color: var(--text-primary);
  --mdc-icon-button-icon-color: var(--text-primary);
}

main.with-nav {
  max-width: 1120px;
  margin: 0 auto;
  padding: 40px 32px;
}

@media (max-width: 640px) {
  .navbar {
    padding: 0 16px;
    height: 48px;
  }
  .nav-brand { font-size: 0.875rem; }
  .hamburger { display: inline-flex; }
  .nav-links {
    display: none;
    position: absolute;
    top: 48px;
    left: 0;
    right: 0;
    background: var(--bg-surface);
    border-bottom: 1px solid var(--border);
    flex-direction: column;
    padding: 8px 16px 12px;
    gap: 2px;
    z-index: 99;
    backdrop-filter: blur(12px);
  }
  .nav-links.open { display: flex; }
  .nav-links a.mat-mdc-button {
    font-size: var(--text-sm);
    padding: 10px 16px;
    width: 100%;
    justify-content: flex-start;
  }
  .nav-links a.mat-mdc-button::after { display: none; }
  .nav-links a.mat-mdc-button.active::after { display: none; }
  .logout-btn { font-size: var(--text-sm); padding: 10px 16px; text-align: left; }
  .theme-toggle { margin: 4px 16px; }
  main.with-nav { padding: 24px 16px; }
}
```

**Step 2: Verify build**

```bash
cd web && npx ng build 2>&1 | head -20
```

**Step 3: Commit**

```bash
git add web/src/app/app.ts
git commit -m "feat(m8): redesign app shell navbar with glass effect + animated underlines"
```

---

### Task 9: Redesign Login page

**Files:**
- Modify: `web/src/app/pages/login.ts` (styles only)

**Step 1: Replace the styles block in login.ts**

Template stays identical (preserves: `h1` with "AI News Platform", `#password`, `button[type='submit']`, `text=Contrasena incorrecta`, `text=Error de conexion`).

New styles:

```scss
:host {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 100vh;
  background: var(--bg-base);
  position: relative;
  overflow: hidden;
}

// Gradient mesh background
:host::before {
  content: '';
  position: absolute;
  top: -40%;
  right: -20%;
  width: 600px;
  height: 600px;
  background: radial-gradient(circle, var(--accent-glow) 0%, transparent 70%);
  pointer-events: none;
}

:host::after {
  content: '';
  position: absolute;
  bottom: -30%;
  left: -10%;
  width: 500px;
  height: 500px;
  background: radial-gradient(circle, var(--accent-glow) 0%, transparent 70%);
  pointer-events: none;
}

.login-container {
  width: 100%;
  max-width: 400px;
  padding: 24px;
  position: relative;
  z-index: 1;
}

.login-card {
  padding: 52px 44px;
  border-radius: 16px !important;
  border: 1px solid var(--border-hover) !important;
  animation: scale-in 0.5s ease-out both;
}

h1 {
  margin: 0 0 8px;
  font-family: var(--font-heading);
  font-size: var(--text-2xl);
  font-weight: 800;
  text-align: center;
  letter-spacing: var(--tracking-tight);
  color: var(--text-primary);
  line-height: var(--leading-tight);
}

.subtitle {
  margin: 0 0 36px;
  color: var(--text-muted);
  font-size: var(--text-base);
  text-align: center;
  font-weight: 400;
}

.error {
  background: var(--error-subtle);
  color: #f87171;
  padding: 12px 16px;
  border-radius: 10px;
  border: 1px solid rgba(239, 68, 68, 0.15);
  font-size: 0.875rem;
  margin-bottom: 20px;
  font-weight: 500;
}

.full-width {
  width: 100%;
}

mat-form-field.full-width {
  margin-bottom: 8px;
}

button.submit-btn {
  height: 52px;
  font-size: var(--text-base);
  font-weight: 600;
  letter-spacing: var(--tracking-normal);
  font-family: var(--font-body);
  border-radius: 10px;
}

@media (max-width: 640px) {
  .login-container { padding: 16px; }
  .login-card { padding: 40px 28px; }
  :host::before, :host::after { display: none; }
}
```

**Step 2: Verify build**

```bash
cd web && npx ng build 2>&1 | head -20
```

**Step 3: Commit**

```bash
git add web/src/app/pages/login.ts
git commit -m "feat(m8): redesign login with gradient mesh + scale-in animation"
```

---

### Task 10: Redesign News Item Card

**Files:**
- Modify: `web/src/app/components/news-item-card.ts` (styles only)

**Step 1: Replace the styles block**

Template stays identical (preserves: `article`, `app-news-item-card`, `.source-badge[data-source]`, `.topic-badge`, `.trending`, `a[target='_blank']`).

New styles:

```scss
:host { display: block; }
article { display: block; }

.news-item {
  transition: border-color 0.2s ease, box-shadow 0.2s ease, transform 0.2s ease,
    background 0.2s ease;
}

.news-item:hover {
  border-color: var(--border-accent) !important;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.12), 0 0 0 1px var(--border-accent);
  transform: translateY(-2px);
}

mat-card-content {
  padding: 24px;
}

.item-header {
  display: flex;
  gap: 8px;
  align-items: center;
  margin-bottom: 12px;
  flex-wrap: wrap;
}

.source-badge {
  font-size: var(--text-xs);
  padding: 3px 10px;
  border-radius: 6px;
  font-weight: 600;
  letter-spacing: var(--tracking-wide);
  background: rgba(255, 255, 255, 0.06);
  color: var(--text-secondary);
}
.source-badge[data-source="hackernews"] { background: rgba(255, 102, 0, 0.12); color: #fb923c; }
.source-badge[data-source="arxiv"] { background: rgba(185, 28, 28, 0.12); color: #f87171; }
.source-badge[data-source="reddit"] { background: rgba(255, 69, 0, 0.12); color: #fb923c; }
.source-badge[data-source="rss"] { background: rgba(245, 158, 11, 0.12); color: #fbbf24; }
.source-badge[data-source="github"] { background: rgba(255, 255, 255, 0.06); color: var(--text-secondary); }
.source-badge[data-source="huggingface"] { background: rgba(255, 204, 0, 0.12); color: #fbbf24; }

.score {
  font-family: var(--font-mono);
  font-size: 0.75rem;
  color: var(--text-muted);
  font-weight: 400;
  font-variant-numeric: tabular-nums;
}

.topic-badge {
  --mdc-chip-elevated-container-color: var(--accent-glow);
  --mdc-chip-label-text-color: var(--accent);
  --mdc-chip-container-height: 22px;
  --mdc-chip-label-text-size: var(--text-xs);
  font-weight: 500;
}

.trending {
  font-size: var(--text-xs);
  padding: 3px 10px;
  border-radius: 6px;
  background: rgba(250, 204, 21, 0.1);
  color: #facc15;
  font-weight: 600;
}

h2 {
  margin: 0 0 8px;
  font-family: var(--font-heading);
  font-size: var(--text-lg);
  line-height: var(--leading-snug);
  letter-spacing: var(--tracking-tight);
  font-weight: 700;
}

h2 a {
  color: var(--text-primary);
  text-decoration: none;
  background-image: linear-gradient(var(--text-primary), var(--text-primary));
  background-size: 0% 1px;
  background-position: left bottom;
  background-repeat: no-repeat;
  transition: background-size 0.25s ease;
}

h2 a:hover {
  background-size: 100% 1px;
}

.summary {
  margin: 0 0 14px;
  color: var(--text-secondary);
  font-size: var(--text-base);
  line-height: var(--leading-relaxed);
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.item-meta {
  display: flex;
  gap: 12px;
  font-family: var(--font-mono);
  color: var(--text-muted);
  font-size: 0.75rem;
  padding-top: 12px;
  border-top: 1px solid var(--border);
}
```

**Step 2: Verify build**

```bash
cd web && npx ng build 2>&1 | head -20
```

**Step 3: Commit**

```bash
git add web/src/app/components/news-item-card.ts
git commit -m "feat(m8): redesign news card with hover glow + animated underline titles"
```

---

### Task 11: Redesign Dashboard

**Files:**
- Modify: `web/src/app/pages/dashboard.ts` (styles only)

**Step 1: Replace the styles block**

Template stays identical (preserves: `.stats-bar`, `.topic-chip`, `mat-chip-listbox`, `app-news-item-card`, `text=Distribucion por tema`, `text=No hay noticias disponibles hoy`).

New styles:

```scss
:host { display: block; }

.loading-bar { margin-bottom: 24px; }

.error, .empty {
  padding: 32px;
  text-align: center;
  border-radius: 14px;
  margin: 24px 0;
  font-size: var(--text-base);
}
.error {
  background: var(--error-subtle);
  color: #f87171;
  border: 1px solid rgba(239, 68, 68, 0.15);
}
.empty {
  background: var(--bg-elevated);
  color: var(--text-muted);
  border: 1px solid var(--border);
}

.topic-summary { margin-bottom: 24px; }
.topic-summary h3 {
  margin: 0 0 12px;
  font-size: var(--text-xs);
  color: var(--text-muted);
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: var(--tracking-wider);
}

.topic-chips-row {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.topic-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.topic-chip {
  --mdc-chip-elevated-container-color: var(--bg-elevated);
  --mdc-chip-label-text-color: var(--text-secondary);
  --mdc-chip-outline-color: var(--border);
  --mdc-chip-label-text-font: var(--font-body);
  --mdc-chip-label-text-size: var(--text-sm);
  border: 1px solid var(--border);
  border-radius: 980px;
  transition: border-color 0.15s ease, background 0.15s ease;
}

.topic-chip.mat-mdc-chip-selected {
  --mdc-chip-elevated-selected-container-color: var(--accent);
  --mdc-chip-selected-label-text-color: #fff;
  border-color: transparent;
}

:host-context(html:not(.dark)) .topic-chip.mat-mdc-chip-selected {
  --mdc-chip-elevated-selected-container-color: var(--accent);
  --mdc-chip-selected-label-text-color: #fff;
}

.topic-chip strong {
  margin-left: 4px;
  font-weight: 600;
  color: var(--text-muted);
}
.topic-chip.mat-mdc-chip-selected strong { color: inherit; opacity: 0.7; }

.clear-filter {
  color: var(--accent);
  font-size: var(--text-sm);
  font-weight: 500;
  --mdc-text-button-label-text-color: var(--accent);
}

.count-label {
  color: var(--text-muted);
  margin-bottom: 16px;
  font-size: 0.875rem;
  font-weight: 500;
}

.news-list {
  display: flex;
  flex-direction: column;
  gap: 14px;
}
```

**Step 2: Verify build + commit**

```bash
cd web && npx ng build 2>&1 | head -20
git add web/src/app/pages/dashboard.ts
git commit -m "feat(m8): redesign dashboard with accent chips + refined spacing"
```

---

### Task 12: Redesign Archive

**Files:**
- Modify: `web/src/app/pages/archive.ts` (styles only)

**Step 1: Replace the styles block**

Template stays identical (preserves: `#archive-date`, `.stats-bar`, `text=No hay noticias para esta fecha`, `text=No hay briefing para esta fecha`, `text=Extraidas`, `app-news-item-card`, `.topic-chip`).

New styles:

```scss
:host { display: block; }

.controls {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  margin-bottom: 8px;
}
.control-field { min-width: 180px; }

.loading-bar { margin-bottom: 24px; }

.error, .empty {
  padding: 32px;
  text-align: center;
  border-radius: 14px;
  margin: 24px 0;
  font-size: var(--text-base);
}
.error {
  background: var(--error-subtle);
  color: #f87171;
  border: 1px solid rgba(239, 68, 68, 0.15);
}
.empty {
  background: var(--bg-elevated);
  color: var(--text-muted);
  border: 1px solid var(--border);
}

.topic-summary { margin-bottom: 24px; }
.topic-summary h3 {
  margin: 0 0 12px;
  font-size: var(--text-xs);
  color: var(--text-muted);
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: var(--tracking-wider);
}

.topic-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.topic-chip {
  font-size: var(--text-sm);
  padding: 5px 14px;
  border-radius: 980px;
  background: var(--bg-elevated);
  border: 1px solid var(--border);
  color: var(--text-secondary);
}
.topic-chip strong { margin-left: 4px; color: var(--text-muted); }

.count-label {
  color: var(--text-muted);
  margin-bottom: 16px;
  font-size: 0.875rem;
  font-weight: 500;
}

.news-list {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

@media (max-width: 640px) {
  .controls { flex-wrap: wrap; }
  .control-field { width: 100%; min-width: 0; }
}
```

**Step 2: Verify build + commit**

```bash
cd web && npx ng build 2>&1 | head -20
git add web/src/app/pages/archive.ts
git commit -m "feat(m8): redesign archive page"
```

---

### Task 13: Redesign Search

**Files:**
- Modify: `web/src/app/pages/search.ts` (styles only)

**Step 1: Replace the styles block**

Template stays identical (preserves: `.search-input`, `.search-btn`, `#topic-select`, `#date-from`, `#date-to`, `text=resultados para`, `text=No se encontraron resultados`, `app-news-item-card`).

New styles:

```scss
:host { display: block; }

.search-form { margin-bottom: 8px; }

.search-row {
  display: flex;
  gap: 10px;
  align-items: flex-start;
}

.search-field { flex: 1; }

.search-btn {
  height: 56px;
  padding: 0 28px;
  font-size: var(--text-sm);
  font-weight: 600;
  letter-spacing: var(--tracking-normal);
  font-family: var(--font-body);
  border-radius: 10px;
}

.filters {
  display: flex;
  gap: 14px;
  flex-wrap: wrap;
}
.filter-field { min-width: 140px; }

.loading-bar { margin-bottom: 24px; }

.error, .empty {
  padding: 32px;
  text-align: center;
  border-radius: 14px;
  margin: 24px 0;
  font-size: var(--text-base);
}
.error {
  background: var(--error-subtle);
  color: #f87171;
  border: 1px solid rgba(239, 68, 68, 0.15);
}
.empty {
  background: var(--bg-elevated);
  color: var(--text-muted);
  border: 1px solid var(--border);
}

.count-label {
  color: var(--text-muted);
  margin-bottom: 16px;
  font-size: 0.875rem;
  font-weight: 500;
}

.news-list {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

@media (max-width: 640px) {
  .search-row { flex-direction: column; }
  .search-field { width: 100%; }
  .search-btn { width: 100%; height: 48px; }
  .filters { flex-direction: column; }
  .filter-field { width: 100%; min-width: 0; }
}
```

**Step 2: Verify build + commit**

```bash
cd web && npx ng build 2>&1 | head -20
git add web/src/app/pages/search.ts
git commit -m "feat(m8): redesign search page"
```

---

### Task 14: Redesign Chat

**Files:**
- Modify: `web/src/app/pages/chat.ts` (styles only)

**Step 1: Replace the styles block**

Template stays identical (preserves: `.empty-state`, `.suggestion-chip`, `.message.user`, `.message.assistant`, `.chat-input`, `.send-btn`, `.topic-filter`, `.source-link`, `text=Chat con IA`).

New styles:

```scss
:host { display: block; height: calc(100vh - 104px); }

.chat-page {
  display: flex;
  flex-direction: column;
  height: 100%;
  max-width: 720px;
  margin: 0 auto;
}

.chat-messages {
  flex: 1;
  overflow-y: auto;
  padding: 24px 0;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.empty-state {
  text-align: center;
  padding: 80px 24px;
  animation: fade-in 0.5s ease-out both;
}

.empty-state h2 {
  font-family: var(--font-heading);
  font-size: var(--text-xl);
  color: var(--text-primary);
  margin: 0 0 8px;
  font-weight: 800;
  letter-spacing: var(--tracking-tight);
}

.empty-state p {
  margin: 0 0 36px;
  font-size: var(--text-base);
  color: var(--text-muted);
}

.suggestions {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
  max-width: 480px;
  margin: 0 auto;
}

.suggestion-chip {
  cursor: pointer;
  --mdc-chip-elevated-container-color: var(--bg-elevated);
  --mdc-chip-label-text-color: var(--text-secondary);
  --mdc-chip-outline-color: var(--border);
  border: 1px solid var(--border);
  border-radius: 12px;
  transition: border-color 0.15s ease, background 0.15s ease;
}

.suggestion-chip:hover {
  border-color: var(--accent);
  --mdc-chip-elevated-container-color: var(--accent-glow);
}

.message {
  padding: 14px 18px;
  border-radius: 18px;
  max-width: 82%;
  line-height: var(--leading-relaxed);
  font-size: var(--text-base);
  animation: fade-in 0.3s ease-out both;
}

.message.user {
  align-self: flex-end;
  background: var(--accent);
  color: #fff;
  border-bottom-right-radius: 6px;
  white-space: pre-wrap;
}

.message.assistant {
  align-self: flex-start;
  background: var(--bg-elevated);
  border: 1px solid var(--border);
  color: var(--text-secondary);
  border-bottom-left-radius: 6px;
}

.message-content { word-break: break-word; }
.message.assistant .message-content :first-child { margin-top: 0; }
.message.assistant .message-content :last-child { margin-bottom: 0; }
.message.assistant .message-content p { margin: 0.5em 0; }

.message.assistant .message-content ul,
.message.assistant .message-content ol {
  margin: 0.5em 0;
  padding-left: 1.5em;
}

.message.assistant .message-content code {
  background: var(--bg-base);
  border: 1px solid var(--border);
  padding: 2px 6px;
  border-radius: 5px;
  font-family: var(--font-mono);
  font-size: 0.85em;
}

.message.assistant .message-content pre {
  background: var(--bg-base);
  border: 1px solid var(--border);
  color: var(--text-primary);
  padding: 16px 18px;
  border-radius: 12px;
  overflow-x: auto;
  margin: 0.5em 0;
}

.message.assistant .message-content pre code {
  background: none;
  border: none;
  padding: 0;
  color: inherit;
}

.message.assistant .message-content strong {
  font-weight: 600;
  color: var(--text-primary);
}

.message.assistant .message-content a {
  color: var(--accent);
  text-decoration: none;
}

.message.assistant .message-content a:hover {
  text-decoration: underline;
}

.cursor {
  animation: blink 0.8s infinite;
  font-weight: bold;
  color: var(--accent);
}

.sources {
  margin-top: 12px;
  padding-top: 10px;
  border-top: 1px solid var(--border);
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  align-items: center;
}

.sources-label {
  font-size: var(--text-xs);
  font-weight: 600;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: var(--tracking-wide);
}

.source-link {
  font-size: var(--text-sm);
  padding: 3px 10px;
  background: var(--bg-hover);
  color: var(--text-secondary);
  border: 1px solid var(--border);
  border-radius: 6px;
  text-decoration: none;
  transition: border-color 0.15s ease;
}

.source-link:hover {
  border-color: var(--accent);
}

.source-link.no-url { color: var(--text-muted); }

.chat-input-form {
  padding: 16px 0;
  border-top: 1px solid var(--border);
}

.input-row {
  display: flex;
  gap: 8px;
  align-items: flex-start;
}

.topic-field { min-width: 140px; }
.chat-field { flex: 1; }

.send-btn {
  height: 56px;
  padding: 0 24px;
  font-size: var(--text-sm);
  font-weight: 600;
  font-family: var(--font-body);
  border-radius: 10px;
}

@media (max-width: 640px) {
  :host { height: calc(100vh - 80px); }
  .suggestions { grid-template-columns: 1fr; }
  .input-row { flex-wrap: wrap; }
  .topic-field { min-width: 100%; }
  .chat-field { min-width: 0; flex: 1; }
  .send-btn { height: 48px; }
  .message { max-width: 92%; }
}
```

**Step 2: Verify build + commit**

```bash
cd web && npx ng build 2>&1 | head -20
git add web/src/app/pages/chat.ts
git commit -m "feat(m8): redesign chat with accent user bubbles + 2x2 suggestion grid"
```

---

### Task 15: Redesign Analytics

**Files:**
- Modify: `web/src/app/pages/analytics.ts` (styles + Highcharts theme object)

**Step 1: Replace the styles block + update darkTheme**

Template stays identical (preserves: `text=Items por dia`, `text=Distribucion por tema`, `text=Fuentes`).

New styles:

```scss
:host { display: block; }

.loading-bar { margin-bottom: 24px; }

.error {
  padding: 32px;
  text-align: center;
  border-radius: 14px;
  margin: 24px 0;
  font-size: var(--text-base);
  background: var(--error-subtle);
  color: #f87171;
  border: 1px solid rgba(239, 68, 68, 0.15);
}

.chart-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 20px;
}

.full-width { grid-column: 1 / -1; }

.chart-card mat-card-content { padding: 24px; }

.chart-card h3 {
  margin: 0 0 16px;
  font-size: var(--text-xs);
  color: var(--text-muted);
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: var(--tracking-wider);
}

@media (max-width: 640px) {
  .chart-grid { grid-template-columns: 1fr; }
}
```

**Step 2: Update the `darkTheme` object in the TS class**

Replace the `darkTheme` property with updated colors (accent indigo for line, updated greys):

```typescript
private darkTheme: Partial<Highcharts.Options> = {
  chart: {
    backgroundColor: 'transparent',
    style: { fontFamily: "'Plus Jakarta Sans', sans-serif" },
  },
  xAxis: {
    labels: { style: { color: '#52525B' } },
    gridLineColor: 'rgba(255,255,255,0.04)',
    lineColor: 'rgba(255,255,255,0.06)',
    tickColor: 'rgba(255,255,255,0.06)',
  },
  yAxis: {
    labels: { style: { color: '#52525B' } },
    gridLineColor: 'rgba(255,255,255,0.04)',
    title: { style: { color: '#52525B' } },
  },
  legend: {
    itemStyle: { color: '#A1A1AA' },
    itemHoverStyle: { color: '#F4F4F5' },
  },
  tooltip: {
    backgroundColor: '#1C1C22',
    borderColor: 'rgba(255,255,255,0.1)',
    style: { color: '#F4F4F5' },
  },
};
```

**Step 3: Update `itemsPerDayOptions` series color**

Change the series color from `'#ffffff'` to `'#6366F1'` (the accent color):

```typescript
series: [{ type: 'line', name: 'Items', data: data.map(d => d.count), color: '#6366F1' }],
```

**Step 4: Update `topicOptions` greyPalette**

Replace the grey palette with accent-influenced shades:

```typescript
const indigoPalette = ['#6366F1', '#818CF8', '#A5B4FC', '#C7D2FE', '#A1A1AA', '#71717A', '#52525B'];
```

And use `indigoPalette` instead of `greyPalette`.

**Step 5: Update `topicOptions` pie borderColor**

Change the pie borderColor from `'#111113'` to `'#141418'` (new bg-surface):

```typescript
borderColor: '#141418',
```

**Step 6: Verify build + commit**

```bash
cd web && npx ng build 2>&1 | head -20
git add web/src/app/pages/analytics.ts
git commit -m "feat(m8): redesign analytics with indigo accent charts"
```

---

### Task 16: Run E2E tests

**Files:** None (verification only)

**Step 1: Build the frontend**

```bash
cd web && npx ng build
```

Expected: Successful build under 1.5MB budget.

**Step 2: Run E2E tests**

```bash
cd /home/paul/Documentos/proyectos/backend/ai-news-platform
python -m pytest tests/e2e/ -v --timeout=60
```

Expected: All E2E tests pass. If any fail:

1. Read the failing test to identify which selector broke
2. Check the E2E constraints cheatsheet at the top of this plan
3. Fix the missing class/id/text in the corresponding component
4. Re-run the specific failing test to verify fix

**Step 3: Commit any E2E fixes**

```bash
git add web/src/app/
git commit -m "fix(m8): fix E2E selector regressions from design overhaul"
```

---

### Task 17: Update AGENTS.md

**Files:**
- Modify: `AGENTS.md` (update design system section and M8 status)

**Step 1: Update the design system references in AGENTS.md**

Add/update the following information:
- Stylesheet structure: `web/src/styles/` directory with 5 partials + entry
- Font change: Plus Jakarta Sans (heading + body), JetBrains Mono (mono)
- Color palette: Electric Indigo accent (#6366F1 dark / #4F46E5 light)
- Token rename mapping: `--bg-surface-hover` → `--bg-hover`, `--text-tertiary` → `--text-muted`, `--accent-subtle` → `--accent-glow`
- New tokens: `--bg-elevated`, `--accent-dim`, `--border-accent`, `--shadow-*`
- Route transitions: View Transitions API via `withViewTransitions()`
- M8 key decisions: Design System First, single font family, accent color change

**Step 2: Commit**

```bash
git add AGENTS.md
git commit -m "docs(m8): update AGENTS.md with design overhaul state"
```

---

## Summary

> **Status: COMPLETE** — All 17 tasks implemented and merged to main on 2026-02-19. 35/35 E2E tests pass.

| Task | Description | Files | Status |
|------|-------------|-------|--------|
| 1 | Create `_tokens.scss` | NEW: `web/src/styles/_tokens.scss` | Done |
| 2 | Create `_typography.scss` | NEW: `web/src/styles/_typography.scss` | Done |
| 3 | Create `_animations.scss` | NEW: `web/src/styles/_animations.scss` | Done |
| 4 | Create `_surfaces.scss` | NEW: `web/src/styles/_surfaces.scss` | Done |
| 5 | Create `_layout.scss` | NEW: `web/src/styles/_layout.scss` | Done |
| 6 | Rewrite entry + config | NEW: `web/src/styles/styles.scss`, DEL: `web/src/styles.scss`, MOD: `angular.json`, `index.html` | Done |
| 7 | Route transitions | MOD: `web/src/app/app.config.ts` | Done |
| 8 | App Shell navbar | MOD: `web/src/app/app.ts` | Done |
| 9 | Login page | MOD: `web/src/app/pages/login.ts` | Done |
| 10 | News Item Card | MOD: `web/src/app/components/news-item-card.ts` | Done |
| 11 | Dashboard | MOD: `web/src/app/pages/dashboard.ts` | Done |
| 12 | Archive | MOD: `web/src/app/pages/archive.ts` | Done |
| 13 | Search | MOD: `web/src/app/pages/search.ts` | Done |
| 14 | Chat | MOD: `web/src/app/pages/chat.ts` | Done |
| 15 | Analytics | MOD: `web/src/app/pages/analytics.ts` | Done |
| 16 | E2E verification | Verification only | Done (35/35 pass) |
| 17 | AGENTS.md update | MOD: `AGENTS.md` | Done |

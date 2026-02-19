# Design Fixes Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Corregir bugs visuales y mejorar la UX del frontend Angular, cubriendo P0 (bugs que rompen la UI), P1 (problemas de diseño mayores) y P2 (mejoras de UX).

**Architecture:** Todos los cambios son en el frontend Angular 21. Los estilos globales compartidos están en `web/src/styles/`. Los componentes usan inline styles dentro del `@Component`. No se necesita tocar el backend ni la capa de datos mock.

**Tech Stack:** Angular 21, Angular Material 21, Highcharts 12, SCSS (tokens en CSS custom properties), modo mock vía `ng serve --configuration mock`.

**Cómo probar en local:**
```bash
cd web
npm run mock          # levanta en http://localhost:4200 sin backend
```

---

## Task 1: Fix — Stats bar overflow horizontal en mobile

**Contexto:** `.stats-bar` tiene `overflow: hidden` para respetar los border-radius. En mobile (390px), 5 stats con `flex: 1` y labels tipo "DURACION" no caben → el último stat se corta. La solución es añadir scroll horizontal en mobile.

**Archivos:**
- Modify: `web/src/styles/_layout.scss` (bloque `@media (max-width: 640px)`)

**Step 1: Abrir el archivo y localizar el bloque mobile**

```bash
# El bloque ya existe, buscar la línea ~31:
grep -n "640px" web/src/styles/_layout.scss
```

**Step 2: Aplicar el fix**

Reemplazar el bloque `@media (max-width: 640px)` existente:

```scss
@media (max-width: 640px) {
  .stats-bar {
    overflow-x: auto;
    -webkit-overflow-scrolling: touch;
    scrollbar-width: none;           // ocultar scrollbar en Firefox
    &::-webkit-scrollbar { display: none; } // ocultar scrollbar en WebKit
  }
  .stat {
    padding: 12px 10px;
    min-width: 68px;                 // evita que los flex items colapsen
  }
  .stat-value { font-size: 1.125rem; }
  .stat-label {
    font-size: 9px;
    letter-spacing: 0.02em;
  }
}
```

**Step 3: Verificar visualmente**
```bash
cd web && npm run mock
# Abrir DevTools → modo responsive → 390px
# Verificar que los 5 stats son visibles y se puede hacer swipe horizontal
```

**Step 4: Commit**
```bash
git add web/src/styles/_layout.scss
git commit -m "fix(ui): stats bar horizontal scroll en mobile [Track A]"
```

---

## Task 2: Fix — Chat suggestion chips con texto truncado

**Contexto:** Las suggestion chips usan `mat-chip` dentro de un grid `1fr 1fr`. `mat-chip` tiene `overflow: hidden` y `white-space: nowrap` internamente → el texto se corta. La solución más limpia es reemplazar `mat-chip` por un `<button>` nativo con los mismos estilos visuales, evitando sobreescribir internals de Material.

**Archivos:**
- Modify: `web/src/app/pages/chat.ts` (template + styles)

**Step 1: Reemplazar `mat-chip` por `button` en el template**

Localizar en el template de `chat.ts`:
```html
<div class="suggestions">
  @for (s of suggestions; track s) {
    <mat-chip class="suggestion-chip" (click)="askQuestion(s)">{{ s }}</mat-chip>
  }
</div>
```

Reemplazar por:
```html
<div class="suggestions">
  @for (s of suggestions; track s) {
    <button type="button" class="suggestion-chip" (click)="askQuestion(s)">{{ s }}</button>
  }
</div>
```

**Step 2: Actualizar los estilos de `.suggestion-chip`**

Reemplazar el bloque CSS de `.suggestion-chip` en `chat.ts`:
```css
.suggestion-chip {
  cursor: pointer;
  background: var(--bg-elevated);
  color: var(--text-secondary);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 10px 14px;
  font-family: var(--font-body);
  font-size: var(--text-sm);
  font-weight: 400;
  text-align: left;
  width: 100%;
  line-height: var(--leading-relaxed);
  transition: border-color 0.15s ease, background 0.15s ease;
  white-space: normal;
  word-break: break-word;
}

.suggestion-chip:hover {
  border-color: var(--accent);
  background: var(--accent-glow);
  color: var(--text-primary);
}
```

**Step 3: Quitar `MatChipsModule` del import si ya no se usa en el componente**

Verificar que no haya otro `mat-chip` en el template. Si es así, eliminar `MatChipsModule` del array `imports` del `@Component`.

**Step 4: Verificar desktop y mobile**
```bash
cd web && npm run mock
# Desktop 1280px → /chat → chips deben mostrar texto completo en 2 columnas
# Mobile 390px → /chat → chips en 1 columna, texto completo
```

**Step 5: Commit**
```bash
git add web/src/app/pages/chat.ts
git commit -m "fix(chat): reemplazar mat-chip suggestions por button nativo [Track A]"
```

---

## Task 3: Fix — Acentos faltantes en labels de UI

**Contexto:** Labels como "Distribucion", "Duracion", "Regulacion" aparecen sin tilde. Son cadenas hardcodeadas en los templates y estilos.

**Archivos:**
- Modify: `web/src/app/pages/dashboard.ts`
- Modify: `web/src/app/pages/archive.ts`
- Modify: `web/src/app/pages/analytics.ts`
- Modify: `web/src/styles/_surfaces.scss`

**Step 1: Corregir `dashboard.ts`**

Buscar y reemplazar:
- `"Distribucion por tema"` → `"Distribución por tema"`
- `"Extraidas"` → `"Extraídas"`
- `"Filtradas"` → ya correcto
- `"Duracion"` → `"Duración"`
- `"limpiar filtro"` → `"limpiar filtro"` (ya correcto)

**Step 2: Corregir `archive.ts`** (mismos labels de la stats bar)

Aplicar las mismas correcciones: `"Extraidas"` → `"Extraídas"`, `"Duracion"` → `"Duración"`, `"Distribucion por tema"` → `"Distribución por tema"`.

**Step 3: Corregir `analytics.ts`**

- `"Items por dia (ultimos 14 dias)"` → `"Items por día (últimos 14 días)"`
- `"Distribucion por tema"` → `"Distribución por tema"`
- En `yAxis.title.text: 'Items'` → dejar igual (término técnico)

**Step 4: Commit**
```bash
git add web/src/app/pages/dashboard.ts web/src/app/pages/archive.ts web/src/app/pages/analytics.ts
git commit -m "fix(i18n): añadir acentos faltantes en labels de UI [Track A]"
```

---

## Task 4: Fix — Analytics Y-axis rango automático

**Contexto:** El gráfico de línea "Items por día" tiene `min: 0` en el Y-axis. Como los datos están entre ~75 y ~95, la línea aparece comprimida en la parte superior del gráfico, haciendo que las variaciones diarias sean casi invisibles.

**Archivos:**
- Modify: `web/src/app/pages/analytics.ts` (método `itemsPerDayOptions`)

**Step 1: Localizar y eliminar `min: 0`**

En `analytics.ts`, dentro de `itemsPerDayOptions`, en el objeto `yAxis`:
```typescript
yAxis: {
  ...this.darkTheme.yAxis as Highcharts.YAxisOptions,
  title: { text: 'Items', style: { color: '#5a5a6e' } },
  min: 0,    // ← ELIMINAR esta línea
},
```

Reemplazar por:
```typescript
yAxis: {
  ...this.darkTheme.yAxis as Highcharts.YAxisOptions,
  title: { text: 'Items', style: { color: '#5a5a6e' } },
},
```

**Step 2: Verificar visualmente**
```bash
cd web && npm run mock
# Navegar a /analytics
# El gráfico de línea debe ahora mostrar las variaciones con más amplitud vertical
```

**Step 3: Commit**
```bash
git add web/src/app/pages/analytics.ts
git commit -m "fix(analytics): remover min:0 del Y-axis para rango automático [Track A]"
```

---

## Task 5: Feature — Analytics charts reactivos al dark/light mode

**Contexto:** Los charts de Highcharts renderizan SVG con colores hardcodeados en el componente (`darkTheme` es un objeto estático). Al cambiar entre light/dark mode, los charts no se actualizan → en light mode muestran labels casi invisibles (`#52525B` sobre fondo blanco); en dark mode el fondo SVG es correcto pero los labels están demasiado oscuros. La solución es hacer el objeto de tema reactivo usando un `signal` que observa la clase `dark` en `<html>`.

**Archivos:**
- Modify: `web/src/app/pages/analytics.ts`

**Step 1: Añadir signal `isDark` y MutationObserver**

En la clase `AnalyticsPage`, añadir:
```typescript
isDark = signal(document.documentElement.classList.contains('dark'));
private themeObserver?: MutationObserver;
```

En `ngOnInit`, después del subscribe existente, añadir:
```typescript
this.themeObserver = new MutationObserver(() => {
  this.isDark.set(document.documentElement.classList.contains('dark'));
});
this.themeObserver.observe(document.documentElement, { attributeFilter: ['class'] });
```

Añadir `ngOnDestroy`:
```typescript
ngOnDestroy() {
  this.themeObserver?.disconnect();
}
```

**Step 2: Convertir `darkTheme` en `chartTheme` computed**

Eliminar la propiedad `private darkTheme` existente y reemplazarla por:

```typescript
private chartTheme = computed<Partial<Highcharts.Options>>(() => {
  const dark = this.isDark();
  const labelColor = dark ? '#A1A1AA' : '#71717A';
  const gridColor = dark ? 'rgba(255,255,255,0.04)' : 'rgba(0,0,0,0.05)';
  const lineColor = dark ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.08)';
  return {
    chart: {
      backgroundColor: 'transparent',
      style: { fontFamily: "'Plus Jakarta Sans', sans-serif" },
    },
    xAxis: {
      labels: { style: { color: labelColor } },
      gridLineColor: gridColor,
      lineColor,
      tickColor: lineColor,
    },
    yAxis: {
      labels: { style: { color: labelColor } },
      gridLineColor: gridColor,
      title: { style: { color: labelColor } },
    },
    legend: {
      itemStyle: { color: dark ? '#A1A1AA' : '#52525B' },
      itemHoverStyle: { color: dark ? '#F4F4F5' : '#09090B' },
    },
    tooltip: {
      backgroundColor: dark ? '#1C1C22' : '#FFFFFF',
      borderColor: dark ? 'rgba(255,255,255,0.1)' : 'rgba(0,0,0,0.1)',
      style: { color: dark ? '#F4F4F5' : '#09090B' },
    },
  };
});
```

**Step 3: Actualizar referencias de `this.darkTheme` → `this.chartTheme()`**

En cada `computed` de opciones de charts (`itemsPerDayOptions`, `topicOptions`, `sourcesOptions`), reemplazar:
- `...this.darkTheme,` → `...this.chartTheme(),`
- `chart: { ...this.darkTheme.chart, ...` → `chart: { ...this.chartTheme().chart, ...`
- `xAxis: { ...this.darkTheme.xAxis as Highcharts.XAxisOptions,` → `...this.chartTheme().xAxis as Highcharts.XAxisOptions,`
- etc.

**Step 4: Añadir `OnDestroy` al implements**

```typescript
export class AnalyticsPage implements OnInit, OnDestroy {
```

E importar `OnDestroy` de `@angular/core`.

**Step 5: Verificar dark/light switching**
```bash
cd web && npm run mock
# Navegar a /analytics en dark mode → charts legibles
# Cambiar a light mode (icono en navbar) → charts deben actualizarse con colores claros
# Cambiar de vuelta → charts vuelven a dark
```

**Step 6: Commit**
```bash
git add web/src/app/pages/analytics.ts
git commit -m "feat(analytics): charts reactivos al dark/light mode con MutationObserver [Track B]"
```

---

## Task 6: Fix — Light mode card visual weight

**Contexto:** En light mode, las news cards y la stats bar se funden con el fondo blanco `#FAFAFA`. `--bg-elevated: #F4F4F5` apenas contrasta con `--bg-base: #FAFAFA` (diferencia de solo 5 puntos de luminosidad). La solución es mejorar la visibilidad de los bordes y añadir una sombra sutil a las cards en light mode.

**Archivos:**
- Modify: `web/src/styles/_surfaces.scss`
- Modify: `web/src/styles/_tokens.scss`

**Step 1: Reforzar borde en light mode en `_tokens.scss`**

En el bloque `:root`, cambiar:
```scss
// Antes:
--border: rgba(0, 0, 0, 0.06);
--border-hover: rgba(0, 0, 0, 0.10);

// Después:
--border: rgba(0, 0, 0, 0.09);
--border-hover: rgba(0, 0, 0, 0.15);
```

**Step 2: Añadir sombra a MatCard en light mode en `_surfaces.scss`**

En el bloque `.mat-mdc-card`, añadir shadow condicional:
```scss
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

// Sombra sutil en light mode para separar cards del fondo
html:not(.dark) .mat-mdc-card {
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.06), 0 1px 2px rgba(0, 0, 0, 0.04) !important;
}
```

**Step 3: Verificar en ambos modos**
```bash
cd web && npm run mock
# /dashboard en light mode → cards deben verse claramente separadas del fondo
# /analytics en light mode → cards de charts con sombra
# /dashboard en dark mode → sin cambios (box-shadow: none)
```

**Step 4: Commit**
```bash
git add web/src/styles/_surfaces.scss web/src/styles/_tokens.scss
git commit -m "fix(ui): mejorar visibilidad de cards en light mode [Track A]"
```

---

## Task 7: UX — Archive auto-carga el briefing de hoy

**Contexto:** La página Archive arranca completamente vacía. El usuario debe seleccionar manualmente una fecha para ver datos, lo cual no es intuitivo. Al entrar, debería cargar automáticamente el briefing de hoy (igual que hace Dashboard).

**Archivos:**
- Modify: `web/src/app/pages/archive.ts`

**Step 1: Añadir `ngOnInit` a `ArchivePage`**

La clase `ArchivePage` no implementa `OnInit`. Modificar:

```typescript
// Añadir imports
import { Component, inject, signal, computed, OnInit } from '@angular/core';

// Cambiar la clase
export class ArchivePage implements OnInit {
  // ... propiedades existentes ...

  ngOnInit() {
    this.loadBriefing(this.todayStr);
  }
}
```

**Step 2: Verificar que `loadBriefing` es privado y funciona correctamente**

El método `private loadBriefing(date: string)` ya existe y funciona correctamente. Solo se añade la llamada en `ngOnInit`.

**Step 3: Verificar visualmente**
```bash
cd web && npm run mock
# Navegar a /archive
# Debe cargar automáticamente las noticias de hoy sin necesidad de seleccionar fecha
# La fecha seleccionada en el input debe ser hoy (ya lo era por el valor inicial de selectedDate)
```

**Step 4: Commit**
```bash
git add web/src/app/pages/archive.ts
git commit -m "feat(archive): auto-cargar briefing de hoy al inicializar [Track A]"
```

---

## Task 8: UX — Search empty state con orientación

**Contexto:** La página de búsqueda muestra solo el formulario vacío antes de realizar una búsqueda. No hay indicación visual de qué hacer ni sugerencias. Añadir un empty state simple con mensaje e iconos de sugerencia de términos frecuentes.

**Archivos:**
- Modify: `web/src/app/pages/search.ts`

**Step 1: Añadir empty state al template**

Añadir después del bloque `@if (loading())` y antes del bloque de resultados en el template de `search.ts`:

```html
@if (!searched() && !loading()) {
  <div class="search-empty-state">
    <div class="search-empty-icon">🔍</div>
    <p class="search-empty-title">Busca entre las noticias archivadas</p>
    <p class="search-empty-hint">Prueba con: LLM, agentes, open source, GPT-4, Mistral...</p>
  </div>
}
```

**Step 2: Añadir estilos del empty state**

En el bloque `styles` de `search.ts`, añadir:
```css
.search-empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 64px 24px;
  text-align: center;
  animation: fade-in 0.4s ease-out both;
}

.search-empty-icon {
  font-size: 2.5rem;
  margin-bottom: 16px;
  opacity: 0.5;
}

.search-empty-title {
  margin: 0 0 8px;
  font-size: var(--text-base);
  font-weight: 500;
  color: var(--text-secondary);
}

.search-empty-hint {
  margin: 0;
  font-size: var(--text-sm);
  color: var(--text-muted);
  font-family: var(--font-mono);
}
```

**Step 3: Verificar visualmente**
```bash
cd web && npm run mock
# Navegar a /search
# Debe mostrar el empty state con ícono y hint
# Al hacer una búsqueda, el empty state desaparece y aparecen resultados (o "no resultados")
```

**Step 4: Commit**
```bash
git add web/src/app/pages/search.ts
git commit -m "feat(search): añadir empty state con orientación al usuario [Track A]"
```

---

## Task 9: Script — Añadir `npm run mock` a package.json

> **Nota:** Este task ya está completado. Verificar con:

```bash
cat web/package.json | grep mock
# Debe mostrar: "mock": "ng serve --configuration mock"
```

Si no está, añadir a `web/package.json`:
```json
"scripts": {
  "ng": "ng",
  "start": "ng serve",
  "mock": "ng serve --configuration mock",
  "build": "ng build",
  "watch": "ng build --watch --configuration development"
}
```

**Commit (si no estaba):**
```bash
git add web/package.json
git commit -m "feat(dev): añadir script npm run mock para desarrollo sin backend [Track A]"
```

---

## Verificación final

```bash
cd web && npm run mock
# Comprobar en orden:
# 1. /dashboard → stats bar scroll en mobile, acentos, dark/light switch
# 2. /chat → suggestion chips sin truncar en 2x2 desktop y 1 col mobile
# 3. /analytics → charts adaptan colores al cambiar tema, Y-axis con rango auto
# 4. /archive → carga datos de hoy automáticamente
# 5. /search → empty state visible, resultados funcionan
```

---

## Resumen de archivos modificados

| Archivo | Tasks |
|---------|-------|
| `web/src/styles/_layout.scss` | Task 1 (stats bar mobile) |
| `web/src/styles/_surfaces.scss` | Task 6 (light mode cards) |
| `web/src/styles/_tokens.scss` | Task 6 (border opacity) |
| `web/src/app/pages/chat.ts` | Task 2 (chips overflow), Task 3 (acentos) |
| `web/src/app/pages/dashboard.ts` | Task 3 (acentos) |
| `web/src/app/pages/archive.ts` | Task 3 (acentos), Task 7 (auto-load) |
| `web/src/app/pages/analytics.ts` | Task 3 (acentos), Task 4 (Y-axis), Task 5 (dark mode) |
| `web/src/app/pages/search.ts` | Task 8 (empty state) |
| `web/package.json` | Task 9 (script mock) ✅ done |

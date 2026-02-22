# Frontend Visual Redesign with Google Stitch + Claude Code

## Goal

Rediseñar visualmente el frontend Angular de ai-news-platform usando Google Stitch como herramienta de diseño AI y Claude Code como traductor a Angular, logrando una estética premium tipo Linear/Vercel/Raycast sin cambiar el stack base.

## Context

- El frontend actual funciona bien pero tiene un look "genérico" de Angular Material
- El principal bottleneck del desarrollador es "no tener ojo para diseño"
- Pencil.dev (herramienta similar) no soporta Angular
- Google Stitch es gratuito, genera diseños AI de alta calidad, y tiene MCP server para Claude Code

## Architecture

### Workflow

```
[Prompt en Stitch] → [Stitch genera UI variantes] → [Stitch MCP] → [Claude Code lee diseño]
                                                                            ↓
                                                                   [Genera Angular code]
                                                                   (Material funcional +
                                                                    SCSS inline + tokens CSS)
```

### Workflow por página

1. **Diseñar en Stitch**: Escribir prompt descriptivo con referencia visual (Linear/Vercel)
2. **Iterar en Stitch**: Elegir variante, refinar con chat, ajustar tema/colores
3. **Conectar via MCP**: Claude Code lee el diseño de Stitch directamente
4. **Traducir a Angular**: Claude Code genera componentes Angular con:
   - Angular Material M3 para funcional (forms, selects, dialogs, progress)
   - SCSS inline styles con CSS custom properties (`var(--token)`)
   - Mismas convenciones actuales (standalone components, signals, inline template)
5. **Ajustar y verificar**: Iterar en código hasta fidelidad visual aceptable

### Stack — qué cambia y qué no

| Elemento | Estado |
|----------|--------|
| Angular 21 | Se mantiene |
| Angular Material 21 (M3) | Se mantiene para funcional (forms, selects, dialogs) |
| SCSS + CSS custom properties | Se mantiene (tokens en `_tokens.scss`) |
| Highcharts | Se mantiene |
| Inline templates/styles | Se mantiene |
| Estilos visuales de cards, layouts, superficies | **Se reemplazan** según diseño de Stitch |
| Backend Python/FastAPI | Intocado |
| Tests e2e Playwright | Se actualizan visual snapshots |

## Setup requerido (una sola vez)

### 1. Google Stitch
- Acceder a [stitch.withgoogle.com](https://stitch.withgoogle.com)
- Gratis (Google Labs experiment)
- Crear diseños con prompts

### 2. Stitch MCP Server
- Instalar: `npx @_davideast/stitch-mcp proxy`
- Alternativa auto-setup: `npx -p stitch-mcp-auto stitch-mcp-auto-setup`
- Requiere Google Cloud project con Stitch API habilitada (free tier)
- Documentación: [stitch.withgoogle.com/docs/mcp/setup](https://stitch.withgoogle.com/docs/mcp/setup)

### 3. Configurar en Claude Code
- Añadir Stitch MCP server a la configuración de Claude Code
- Verificar conexión con un diseño de prueba

## Páginas a rediseñar (por orden de prioridad)

| # | Página | Archivo | Complejidad |
|---|--------|---------|-------------|
| 1 | Dashboard | `web/src/app/pages/dashboard.ts` | Alta (hero card, stats bar, topic chips, news list) |
| 2 | News Item Card | `web/src/app/components/news-item-card.ts` | Media (componente compartido, usado en todas las páginas) |
| 3 | Chat | `web/src/app/pages/chat.ts` | Alta (SSE messages, markdown, suggestions) |
| 4 | Archive | `web/src/app/pages/archive.ts` | Media (date picker, news list, stats) |
| 5 | Search | `web/src/app/pages/search.ts` | Baja (form + results list) |
| 6 | Analytics | `web/src/app/pages/analytics.ts` | Media (Highcharts, tema reactivo) |
| 7 | Login | `web/src/app/pages/login.ts` | Baja (form simple) |
| 8 | App shell (nav/sidebar) | `web/src/app/app.ts` | Media (navigation, theme toggle) |
| 9 | Tokens globales | `web/src/styles/_tokens.scss` | Baja (ajustar si Stitch sugiere paleta) |

## Estética objetivo

**Referencia**: Linear, Vercel Dashboard, Raycast

**Características clave:**
- Dark-first (el modo oscuro es la experiencia principal)
- Mucho espacio negativo
- Tipografía limpia con jerarquía clara
- Bordes sutiles (1px, baja opacidad)
- Sombras mínimas (solo para elevación funcional)
- Colores de accent contenidos (no saturados)
- Micro-interacciones sutiles (hover, transitions)
- Cards con bordes, no con sombras
- Monospace para datos numéricos/técnicos

## Riesgos y mitigaciones

| Riesgo | Probabilidad | Mitigación |
|--------|-------------|-----------|
| Stitch es experimental (puede desaparecer) | Media | Sin lock-in — el código Angular generado es tuyo. Stitch es solo la herramienta de diseño. |
| Stitch MCP requiere Google Cloud setup | Baja | Free tier suficiente. Setup una sola vez. |
| Traducción HTML→Angular pierde fidelidad | Media | Iterar con Claude Code hasta match visual. Screenshots para comparar. |
| Rediseño rompe visual regression tests | Seguro | Actualizar snapshots después de cada página (`npm run e2e:visual:update`) |
| Angular Material overrides difíciles | Media | Mantener Material solo para funcional. Superficies visuales son custom SCSS. |

## Criterios de éxito

1. Las 6 páginas principales rediseñadas con estética Linear/Vercel
2. Dark mode y light mode funcionan correctamente
3. Mobile responsive (390px+) funciona
4. 0 errores de TypeScript (`npx tsc --noEmit`)
5. Tests e2e pasan (con snapshots actualizados)
6. El desarrollador puede usar Stitch + Claude Code para futuros cambios visuales

## Decisiones tomadas

1. **No migrar a React** — Angular es el stack actual, funciona bien, el ecosistema design-to-code es secundario
2. **No añadir Tailwind** — mantener SCSS + CSS custom properties (stack actual funciona, no añadir complejidad)
3. **No usar Figma** — requiere plan de pago para MCP. Stitch es gratis.
4. **No usar Pencil.dev** — no soporta Angular
5. **No usar Spartan UI** — demasiado riesgo (librería joven) para el beneficio
6. **Stitch como "ojo de diseño"** — el AI diseña, Claude Code traduce. El developer no necesita "tener ojo".

---

*Diseño aprobado: 22 de febrero de 2026*

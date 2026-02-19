# Plan de Mejora Premium — AI News Platform

> Fecha: 2026-02-19
> Autor: Auditoría de Diseño Expert
> Stack: Angular 21 + Angular Material M3 + Highcharts + SCSS tokens

---

## 1. Diagnóstico del Estado Actual

### 1.1 Lo que ya funciona bien
- **Token system** sólido con CSS custom properties y dark/light bien separados
- **Tipografía** correcta (Plus Jakarta Sans + JetBrains Mono)
- **View Transitions** entre rutas
- **Skeleton loading** y animaciones base
- **Search results cards** con estructura legible (source badge, topic, title, summary, date)

### 1.2 Problemas Críticos Detectados

| # | Problema | Severidad | Páginas Afectadas |
|---|---------|-----------|-------------------|
| 1 | **Densidad visual extrema** — Las cards son muros de texto sin ningún elemento visual (iconos, imágenes, gradientes). Todo se lee como un terminal. | Alta | Dashboard, Archivo, Buscar |
| 2 | **Sin jerarquía visual** — Trending news y noticias regulares tienen exactamente el mismo peso visual. No hay "hero card" ni destacado. | Alta | Dashboard |
| 3 | **Contraste insuficiente en dark mode** — El texto secundario (#A1A1AA sobre #141418) apenas alcanza WCAG AA. Los títulos de cards son difíciles de escanear. | Alta | Todas |
| 4 | **Vacío visual masivo** — Dashboard y Archive muestran ~20 items en la mitad superior y dejan el 60% inferior completamente vacío (fondo negro). | Alta | Dashboard, Archivo |
| 5 | **Charts genéricos** — Colores aleatorios (naranja, amarillo, gris, rosa), sin paleta coherente. Line chart es una línea azul plana sin área fill. No hay tooltips visibles ni data highlights. | Alta | Analytics |
| 6 | **Sin identidad de marca** — "AI News Platform" es texto plano. No hay logo, icono, ni gradiente que genere reconocimiento. Podría ser cualquier dashboard admin. | Media | Navbar, todas |
| 7 | **Tags/Badges sin color-coding** — hackernews, rss, github, arxiv todos usan el mismo estilo. No hay diferenciación visual por fuente. | Media | Dashboard, Archivo, Buscar |
| 8 | **Chat page vacía** — 70% de la pantalla es espacio vacío. Los suggestion chips son rectángulos planos. No transmite "experiencia AI". | Media | Chat |
| 9 | **Mobile degradado** — Texto extremadamente pequeño, layout comprimido sin adaptación real. Search mobile tiene layout roto (botón Buscar desalineado). | Media | Todas (mobile) |
| 10 | **Cero micro-interacciones** — Sin hover states premium, sin transiciones en cards, sin feedback táctil. La UI se siente estática. | Media | Todas |
| 11 | **Stats bar plana** — Los números son correctos pero carecen de color, iconos, o indicadores de tendencia (flechas up/down). | Baja | Dashboard |
| 12 | **Empty states genéricos** — El icono de lupa en Search es estándar. Sin ilustración ni personalidad. | Baja | Buscar |

---

## 2. Plan de Mejora Premium

### Track 1 — Identidad Visual y Color System (Fundación)

#### 1A. Logo y Branding en Navbar
**Qué:** Reemplazar el texto plano "AI News Platform" con un icono SVG + wordmark.
**Cómo:**
- Crear un icono SVG compacto (24x24) que combine un "newspaper fold" con un "neural node" — líneas geométricas, no ilustración compleja
- Usar un gradiente sutil indigo→violet en el icono (alineado con `--accent`)
- El wordmark se queda en Plus Jakarta Sans bold, pero con tracking -0.02em más tight
- Añadir un divider sutil `|` entre logo y nav links

**Impacto:** Reconocimiento inmediato de marca. Deja de parecer un template.

#### 1B. Source Color System
**Qué:** Asignar un color único a cada fuente (hackernews, arxiv, github, etc.).
**Cómo:** Añadir tokens al sistema:
```scss
// _tokens.scss additions
--source-hackernews: #FF6600;    // HN orange
--source-arxiv: #B31B1B;         // arXiv red
--source-github: #8B5CF6;        // GitHub violet
--source-rss: #F59E0B;           // RSS amber
--source-huggingface: #FFD21E;   // HF yellow
--source-reddit: #FF4500;        // Reddit orange-red
```
- Los badges de fuente usan `background: color-mix(in srgb, var(--source-X) 15%, transparent)` con `color: var(--source-X)`
- En dark mode, opacidad del background al 20%

**Impacto:** Escaneo visual instantáneo por fuente. Color-coding es lo que hacen Bloomberg, TechCrunch, etc.

#### 1C. Topic Chip Colors
**Qué:** Los chips de tema ("modelos", "herramientas", "papers") necesitan diferenciación visual.
**Cómo:**
- Usar un mapa de colores derivados del accent (hue-shift):
  - modelos → indigo
  - herramientas → emerald
  - papers → amber
  - open_source → violet
  - productos → cyan
  - agentes → rose
  - regulacion → slate
- Los chips "trending" mantienen un estilo especial (filled con gradient, no outlined)

**Impacto:** El dashboard deja de ser monocromático. Los temas se distinguen a primera vista.

---

### Track 2 — Dashboard Premium (Página Principal)

#### 2A. Hero Card para Trending #1
**Qué:** La noticia con más puntos del día se muestra como "hero" con tratamiento especial.
**Cómo:**
- Primera card ocupa full-width con padding extra (32px en lugar de 20px)
- Fondo con gradiente sutil: `linear-gradient(135deg, var(--bg-elevated), color-mix(in srgb, var(--accent) 4%, var(--bg-elevated)))`
- Badge "TRENDING" con animación pulse sutil
- Título en `--text-xl` (24px) en lugar del estándar `--text-lg` (18px)
- Borde izquierdo con accent color (4px solid var(--accent))

**Impacto:** Jerarquía visual clara. El usuario sabe inmediatamente qué es lo más importante.

#### 2B. Stats Bar con Iconos y Color
**Qué:** Transformar la stats bar de números planos a KPI cards visuales.
**Cómo:**
- Añadir un icono Material encima de cada número (Download, FilterAlt, Trending, Timer)
- El icono usa `color: var(--accent)` para dar vida
- Añadir micro-indicadores: flecha ↑/↓ con color verde/rojo comparando con el día anterior
- Número principal usa `color: var(--text-primary)` (más contraste, ahora es correcto pero se pierde)
- Opcional: animación countUp en los números al hacer scroll into view

**Impacto:** Los stats dejan de ser un muro de números y se convierten en dashboard KPIs legibles.

#### 2C. Card Hover States Premium
**Qué:** Interactividad visible al pasar el mouse sobre las news cards.
**Cómo:**
```scss
.news-card {
  transition: transform 0.2s ease, border-color 0.2s ease, box-shadow 0.2s ease;

  &:hover {
    transform: translateY(-2px);
    border-color: var(--border-hover);
    box-shadow: var(--shadow-md);
  }

  // Dark mode: glow sutil
  .dark &:hover {
    box-shadow: 0 4px 20px rgba(99, 102, 241, 0.08);
  }
}
```
- El título cambia a `color: var(--accent)` en hover
- El source badge se ilumina ligeramente

**Impacto:** La interfaz se siente viva y responsiva al usuario.

#### 2D. Card Layout Improvements
**Qué:** Mejorar la estructura visual interna de cada card.
**Cómo:**
- Añadir un divider sutil antes del footer (author + date)
- Alinear badges (source, points, topic) en una línea superior con `gap: 8px`
- El summary text usa `line-clamp: 3` consistentemente
- Añadir un link icon (→) sutil en la esquina derecha que aparece en hover
- Footer con tipografía monospace para fecha, alineado a la derecha

**Impacto:** Cards más escaneables y profesionales.

---

### Track 3 — Analytics Page Premium

#### 3A. Paleta de Colores Coherente para Charts
**Qué:** Unificar todos los charts bajo una paleta derivada del accent.
**Cómo:**
```scss
// Chart palette tokens
--chart-1: #6366F1;  // indigo (primary)
--chart-2: #8B5CF6;  // violet
--chart-3: #A78BFA;  // violet-light
--chart-4: #C4B5FD;  // violet-lighter
--chart-5: #818CF8;  // indigo-light
--chart-6: #6EE7B7;  // emerald (contraste)
--chart-7: #FBBF24;  // amber (contraste)
```
- Aplicar en Highcharts via theme config
- El donut chart usa gradientes sutiles en cada segmento
- El bar chart usa la misma paleta ordenada por saturación

**Impacto:** Los charts se ven cohesivos y profesionales, no como colores aleatorios de Excel.

#### 3B. Line Chart con Area Fill
**Qué:** El line chart actual es una línea sola flotando. Añadir area fill.
**Cómo:**
- Configurar Highcharts `type: 'area'` con `fillColor` gradient:
  ```js
  fillColor: {
    linearGradient: { x1: 0, y1: 0, x2: 0, y2: 1 },
    stops: [
      [0, 'rgba(99, 102, 241, 0.25)'],
      [1, 'rgba(99, 102, 241, 0.02)']
    ]
  }
  ```
- Añadir puntos circulares en cada data point (`marker: { radius: 4 }`)
- Tooltip con diseño custom (fondo dark, border-radius, shadow)
- Smooth curve con `spline` en lugar de `line`

**Impacto:** El chart pasa de "gráfico de Excel" a "dashboard profesional de analytics".

#### 3C. Chart Cards con Headers Mejorados
**Qué:** Los headers "ITEMS POR DÍA" en ALL CAPS son agresivos.
**Cómo:**
- Cambiar a Title Case: "Items por día (últimos 14 días)"
- Usar `--text-base` con `font-weight: 600` en lugar de `--text-xs` uppercase
- Añadir un dot indicator con el color del chart a la izquierda del título
- Padding superior de la card: 24px (actualmente parece apretado)

**Impacto:** Headers legibles y elegantes.

#### 3D. KPI Summary Row encima de Charts
**Qué:** Añadir una fila de KPIs rápidos arriba de los charts (Total items, Avg/day, Top source, Top topic).
**Cómo:**
- Reutilizar el componente stats-bar del dashboard
- 4 métricas: Total últimos 14d | Promedio/día | Fuente top | Tema top
- Cada KPI con su icono Material correspondiente

**Impacto:** Contexto inmediato antes de ver los charts. Patrón estándar de dashboards premium.

---

### Track 4 — Chat Page Premium

#### 4A. Welcome Screen con Personalidad AI
**Qué:** Transformar la pantalla vacía del chat en una experiencia de bienvenida memorable.
**Cómo:**
- Icono central: SVG animado de un "AI brain" o "sparkles" con animación pulse sutil
- Gradiente de fondo sutil detrás del título: `radial-gradient(ellipse at center, color-mix(in srgb, var(--accent) 6%, transparent), transparent 70%)`
- Título "Chat con IA" con gradient text: `background: linear-gradient(135deg, var(--accent), #A78BFA); -webkit-background-clip: text; color: transparent;`
- Subtítulo más prominente

**Impacto:** El chat se siente como un producto AI premium, no como un form vacío.

#### 4B. Suggestion Chips Mejorados
**Qué:** Los 4 rectángulos planos necesitan vida visual.
**Cómo:**
- Añadir un icono a la izquierda de cada sugerencia (Sparkle, Code, Document, Bot)
- Hover: background color shift + scale(1.02) + shadow
- Layout: grid 2x2 con gap de 12px (ya está, pero más padding interno: 16px 20px)
- Borde con gradient sutil en hover: `border-image: linear-gradient(var(--accent), var(--accent-dim)) 1`
- Texto en `--text-sm` con `color: var(--text-secondary)` (no muted)

**Impacto:** Las sugerencias se sienten clicables e invitantes.

#### 4C. Input Bar Rediseñado
**Qué:** La barra de input inferior se siente desconectada de la experiencia.
**Cómo:**
- Contenedor con `position: sticky; bottom: 0` y backdrop-blur
- Background: `background: color-mix(in srgb, var(--bg-base) 80%, transparent); backdrop-filter: blur(12px);`
- Border-top sutil con gradient
- Botón "Enviar" con accent color filled (no ghost button)
- Añadir icono Send al botón
- El selector de tema se integra como un chip compacto dentro del input bar, no como dropdown separado

**Impacto:** El input se siente integrado y moderno (estilo ChatGPT/Claude).

---

### Track 5 — Search Page Premium

#### 5A. Search Bar Prominente
**Qué:** El campo de búsqueda necesita ser el protagonista visual.
**Cómo:**
- Aumentar height a 56px (actualmente ~44px)
- Añadir icono Search a la izquierda dentro del field
- Focus state: glow ring con `box-shadow: var(--shadow-glow), var(--shadow-md)`
- Botón "Buscar" con accent filled (actualmente parece disabled)
- Los filtros (Tema, Desde, Hasta) se colapsan en un toggle "Filtros avanzados" para simplificar la vista default

**Impacto:** Experiencia de búsqueda más directa y premium.

#### 5B. Empty State con Ilustración
**Qué:** El icono de lupa genérico necesita más personalidad.
**Cómo:**
- SVG ilustración custom: lupa con nodos de AI/neural network dentro
- Animación idle sutil (floating up/down 4px)
- El texto "Busca entre las noticias archivadas" con mejor contraste
- Las sugerencias ("LLM, agentes, open source...") como chips clicables (no texto plano en mono)

**Impacto:** Estado vacío que invita a explorar en lugar de parecer roto.

#### 5C. Search Results con Highlight
**Qué:** Cuando hay resultados, el término buscado debería resaltarse.
**Cómo:**
- El backend ya devuelve los textos. Wrap matches en `<mark>` con estilo:
  ```scss
  mark {
    background: color-mix(in srgb, var(--accent) 20%, transparent);
    color: inherit;
    border-radius: 2px;
    padding: 0 2px;
  }
  ```
- Añadir counter: "3 resultados para 'LLM'" con estilo más prominente

**Impacto:** Feedback visual de la búsqueda. Patrón estándar en productos serios.

---

### Track 6 — Navbar y Navegación

#### 6A. Active State Mejorado
**Qué:** La página activa solo tiene un underline. Necesita más presencia.
**Cómo:**
- Active: `color: var(--text-primary)` + underline 2px accent + `font-weight: 600`
- Hover (no active): `color: var(--text-primary)` con transición suave
- Inactive: `color: var(--text-muted)` (más contraste que ahora)
- Añadir un dot indicator debajo del link activo (estilo Apple) como alternativa al underline

**Impacto:** Navegación más clara. El usuario sabe dónde está inmediatamente.

#### 6B. Mobile Menu Premium
**Qué:** El menú mobile es un dropdown básico. Necesita polish.
**Cómo:**
- Slide-in desde la derecha (sheet) en lugar de dropdown
- Background con backdrop-blur
- Cada link con icono Material a la izquierda
- Dark mode toggle integrado como switch en el sheet
- Animación staggered en los items (fade-in con delay incremental)
- "Salir" en la parte inferior con color error sutil

**Impacto:** Experiencia mobile que se siente nativa y premium.

#### 6C. Navbar Scroll Behavior
**Qué:** La navbar siempre se ve igual. Al hacer scroll debería tener feedback visual.
**Cómo:**
- `position: sticky; top: 0; z-index: 100;`
- Al scroll > 10px: añadir `backdrop-filter: blur(12px)` + `border-bottom: 1px solid var(--border)` + shadow sutil
- Transición suave (0.3s)

**Impacto:** Navbar profesional que responde al contexto.

---

### Track 7 — Contraste y Accesibilidad

#### 7A. Fix Dark Mode Contrast
**Qué:** El texto secundario y muted no cumple WCAG AA en dark mode.
**Cómo:**
```scss
// Actualizar tokens dark:
--text-secondary: #B4B4BE;  // era #A1A1AA → +15% luminancia
--text-muted: #6B6B78;      // era #52525B → +20% luminancia
```
- Card titles siempre usan `--text-primary` (actualmente algunos usan secondary)
- Summary text sube a `--text-secondary` actualizado

**Impacto:** Lectura cómoda en dark mode. Cumple WCAG AA (4.5:1 ratio).

#### 7B. Focus States Mejorados
**Qué:** El focus ring actual es solo `box-shadow: var(--shadow-glow)` que es invisible en light mode.
**Cómo:**
- Aumentar el glow: `0 0 0 3px var(--accent-glow), 0 0 0 1px var(--accent)`
- Asegurar que todos los elementos interactivos tienen `:focus-visible`
- Tab navigation fluida por la navbar

**Impacto:** Accesibilidad para navegación por teclado.

---

### Track 8 — Micro-interacciones y Polish

#### 8A. Number Count-Up Animation
**Qué:** Los stats (91, 70, 26...) aparecen estáticos. Deberían animarse al cargar.
**Cómo:**
- Directiva Angular `countUp` que anima de 0 al valor final en 800ms con easing
- Trigger: primera vez que el elemento entra en viewport (`IntersectionObserver`)

**Impacto:** Delight visual. Los dashboards premium siempre animan números.

#### 8B. Skeleton Loading Mejorado
**Qué:** El skeleton actual funciona pero es genérico.
**Cómo:**
- Crear skeleton-card con la forma exacta de una news card (badge placeholder + title lines + body lines)
- Mostrar 3-5 skeleton cards durante la carga
- Transición fade de skeleton → content real

**Impacto:** Perceived performance. La app se siente más rápida.

#### 8C. Route Transition Polish
**Qué:** Las View Transitions existen pero son sutiles. Pueden mejorarse.
**Cómo:**
- Añadir `view-transition-name` a elementos compartidos (navbar, stats-bar)
- La navbar persiste (no hace fade), solo el contenido transiciona
- Staggered animation en las cards al entrar a una nueva ruta

**Impacto:** Navegación fluida estilo app nativa.

#### 8D. Pull-to-Refresh Visual (Mobile)
**Qué:** En mobile, el usuario debería poder hacer pull-to-refresh con feedback visual.
**Cómo:**
- Indicador de refresh con spinner accent color
- Animación de las cards re-entrando con stagger

**Impacto:** Experiencia mobile que se siente nativa.

---

### Track 9 — Archive Page Específico

#### 9A. Date Navigation Mejorada
**Qué:** La barra de fecha + tema se siente utilitaria.
**Cómo:**
- Añadir navegación por día: botones "← Ayer" / "Hoy" / "Mañana →"
- El datepicker se abre desde un botón de calendario, no como field primario
- Mostrar la fecha seleccionada como header prominente: "Noticias del 19 de febrero, 2026"

**Impacto:** Navegación temporal intuitiva, menos clics.

#### 9B. Empty State para Días sin Datos
**Qué:** Si un día no tiene noticias, mostrar un estado vacío apropiado.
**Cómo:**
- Ilustración SVG de calendario vacío
- Texto: "No se encontraron noticias para esta fecha"
- Link para volver al día más reciente con datos

**Impacto:** UX completa sin dead ends.

---

## 3. Priorización (Esfuerzo vs Impacto)

### Fase 1 — Quick Wins (1-2 días)
| Item | Track | Esfuerzo | Impacto |
|------|-------|----------|---------|
| 7A. Fix Dark Mode Contrast | 7 | Bajo | Alto |
| 1B. Source Color System | 1 | Bajo | Alto |
| 2C. Card Hover States | 2 | Bajo | Medio |
| 3A. Chart Color Palette | 3 | Bajo | Alto |
| 6A. Active State Navbar | 6 | Bajo | Medio |

### Fase 2 — Impacto Alto (3-5 días)
| Item | Track | Esfuerzo | Impacto |
|------|-------|----------|---------|
| 2A. Hero Card Trending | 2 | Medio | Alto |
| 2B. Stats Bar con Iconos | 2 | Medio | Alto |
| 3B. Line Chart Area Fill | 3 | Medio | Alto |
| 4A. Chat Welcome Screen | 4 | Medio | Alto |
| 5A. Search Bar Prominente | 5 | Medio | Medio |
| 1C. Topic Chip Colors | 1 | Medio | Medio |

### Fase 3 — Polish Premium (5-8 días)
| Item | Track | Esfuerzo | Impacto |
|------|-------|----------|---------|
| 1A. Logo y Branding | 1 | Medio | Medio |
| 4B-C. Chat Chips + Input | 4 | Medio | Medio |
| 6B-C. Mobile Menu + Scroll | 6 | Medio | Medio |
| 8A. Count-Up Animation | 8 | Bajo | Medio |
| 3C-D. Chart Headers + KPIs | 3 | Medio | Medio |
| 5B-C. Empty State + Highlight | 5 | Medio | Medio |

### Fase 4 — Extras (cuando haya tiempo)
| Item | Track | Esfuerzo | Impacto |
|------|-------|----------|---------|
| 8B-D. Skeletons + Transitions | 8 | Alto | Bajo |
| 9A-B. Archive Navigation | 9 | Medio | Bajo |
| 7B. Focus States | 7 | Bajo | Bajo |

---

## 4. Métricas de Éxito

| Métrica | Antes | Objetivo |
|---------|-------|----------|
| WCAG AA Compliance (text contrast) | ~70% | 100% |
| Tiempo para identificar trending news | >3s escaneo | <1s (hero card) |
| Color differentiation por fuente | 0 (todo gris) | 6 colores únicos |
| Interacciones hover/focus | 0 visibles | Todas las cards + links |
| Chart palette coherence | Aleatorio | Paleta unificada 7 colores |
| Mobile usability score | ~65 (estimado) | >85 |

---

## 5. Principios de Diseño para la Implementación

1. **Evolución, no revolución** — Cada cambio se construye sobre el token system existente. No reescribir, extender.
2. **Dark-first** — El dark mode es la experiencia principal. Diseñar dark, adaptar light.
3. **Token-driven** — Todo nuevo color/spacing se añade como token CSS. Zero magic numbers.
4. **Performance budget** — Ninguna animación > 300ms. Ningún SVG > 5KB. Ningún layout shift visible.
5. **Incremental delivery** — Cada fase se puede deployar independientemente. No hay dependencias cruzadas entre tracks.

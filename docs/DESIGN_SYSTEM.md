# AI News Platform — Design System

Reference document for AI agents and developers working on the frontend.
Covers tokens, typography, components, patterns, and conventions.

**Stack:** Angular 21 + Angular Material M3 + SCSS + CSS Custom Properties
**Theme:** Dark-first with light mode support. Violet/indigo accent palette.
**Fonts:** Plus Jakarta Sans (headings + body), JetBrains Mono (code + data)

---

## 1. Architecture

### File structure

```
web/src/styles/
  styles.scss          # Entry point: Material M3 theme + reset
  _tokens.scss         # CSS custom properties (light/dark)
  _typography.scss     # Font families + type scale
  _animations.scss     # Keyframes + utility classes
  _surfaces.scss       # Material overrides + shared components (stats-bar, cards)
  _layout.scss         # Focus ring, scrollbar, responsive utils

web/src/app/
  app.ts               # Shell: navbar, theme toggle, routing
  components/
    news-item-card.ts  # Shared card component (inline styles)
  pages/
    dashboard.ts       # News feed with topic filter
    archive.ts         # Date-based briefing viewer
    search.ts          # Full-text search with filters
    analytics.ts       # Highcharts dashboard (3 charts)
    chat.ts            # Streaming AI chat with markdown
    login.ts           # Authentication form
```

### Design decisions

- **CSS custom properties over SCSS variables** — Enables runtime dark/light switching without page reload.
- **Inline component styles** — Each component has `styles: [...]` with scoped CSS. Global tokens are referenced via `var(--token)`.
- **Material M3 + custom overrides** — Uses `mat.$violet-palette` then overrides surface/text tokens to match our design language.
- **`color-mix()` for tinted backgrounds** — `color-mix(in srgb, var(--color) 15%, transparent)` creates dynamic badge/chip backgrounds.
- **No external icon library** — Material Icons (`mat-icon`) exclusively.

---

## 2. Design Tokens

All tokens are CSS custom properties defined in `_tokens.scss`. Components reference them via `var(--token-name)`.

### Surfaces

| Token | Light | Dark | Usage |
|-------|-------|------|-------|
| `--bg-base` | `#FAFAFA` | `#0C0C0E` | Page background |
| `--bg-surface` | `#FFFFFF` | `#141418` | Card/panel backgrounds |
| `--bg-elevated` | `#F4F4F5` | `#1C1C22` | Secondary surfaces, stats bar |
| `--bg-hover` | `#E4E4E7` | `#24242C` | Interactive hover state |

### Accent

| Token | Light | Dark | Usage |
|-------|-------|------|-------|
| `--accent` | `#4F46E5` (indigo-600) | `#6366F1` (indigo-500) | Buttons, links, active states |
| `--accent-dim` | `#4338CA` | `#4F46E5` | Darker accent variant |
| `--accent-glow` | `rgba(79,70,229,0.1)` | `rgba(99,102,241,0.15)` | Subtle tinted backgrounds, focus ring |

### Text

| Token | Light | Dark | Usage |
|-------|-------|------|-------|
| `--text-primary` | `#09090B` | `#F4F4F5` | Headings, strong text |
| `--text-secondary` | `#52525B` | `#B4B4BE` | Body text (default) |
| `--text-muted` | `#A1A1AA` | `#6B6B78` | Metadata, labels, placeholders |

### Borders

| Token | Light | Dark | Usage |
|-------|-------|------|-------|
| `--border` | `rgba(0,0,0,0.09)` | `rgba(255,255,255,0.06)` | Default dividers |
| `--border-hover` | `rgba(0,0,0,0.15)` | `rgba(255,255,255,0.10)` | Interactive state |
| `--border-accent` | `rgba(79,70,229,0.25)` | `rgba(99,102,241,0.3)` | Accent-tinted (card hover) |

### Semantic

| Token | Value | Usage |
|-------|-------|-------|
| `--error` | `#EF4444` | Error state |
| `--error-subtle` | `rgba(239,68,68,0.1)` | Error background |
| `--success` | `#10B981` | Success state |
| `--warning` | `#F59E0B` | Warning state |

### Shadows

| Token | Light | Dark |
|-------|-------|------|
| `--shadow-sm` | `0 1px 2px rgba(0,0,0,0.04)` | `0 1px 2px rgba(0,0,0,0.2)` |
| `--shadow-md` | `0 4px 12px rgba(0,0,0,0.06)` | `0 4px 12px rgba(0,0,0,0.3)` |
| `--shadow-lg` | `0 8px 24px rgba(0,0,0,0.08)` | `0 8px 24px rgba(0,0,0,0.4)` |
| `--shadow-glow` | `0 0 0 3px var(--accent-glow)` | same | Focus ring |

### Source brand colors

Used for news source badges. Same in both themes.

| Token | Color | Source |
|-------|-------|--------|
| `--source-hackernews` | `#FF6600` | Hacker News |
| `--source-arxiv` | `#B31B1B` | arXiv |
| `--source-github` | `#8B5CF6` | GitHub |
| `--source-rss` | `#F59E0B` | RSS feeds |
| `--source-huggingface` | `#FFD21E` | Hugging Face |
| `--source-reddit` | `#FF4500` | Reddit |

### Topic category colors

Applied via `[data-topic]` attributes. Dark mode uses lighter variants.

| Token | Light | Dark | Topic |
|-------|-------|------|-------|
| `--topic-modelos` | `#6366F1` | `#818CF8` | AI models |
| `--topic-herramientas` | `#10B981` | `#34D399` | Tools |
| `--topic-papers` | `#F59E0B` | `#FBBF24` | Research papers |
| `--topic-open_source` | `#8B5CF6` | `#A78BFA` | Open source |
| `--topic-productos` | `#06B6D4` | `#22D3EE` | Products |
| `--topic-agentes` | `#F43F5E` | `#FB7185` | AI agents |
| `--topic-regulacion` | `#64748B` | `#94A3B8` | Regulation |

---

## 3. Typography

Defined in `_typography.scss`. Single font family for headings and body (Plus Jakarta Sans).

### Font families

| Token | Value | Usage |
|-------|-------|-------|
| `--font-heading` | Plus Jakarta Sans | Page titles, card titles |
| `--font-body` | Plus Jakarta Sans | Body text, UI elements |
| `--font-mono` | JetBrains Mono | Code blocks, stat values, metadata |

### Type scale

| Token | Size | px | Usage |
|-------|------|----|-------|
| `--text-xs` | 0.6875rem | 11 | Labels, metadata, badges |
| `--text-sm` | 0.8125rem | 13 | Chips, nav, small body |
| `--text-base` | 0.9375rem | 15 | Body text default |
| `--text-lg` | 1.125rem | 18 | Card titles |
| `--text-xl` | 1.5rem | 24 | Page headings, stat values |
| `--text-2xl` | 2rem | 32 | Login title |
| `--text-display` | 2.5rem | 40 | Display (unused) |

### Line heights

| Token | Value | Usage |
|-------|-------|-------|
| `--leading-tight` | 1.25 | Headings, stat values |
| `--leading-snug` | 1.35 | Card titles |
| `--leading-normal` | 1.5 | Body text (default on `<body>`) |
| `--leading-relaxed` | 1.65 | Chat messages, summaries |

### Letter spacing

| Token | Value | Usage |
|-------|-------|-------|
| `--tracking-tight` | -0.025em | Headings, stat values |
| `--tracking-normal` | 0 | Body text |
| `--tracking-wide` | 0.02em | Badge labels |
| `--tracking-wider` | 0.06em | Uppercase labels |

---

## 4. Animations

Defined in `_animations.scss`. View `freeze-animations.ts` for E2E screenshot handling.

### Keyframes

| Name | From | To | Duration | Usage |
|------|------|----|----------|-------|
| `fade-in` | opacity:0, translateY(12px) | opacity:1, translateY(0) | 0.4s ease-out | Page load, item entry |
| `fade-in-subtle` | opacity:0 | opacity:1 | varies | Subtle appearance |
| `scale-in` | opacity:0, scale(0.96) | opacity:1, scale(1) | 0.4s ease-out | Login card |
| `blink` | opacity:1 | opacity:0 | 0.8s infinite | Chat cursor |
| `hero-pulse` | opacity:1 | opacity:0.6 | 2s infinite | Trending badge |
| `float` | translateY(0) | translateY(-4px) | 3s infinite | Search empty icon |
| `skeleton-shimmer` | bg-pos 200% | bg-pos -200% | 1.5s infinite | Loading state |

### View transitions (route animations)

- **Exit:** `vt-fade-out` — 150ms ease-in, fades to opacity:0
- **Enter:** `vt-fade-slide-in` — 300ms ease-out, fades in from translateY(6px)

### Staggered animations

Stats bar uses SCSS loop for cascade effect:
```scss
@for $i from 1 through 6 {
  .stat:nth-child(#{$i}) { animation-delay: #{($i - 1) * 80}ms; }
}
```

News list items also stagger: `[style.animation-delay]="i * 50 + 'ms'"` via Angular binding.

### E2E freeze helper

`e2e/helpers/freeze-animations.ts` handles animations for screenshots:
1. `document.getAnimations().forEach(a => a.finish())` — completes finite animations to end state
2. `anim.cancel()` for infinite animations (shimmer, blink, pulse)
3. Injects `animation: none !important` to prevent new animations

---

## 5. Spacing and sizing patterns

### Border radius scale

| Value | Usage |
|-------|-------|
| 6px | Badges (source, trending) |
| 8px | MatOption items |
| 10px | Buttons, form fields |
| 12px | Select panels, chat suggestion chips |
| 14px | Cards, stats bar, datepicker |
| 16px | Login card |
| 18px | Chat messages |
| 980px | Pill chips (topic, quick search) |

### Common heights

| Element | Desktop | Mobile |
|---------|---------|--------|
| Navbar | 52px | 48px |
| Form field (outline) | ~56px | ~56px |
| Submit button | 56px | 48px |
| Login button | 52px | 52px |
| MatOption | 44px | 44px |

### Content widths

| Context | Value |
|---------|-------|
| Main content | max-width: 1120px, padding: 40px 32px |
| Chat page | max-width: 720px |
| Login form | max-width: 400px |
| Suggestions grid | max-width: 500px |
| Mobile padding | 24px 16px |

### Responsive breakpoint

**Single breakpoint: 640px** (mobile).

Notable mobile changes:
- Navbar: 48px height, hamburger menu
- Forms: full-width stacked
- Charts: single column grid
- Chat suggestions: 1 column
- Stats bar: horizontal scroll, smaller text

---

## 6. Component Patterns

### Navbar (app.ts)

- Sticky top, z-index 100
- Frosted glass: `backdrop-filter: blur(12px)`, `color-mix(80% bg-surface)`
- Active link: underline indicator (2px accent, animated width)
- Theme toggle: cycles dark -> light -> system, icon rotates 15deg on hover
- Mobile: hamburger button, full-width dropdown with open/close transition

### NewsItemCard (news-item-card.ts)

- Hover: `translateY(-2px)`, accent border glow, shadow
- Source badges: `color-mix(15%)` background with brand color
- Topic chips: Material chips with data-topic color overrides
- Hero variant: 4px left accent border, gradient background, 5-line summary
- Title links: animated underline on hover (background-size transition)
- Meta footer: monospace, separated by border-top

### Stats Bar (_surfaces.scss)

- Shared by Dashboard and Archive
- Flex row, dividers between stats
- Staggered fade-in animation (80ms delay per stat)
- Icon: accent color at 70% opacity
- Value: monospace, tabular-nums, `--text-xl`
- Label: uppercase, `--text-xs`, wider tracking
- Mobile: horizontal scroll, hidden scrollbar

### Submit Button (_surfaces.scss)

- Class: `.submit-btn` applied alongside `mat-flat-button`
- Accent background, white text
- Hover: `filter: brightness(1.12)`
- Active: `transform: scale(0.98)`
- Disabled: `opacity: 0.4`
- Consistent 10px border-radius

### Chat Messages (chat.ts)

- User messages: accent background, white text, right-aligned, rounded (bottom-right: 6px)
- Assistant messages: elevated background, border, left-aligned (bottom-left: 6px)
- Markdown rendering: sanitized HTML with styled `<p>`, `<code>`, `<pre>`, `<strong>`, `<a>`
- Streaming cursor: blinking `|` in accent color
- Input form: sticky bottom, frosted glass background

### Material Overrides (_surfaces.scss)

| Component | Key overrides |
|-----------|---------------|
| MatCard | bg-elevated, 14px radius, 1px border, no shadow (dark), subtle shadow (light) |
| MatFormField | 10px radius, custom outline colors, font-body |
| MatSelect panel | bg-surface, 12px radius, heavy shadow, 44px option height |
| MatDatepicker | bg-elevated, 14px radius, accent selected, border + shadow |
| MatChip | bg-elevated, font-body, custom border |
| MatProgressBar | accent active, bg-hover track, 4px radius |

---

## 7. Theme system

### How it works

1. `html.dark` class controls dark mode
2. `_tokens.scss` defines light tokens in `:root`, dark tokens in `.dark`
3. `styles.scss` applies Material M3 theme per `html.dark` / `html:not(.dark)`
4. Components use `var(--token)` — values swap automatically

### Switching logic (app.ts)

```
dark -> light -> system -> dark (cycle)
```

- **dark/light**: `localStorage.setItem('theme', ...)`, toggles `.dark` on `<html>`
- **system**: follows `prefers-color-scheme: dark`, removes localStorage key
- **On load**: reads localStorage first, falls back to system preference

### Chart theme (analytics.ts)

- `MutationObserver` watches `<html>` class changes
- `isDark()` signal triggers recomputation
- Highcharts options recalculated: label color, grid color, tooltip bg, etc.

---

## 8. Page-specific patterns

### Dashboard

- Topic chips for filtering (pill shape, data-topic colors)
- Count label: "X noticias" muted text
- Hero card: first item gets `.hero` variant (accent border, larger text, gradient bg)
- News list: flex column, 14px gap, staggered fade-in

### Search

- Search row: input + button side by side (desktop), stacked (mobile)
- Filter row: topic select + date range pickers
- Mobile: `display: contents` on search-row, CSS `order` reflows to Input -> Filters -> Button
- Empty state: floating icon animation, quick-search pill chips
- Form fields use `subscriptSizing="dynamic"` to remove reserved hint space

### Archive

- Date-based briefing viewer
- Controls: topic filter + date picker
- Same stats bar as dashboard
- Topic chips with same color system

### Analytics

- 2-column grid of chart cards (1-column on mobile)
- Full-width chart: `grid-column: 1 / -1`
- Chart card title: dot indicator (8px accent circle via `::before`)
- Highcharts configured with design tokens (dynamic dark/light)

### Chat

- Max-width 720px centered layout
- Empty state: gradient title, suggestion chips (2x2 grid, 1 column mobile)
- Welcome glow: radial gradient background behind icon
- Streaming: real-time text with blinking cursor
- Sources: pill-style links below assistant messages
- Input: sticky bottom with frosted glass backdrop

### Login

- Centered card with background glow effects (radial gradients)
- Card animates in with `scale-in`
- Two decorative `::before`/`::after` pseudo-elements
- Mobile: glows hidden, reduced padding

---

## 9. Screenshots reference

Screenshots are generated by `e2e/screenshot-docs.spec.ts` and stored in:

```
docs/screenshots/
  desktop-dark/     14 PNGs (6 pages + 8 components)
  desktop-light/    14 PNGs
  mobile-dark/      15 PNGs (+ navbar-menu-open)
  mobile-light/     15 PNGs (+ navbar-menu-open)
```

### Pages captured

| Name | Content |
|------|---------|
| `dashboard` | Full page with stats bar + hero card + news list |
| `archive` | Briefing view with stats + news items |
| `search-empty` | Empty state with suggestion chips |
| `search-results` | Results for "LLM" query |
| `analytics` | Charts grid (area, pie, bar) |
| `chat` | Empty state with suggestions |

### Components captured

| Name | Content |
|------|---------|
| `navbar` | Top navigation bar |
| `stats-bar` | Statistics summary row |
| `news-card` | Single news item card |
| `mat-select-open` | Topic dropdown panel |
| `mat-datepicker-open` | Full viewport with calendar open |
| `suggestion-chips` | Chat suggestion buttons |
| `navbar-menu-open` | Mobile hamburger menu expanded (mobile only) |

### Regenerating

```bash
npm run e2e:screendocs              # All 4 viewport-theme combos
npm run e2e:visual                  # Visual regression tests
npm run e2e:visual:update           # Update visual baselines
```

---

## 10. Known conventions for contributors

### Adding a new page

1. Create `web/src/app/pages/new-page.ts` with inline template + styles
2. Reference tokens via `var(--token-name)` — never hardcode colors
3. Use `var(--font-body)` / `var(--font-heading)` / `var(--font-mono)`
4. Add route in `app.routes.ts`, nav link in `app.ts`
5. Add E2E test in `web/e2e/new-page.spec.ts`
6. Add screenshots to `screenshot-docs.spec.ts` (capturePages + captureComponents)
7. Update visual baselines: `npm run e2e:visual:update`

### Adding a new component

1. Create in `web/src/app/components/` with inline styles
2. Follow existing patterns: `var(--bg-elevated)` for backgrounds, `var(--border)` for borders
3. Border radius: 14px for cards, 10px for buttons/fields, 6px for badges
4. Transitions: `0.2s ease` for visual changes, `0.15s ease` for interactive
5. Hover patterns: subtle `translateY(-2px)` + border-accent + shadow

### Color usage rules

- **Never hardcode colors** — always use `var(--token)`
- **Source/topic badges:** use `color-mix(in srgb, var(--source-X) 15%, transparent)` pattern
- **Tinted backgrounds:** use `color-mix()` or `var(--accent-glow)`
- **Text hierarchy:** primary (headings) > secondary (body) > muted (meta)
- **Dark mode adjustments:** topic colors have lighter variants, shadows are heavier

### Material component rules

- Always override Material tokens via CSS custom properties (not inline styles)
- Use `.submit-btn` class on `mat-flat-button` for primary actions
- Use `subscriptSizing="dynamic"` on form fields to avoid extra spacing
- Select panels, datepickers render in CDK overlay — style globally in `_surfaces.scss`

### Responsive rules

- Single breakpoint: `@media (max-width: 640px)`
- Mobile navbar: 48px, hamburger menu
- Form fields: `width: 100%` on mobile
- Grids: collapse to single column
- Stats bar: horizontal scroll

---

## 11. Improvement areas (for reviewers)

Potential improvements that a reviewer or future agent might evaluate:

1. **Fluid typography** — Currently fixed sizes per breakpoint. Could benefit from `clamp()` for smoother scaling.
2. **Container queries** — Could replace some media queries for component-level responsiveness.
3. **Additional breakpoint** — Only 640px exists. A tablet breakpoint (~1024px) could improve mid-range layouts.
4. **CSS layers** — Could use `@layer` to manage specificity between Material overrides and custom styles.
5. **Color contrast** — `--text-muted` on dark backgrounds (#6B6B78 on #0C0C0E) may not meet WCAG AA. Worth auditing.
6. **Motion preferences** — No `prefers-reduced-motion` media query. Should disable animations for users who prefer reduced motion.
7. **Component extraction** — Stats bar, topic chips, and error states are repeated across pages. Could be standalone components.
8. **CSS custom property nesting** — Could introduce semantic aliases like `--color-interactive`, `--color-surface-card` for better abstraction.
9. **Dark mode as default** — The primary experience is dark, but `:root` defines light tokens. Consider making `.dark` the `:root` default.
10. **Highcharts theming** — Chart theme is computed in TypeScript. Could be driven by CSS custom properties for better consistency.

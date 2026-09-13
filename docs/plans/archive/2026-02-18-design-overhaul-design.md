# Design Overhaul — Minimal Luxury (Raycast-inspired)

**Date:** 2026-02-18
**Approach:** C — Design System First
**Aesthetic:** Minimal Luxury, dark-first, Raycast reference
**Scope:** All frontend styles + design system foundation. Zero TS logic changes.

## Decision Summary

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Aesthetic | Minimal Luxury | Ultra-clean, every detail polished, negative space |
| Reference | Raycast | Dark mode impecable, monocromatico + acento preciso |
| Theme priority | Dark-first | Dark mode is the primary experience |
| Motion level | Subtle premium | Fluid but never distracting |
| Approach | Design System First | Tokens + mixins + partials before components |

## 1. Typography

**Single font family for heading + body (like Raycast):**

| Role | Font | Weights | Source |
|------|------|---------|--------|
| Heading + Body | Plus Jakarta Sans | 400, 500, 700, 800 | Google Fonts |
| Monospace | JetBrains Mono | 400, 500 | Google Fonts (keep) |

**Type Scale (CSS custom properties):**

| Token | Size | Use |
|-------|------|-----|
| `--text-xs` | 0.6875rem (11px) | Labels, metadata, source badges |
| `--text-sm` | 0.8125rem (13px) | Body small, chips, nav links |
| `--text-base` | 0.9375rem (15px) | Body default, summaries |
| `--text-lg` | 1.125rem (18px) | Card titles |
| `--text-xl` | 1.5rem (24px) | Page headings |
| `--text-2xl` | 2rem (32px) | Login title |
| `--text-display` | 2.5rem (40px) | Reserved for future display use |

**Letter spacing:** headings `-0.025em`, body `0`, small text `0.02em`.

## 2. Color Palette

### Dark Mode (default)

```
--bg-base:        #0C0C0E     (near black, blue undertone)
--bg-surface:     #141418     (elevated surface)
--bg-elevated:    #1C1C22     (cards, modals, chat bubbles)
--bg-hover:       #24242C     (interactive hover)

--accent:         #6366F1     (electric indigo)
--accent-dim:     #4F46E5     (pressed/active state)
--accent-glow:    rgba(99,102,241,0.15)  (backgrounds, focus ring)

--text-primary:   #F4F4F5
--text-secondary: #A1A1AA
--text-muted:     #52525B

--border:         rgba(255,255,255,0.06)
--border-hover:   rgba(255,255,255,0.10)
--border-accent:  rgba(99,102,241,0.3)

--error:          #EF4444
--error-subtle:   rgba(239,68,68,0.1)
--success:        #10B981
--warning:        #F59E0B
```

### Light Mode (secondary)

```
--bg-base:        #FAFAFA
--bg-surface:     #FFFFFF
--bg-elevated:    #F4F4F5
--bg-hover:       #E4E4E7

--accent:         #4F46E5
--accent-dim:     #4338CA
--accent-glow:    rgba(79,70,229,0.1)

--text-primary:   #09090B
--text-secondary: #52525B
--text-muted:     #A1A1AA

--border:         rgba(0,0,0,0.06)
--border-hover:   rgba(0,0,0,0.10)
--border-accent:  rgba(79,70,229,0.25)
```

### Source Badge Colors (preserved for E2E)

```
hackernews:  bg rgba(255,102,0,0.12)  text #fb923c
arxiv:       bg rgba(185,28,28,0.12)  text #f87171
reddit:      bg rgba(255,69,0,0.12)   text #fb923c
rss:         bg rgba(245,158,11,0.12) text #fbbf24
github:      bg rgba(255,255,255,0.08) text var(--text-secondary)
huggingface: bg rgba(255,204,0,0.12)  text #fbbf24
```

## 3. Motion System

All CSS-only except route transitions (Angular animations).

### 3.1 Route Transitions

Angular `@routeAnimations` trigger:
- **Enter:** opacity 0 + translateY(6px) → 1 + 0, 300ms ease-out
- **Exit:** opacity 1 → 0, 150ms ease-in

### 3.2 Staggered Reveals

- Cards: fade-in + translateY(12px), 400ms ease-out, delay = index * 60ms
- Stats bar: each stat staggered 80ms apart
- Chips: staggered 40ms apart

### 3.3 Micro-interactions

| Element | Hover | Active/Click | Focus |
|---------|-------|-------------|-------|
| Card | translateY(-2px) + shadow + border glow | — | accent ring |
| Button (primary) | brightness(1.1) | scale(0.98) | accent ring |
| Button (ghost) | bg-hover | scale(0.98) | accent ring |
| Nav link | underline width 0→100% | — | accent ring |
| Chip | border-color + bg shift | — | accent ring |
| Form field | — | — | glow ring accent |
| Theme toggle | rotate(180deg) icon | — | — |

### 3.4 Skeleton Loading

Improved shimmer: subtler gradient, bg-surface → bg-hover → bg-surface, 1.5s infinite.

### 3.5 Theme Transition

`html { transition: background-color 0.4s, color 0.3s; }`

## 4. Design System Architecture

### File Structure

```
web/src/styles/
  _tokens.scss        # CSS custom properties (all design tokens)
  _typography.scss     # Font-face, type scale, text utilities
  _animations.scss     # @keyframes, animation/transition mixins
  _surfaces.scss       # Card, badge, chip, button base styles
  _layout.scss         # Container, spacing, responsive breakpoints
  styles.scss          # Entry: @use all partials + Material M3 theme + reset
```

### Key SCSS Mixins

```scss
// Surface levels
@mixin surface($level: 'surface')  // applies bg + border + radius

// Typography
@mixin text($size, $weight: 400)   // font-size + line-height + spacing

// Animations
@mixin fade-in($delay: 0, $distance: 12px)  // configurable reveal
@mixin stagger($count, $interval: 60ms)      // nth-child delays

// Interactions
@mixin hover-lift                   // translateY + shadow + border glow
@mixin focus-ring                   // accent glow focus-visible
@mixin press-scale                  // scale(0.98) on :active
```

### Design Tokens as CSS Custom Properties

All tokens defined as CSS custom properties (not SCSS variables) because they need
runtime switching for dark/light mode. SCSS mixins wrap token combinations.

## 5. Component Changes

### 5.1 App Shell (app.ts)

**Navbar:**
- Glass effect: `backdrop-filter: blur(12px)`, bg semi-transparent
- Brand: Plus Jakarta Sans 700, --text-lg
- Links: weight 500, animated underline on hover (width 0→100%)
- Active: horizontal line under link (not dot), with transition
- Vertical separator between brand and links
- Theme toggle: icon rotate transition
- Logout: icon only (minimal)

**Layout:**
- `max-width: 1120px`, `padding: 40px 32px`
- Route animation container

### 5.2 Login (login.ts)

- Background: gradient mesh (radial gradients of accent, very subtle, corner positioned)
- Card: bg-elevated, border more visible, `border-radius: 16px`
- Title: --text-2xl, weight 800
- Input: 52px height, focus glow ring
- Button: accent color, hover brightness
- Entry animation: card fade-in + scale(0.96→1)

### 5.3 Dashboard (dashboard.ts)

- Stats bar: staggered entry, mono numbers, refined separators
- Topic chips: rounded pills, selected = accent filled
- Cards: hover lift + border glow
- Full stagger animation on card list

### 5.4 News Item Card (news-item-card.ts)

- Padding 24px (up from 20px)
- Source badge: refined opacity, same colors (E2E constraint)
- Title: --text-lg, weight 700, hover underline transition
- Summary: --text-base, line-clamp 3
- Meta footer: border-top subtle separator
- Hover: translateY(-2px) + box-shadow + border-accent glow

### 5.5 Archive (archive.ts)

- Controls styling aligned with new DS
- Stats bar: same as dashboard improvements
- Topic chips: read-only display (current behavior preserved)

### 5.6 Search (search.ts)

- Search bar more prominent: taller input, visually integrated button
- Filters: improved spacing
- Cards: same improvements as dashboard

### 5.7 Chat (chat.ts)

- Empty state: --text-xl heading, refined subtitle, suggestion chips in 2x2 grid
- User bubbles: accent bg (electric indigo) + white text
- Assistant bubbles: bg-surface + border, code blocks with darker bg
- Input area: larger border-radius, accent button
- Streaming cursor: accent color pulsing
- Sources: refined pills with hover accent border

### 5.8 Analytics (analytics.ts)

- Chart cards: 24px padding
- Highcharts theme: accent indigo for line series (not white)
- Pie chart: shades of accent + greys
- Grid gap: 20px

## 6. E2E Constraints (Must Preserve)

### Element IDs
`#password`, `#archive-date`, `#topic-select`, `#date-from`, `#date-to`

### CSS Classes
`.navbar`, `.stats-bar`, `.topic-badge`, `.topic-chip`, `.search-input`, `.search-btn`,
`.chat-input`, `.send-btn`, `.topic-filter`, `.empty-state`, `.suggestion-chip`,
`.message.user`, `.message.assistant`, `.source-link`

### Data Attributes
`[data-source='hackernews']`, `[data-source='reddit']`, `[data-source='arxiv']`

### Other
- `app-news-item-card` Angular selector
- `article` semantic element wrapping cards
- `button[type='submit']` on login
- `h1` on login containing "AI News Platform"
- All Spanish text strings (nav labels, headings, error messages)
- `ainews_token` localStorage key
- `a[href='/dashboard']`, `a[href='/archive']`, `a[href='/search']`, `a[href='/analytics']`

## 7. Build Constraints

- Angular build budget: 1MB warning / 1.5MB error
- Google Fonts CDN (no self-hosting)
- Angular Material M3 theme system
- Inline templates and styles (single-file components)

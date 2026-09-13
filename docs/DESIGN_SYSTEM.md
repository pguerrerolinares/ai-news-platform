# Design System

> Rewritten 2026-09-13 against the actual frontend (`frontend/src/`). The previous
> version of this file described an Angular + Material stack that was replaced by
> React in February 2026 (see `git log --diff-filter=A -- docs/DESIGN_SYSTEM.md`);
> it was untracked from git at that point and this is a from-scratch rewrite, not
> a diff against it.

## Stack

- **React 19** + **Vite 7**, TypeScript, `react-router` for routing.
- **Tailwind CSS 4** — CSS-first config via `@theme` in `frontend/src/index.css`
  (no `tailwind.config.js`).
- **shadcn/ui** (`frontend/src/components/ui/`) on top of **Radix UI** primitives,
  styled with `class-variance-authority` (`cva`) + `tailwind-merge` (`cn()` helper
  in `frontend/src/lib/utils.ts`).
- **lucide-react** / `@tabler/icons-react` for generic icons, `@icons-pack/react-simple-icons`
  for source brand icons (HN, GitHub, arXiv, Reddit, RSS, HuggingFace).
- **motion** (Motion for React, formerly Framer Motion) for transitions.
- **recharts** for charts (Admin dashboard).

## Tokens (`frontend/src/index.css`)

All tokens are CSS custom properties in OKLCH, defined once on `:root` (light) and
overridden under `.dark`, then re-exposed as Tailwind theme colors via `@theme inline`
so they're usable as `bg-background`, `text-foreground`, `border-border`, etc.

| Token | Purpose |
|---|---|
| `--background` / `--foreground` | Page background / default text |
| `--card` / `--card-foreground` | Card surfaces |
| `--popover` / `--popover-foreground` | Popovers, dropdowns, tooltips |
| `--primary` / `--primary-foreground` | Primary actions |
| `--secondary` / `--secondary-foreground` | Secondary actions |
| `--muted` / `--muted-foreground` | De-emphasized text/surfaces |
| `--accent` / `--accent-foreground` | Hover/active surfaces |
| `--destructive` | Errors, destructive actions |
| `--border` / `--input` / `--ring` | Borders, form inputs, focus rings |
| `--chart-1` … `--chart-5` | recharts series colors |
| `--sidebar*` | Admin sidebar (separate palette from the main surface) |
| `--radius` (`0.625rem`) | Base radius; `--radius-sm/md/lg/xl/2xl/3xl/4xl` derive from it via `calc()` |

Dark mode is class-based: the `.dark` class on `<html>` (toggled by `useTheme` /
`ThemeToggle`, see `frontend/src/hooks/use-theme.tsx`) switches every token via
`@custom-variant dark (&:is(.dark *))`. The theme switch itself uses the browser
View Transitions API (`::view-transition-*` rules in `index.css`) for a circular
reveal animation — no extra library.

There is **no custom font stack**: components use the browser/Tailwind default
system font. There is no dedicated type-scale doc — sizes are ad hoc Tailwind
utilities (`text-sm`, `text-xs`, …) at each call site.

## Components

### shadcn/ui primitives (`frontend/src/components/ui/`)

`avatar`, `badge`, `breadcrumb`, `button`, `calendar`, `card`, `chart`, `checkbox`,
`drawer`, `dropdown-menu`, `input`, `label`, `popover`, `scroll-area`, `select`,
`separator`, `sheet`, `sidebar`, `skeleton`, `sonner` (toasts), `table`, `tabs`,
`textarea`, `toggle` / `toggle-group`, `tooltip`.

Each exports a `cva()` variant map (e.g. `buttonVariants`: `default` / `destructive`
/ `outline` / `secondary` / `ghost` / `link`, sizes `xs`/`sm`/`default`/`lg` +
`icon`/`icon-xs`/`icon-sm`/`icon-lg`) and a typed `VariantProps` component. These
are generated/updated with the `shadcn` CLI (`shadcn` devDependency in
`frontend/package.json`) — treat manual edits inside `ui/` as customization on top
of a regenerable base, not hand-rolled components.

### App-level components (`frontend/src/components/`)

`app-nav`, `layout`, `animated-outlet` / `animated-card-grid` (page and grid
transitions via `motion`), `news-card` (the feed item card — source icon +
color, topic badge, relative time via a local `timeAgo()`, `safeUrl()`-guarded
outbound link), `calendar-heatmap`, `date-picker`, `pill-tabs`, `theme-toggle`,
`topic-filter`, `topic-group`.

### Pages (`frontend/src/pages/`)

`Dashboard`, `Discover`, `Search`, `Trending`, `Timeline`, `Briefing`, `Admin`.
(Login/Settings/Chat pages were removed with the guest-only auth model — see
`docs/adr/002-web-publica-guest-only.md`.)

## Source & topic identity (`frontend/src/lib/constants.ts`)

- `SOURCE_COLORS`: Tailwind utility strings per source (`bg-*/10 text-* border-*/20`),
  used for badges. Covers `hackernews`, `github`, `arxiv`, `reddit`, `rss`,
  `huggingface`. **`github_search` and `webscraper` (both enabled extractors, see
  `EXTRACTOR_REGISTRY` in `src/extractors/__init__.py`) have no entry** — they fall
  through to whatever default a missing key resolves to; add colors here when
  picking this up (tracked as finding #35, not in this pass' scope).
- `SOURCE_ICONS` (in `news-card.tsx`): same gap — no icon mapped for
  `github_search`/`webscraper`.
- `TOPIC_LABELS`: display labels for the `valid_topic` DB constraint values
  (`models`, `papers`, `agents`, `products`, `tools`, `open_source`, `regulation`).

## Conventions

- All UI text is in English, hardcoded in components (see `CLAUDE.md` — "Frontend
  text"). There is a `frontend/src/locales/en.json` file but no i18n library wiring
  it up; treat it as dead until it's actually used or removed.
- Styling is Tailwind utility classes directly in JSX; `cn()` merges conditional
  classes. There is no separate CSS-in-JS or component-scoped stylesheet approach
  outside of `index.css`.
- Icons follow the source's real brand color (`SOURCE_ICONS`) but generic UI icons
  use `currentColor` / theme tokens, never a hardcoded color.

# React Frontend v1 — Design Doc

## Goal

Build a content-first AI news site using React + Shadcn UI. Four public pages (Latest, Trending, Buscar, Chat) with mock data. Focus on reader experience, not admin dashboards.

## Context

The project collects AI news from multiple sources (HackerNews, GitHub, arXiv, Reddit, RSS, HuggingFace), scores and classifies them, and presents a daily briefing. The current Angular frontend works but has a heavy development workflow. This React frontend validates a lighter stack (Vite + React + Tailwind + Shadcn) with better DX and smaller bundles (~92 kB vs ~276 kB).

## Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Page structure | Latest, Trending, Buscar, Chat | Content-first like TDS. Admin stats are out of scope. |
| Navigation | Top nav, hamburger on mobile | Clean, no icons. Sheet/Drawer for mobile menu. |
| Data source | Mock data (20 items) | Iterate design without backend dependency. |
| Chat UX | Full page | Dedicated /chat route, ChatGPT-style. Mock responses for now. |
| "Latest" vs "Hoy" | Latest (chronological feed) | Not grouped by day — just the most recent items. |
| Trending | Flag + top scores | Items marked trending by pipeline + highest scored items. |

## Pages

### `/` — Latest

Feed of the most recent news items. Layout:
- Header: "Latest" title + item count + topic Select dropdown
- Featured card: highest-scored item, large format
- News grid: remaining items in 3-column responsive grid (3 cols desktop, 2 tablet, 1 mobile)
- Each card: title, source badge (colored), topic badge, trending flame, score, author, time

Endpoint (future): `GET /api/items/today` + `GET /api/items`

### `/trending` — Trending

Two sections:
1. **En movimiento** — items with `trending: true`, sorted by score
2. **Top puntuados** — all items sorted by score descending

Same NewsCard component as Latest.

Endpoint (future): `GET /api/items/trending` + `GET /api/items/top`

### `/buscar` — Buscar

- Search input at top
- Results grid below (same NewsCard)
- Filters: topic select, sort by (relevancia, fecha, score)
- Empty state when no query

Endpoint (future): `GET /api/search?q=&topic=&sort_by=`

### `/chat` — Chat

Full-page chat interface:
- Message list with scroll (ScrollArea)
- User messages right-aligned, AI messages left-aligned
- Input bar at bottom (Textarea + Send button)
- Suggestion chips for first interaction ("Que noticias hay de LLMs?", "Resume el trending de hoy", "Que herramientas nuevas hay?")
- Mock AI responses (no SSE streaming yet)

Endpoint (future): `POST /api/chat` (SSE)

## Navigation

- **Desktop (md+):** `AI News | Latest · Trending · Buscar · Chat | [theme toggle]`
- **Mobile (<md):** `AI News | [hamburger] | [theme toggle]` — Sheet/Drawer with nav links

Active route highlighted with `bg-primary text-primary-foreground`.

## Shared Components

- `NewsCard` — reusable news item card (already built)
- `FeaturedCard` — large highlighted card (already built)
- `AppNav` — top navigation (needs mobile hamburger)
- `Layout` — wraps Outlet with nav (already built)
- `ThemeToggle` — dark/light mode (already built)

## Out of Scope (Backlog)

- Backend real connection / JWT auth
- "Para ti" section — user profiles, likes, personalized recommendations
- Improved dedup — cross-source duplicate detection and weighting
- Admin section — briefings, stats, pipeline health
- Login page
- SSE streaming for chat
- Pagination / infinite scroll

## Success Criteria

1. All 4 pages render with mock data
2. Mobile responsive with hamburger nav
3. Dark/light mode works on all pages
4. Topic filtering works on Latest
5. Search filtering works on Buscar
6. Chat shows mock conversation flow

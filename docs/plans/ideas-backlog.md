# Ideas Backlog — Future Features

> Ideas discussed during milestone planning. Not committed to any specific milestone.
> Add new ideas freely. Move to a milestone plan when ready to implement.

---

## Done

- [x] **Trending page/section** — Done (React Trending.tsx with `/api/items/trending` + `/api/items/top`)
- [x] **Theme simplification** — Done (React ThemeToggle, dark/light only, no "system" option)
- [x] ~~**Design fixes (2026-02-19 plan)**~~ — Obsolete (Angular-specific, React frontend is fresh)
- [x] ~~**Mobile bottom nav redesign**~~ — Obsolete (React uses top nav + Sheet drawer)
- [x] **Wire React to real API** — Done (2026-02-24). Login, JWT auth, API client, 4 pages wired, SSE chat
- [x] **Pipeline scheduling + live feeds** — Done (2026-02-25). APScheduler 3-tier jobs, pipeline sources filter, Reddit OAuth, RSS ETags, HF daily_papers, circuit breaker

## In Progress

(nothing currently in progress)

## Frontend — Charts & Analytics

- [ ] **Analytics page**: Use stats endpoints (`by-topic-date`, `by-source-date`,
  `trending-timeline`, `score-distribution`) to build chart visualizations
  - Stacked area chart: topics over time
  - Stacked bar chart: sources over time
  - Sparkline: trending items over time
  - Histogram: score distribution
  - Leaderboard: top items by score

- [ ] **Mini charts in Dashboard**: Sparkline of items per day (last 7 days), topic breakdown
  pie chart for the current day

- [ ] **Chat with inline charts**: LLM returns structured data alongside text, frontend
  detects chart payloads and renders charts inline in the conversation

## Frontend — UX Improvements

- [ ] **Pagination UI controls**: Infinite scroll or pagination buttons for:
  - Dashboard news list
  - Search results
  - Trending lists

- [ ] **"Related news" sidebar**: Use `/api/items/{id}/similar` to show related items
  when clicking on a news card

- [ ] **Source-based browse view**: Use `/api/sources` + `/api/items?source=X` to let
  users browse by source (HackerNews, arXiv, Reddit, etc.)

- [ ] **Archive page**: Historical briefings by date (was in Angular, not yet in React)

- [ ] **Auto-hide nav on scroll**: Top navigation hides when scrolling down,
  reappears when scrolling up. Saves mobile viewport space.

## Backend — Future Endpoints

- [ ] **Semantic search**: Expose vector similarity search as an API endpoint
  (currently only used internally by RAG chat). Different from full-text search —
  finds conceptually similar items even without exact keyword matches.

- [ ] **Item detail endpoint**: `GET /api/items/{id}` — currently no way to fetch a
  single item by ID (only lists). Needed for deep-linking and "related news" flow.

- [ ] **Chat history**: Store and retrieve past chat conversations per session/user.

- [ ] **Alerts/subscriptions**: Let users subscribe to topics or keywords and get
  notified (Telegram/email) when matching items appear.

---

*Last updated: 25 de febrero de 2026*

# Ideas Backlog — Future Features

> Ideas discussed during milestone planning. Not committed to any specific milestone.
> Add new ideas freely. Move to a milestone plan when ready to implement.

---

## Frontend — Charts & Analytics

- [ ] **Analytics page overhaul**: Use new stats endpoints (`by-topic-date`, `by-source-date`,
  `trending-timeline`, `score-distribution`) to build richer Highcharts visualizations
  - Stacked area chart: topics over time
  - Stacked bar chart: sources over time
  - Sparkline: trending items over time
  - Histogram: score distribution
  - Leaderboard: top items by score

- [ ] **Mini charts in Dashboard**: Sparkline of items per day (last 7 days), topic breakdown
  pie chart for the current day

- [ ] **Charts in Archive page**: Pie chart of topic distribution for the selected date

- [ ] **Charts in Search results**: Timeline showing how many results fall on each date
  (useful for seeing trends in search results)

- [ ] **Chat with inline charts**: LLM returns structured data alongside text, frontend
  detects chart payloads and renders Highcharts inline in the conversation. Requires:
  - Backend: Chat SSE new event type `type: "chart"` with chart config/data
  - Frontend: Chart renderer component inside chat messages
  - LLM prompt engineering to produce chart-ready data

## Frontend — Editorial Redesign (Backlog)

- [ ] **Admin/Reader view toggle**: Dashboard switches between Reader (news-first) and
  Admin (pipeline stats) views. Requires user types/roles (not yet implemented).

- [ ] **Mobile bottom nav redesign**: Current Material nav is generic. Redesign with
  editorial aesthetic matching the Stitch dark mode design (DASH, LOGS, bolt, STATS, API).

- [ ] **Theme simplification**: Only dark/light toggle (remove "system" preference option).
  Keep it simple — 2 modes only.

- [ ] **Auto-hide nav on scroll**: Bottom navigation bar should hide when scrolling down
  and reappear when scrolling up. Saves mobile viewport space.

## Frontend — UX Improvements

- [ ] **Pagination UI controls**: Now that all list endpoints support `offset`/`limit`
  and return `X-Total-Count`, add pagination buttons or infinite scroll to:
  - Dashboard news list
  - Archive items
  - Search results

- [ ] **Design fixes (from 2026-02-19 plan)**: 9 pending tasks including stats bar
  mobile scroll, accent marks, light mode card contrast, analytics dark mode charts

- [ ] **"Related news" sidebar**: Use `/api/items/{id}/similar` to show related items
  when clicking on a news card

- [ ] **Source-based browse view**: Use `/api/sources` + `/api/items?source=X` to let
  users browse by source (HackerNews, arXiv, Reddit, etc.)

- [ ] **Trending page/section**: Dedicated trending view using `/api/items/trending`

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

*Last updated: 22 de febrero de 2026*

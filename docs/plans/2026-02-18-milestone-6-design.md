# Milestone 6 — Frontend Polish Design

## Goal

Eliminate code duplication in Angular pages, add missing source badge colors, render markdown in chat, make topic chips interactive, expose topics via API, and widen the layout.

## Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Shared card component | Standalone Angular component with `@Input()` | Eliminates ~120 lines of duplicated template+CSS across 3 pages |
| Markdown rendering | `marked` + DOMPurify | Lightweight (0 deps for marked), secure HTML output |
| Topics endpoint | `GET /api/topics` (no auth) | Topics are public info, drives dropdowns dynamically from config |
| Layout width | 1024px | Analytics charts and dashboard need more space than 800px |
| Topic filter on dashboard | Clickable topic chips filter the items list | Reuses existing computed topicCounts, no API call needed (client-side filter) |

## Components

### 1. NewsItemCard Component (`web/src/app/components/news-item-card.ts`)

Standalone component receiving `@Input() item: NewsItem`. Contains the full card template (source badge, score, topic badge, trending badge, title link, summary, meta) and all associated CSS. Includes badge colors for all 6 sources (hackernews, arxiv, reddit, rss, github, huggingface).

### 2. Dashboard Topic Filter (`web/src/app/pages/dashboard.ts`)

Topic chips become clickable. A `selectedTopic` signal controls filtering. Clicking a chip sets it active; clicking again clears the filter. The items list is filtered client-side via a computed signal.

### 3. Archive Topic Filter (`web/src/app/pages/archive.ts`)

Add a topic dropdown (same as search page has) that filters the briefing items client-side.

### 4. Chat Markdown Rendering (`web/src/app/pages/chat.ts`)

Install `marked` and `dompurify`. Convert assistant message content from markdown to sanitized HTML. Display with `[innerHTML]`. Add CSS for rendered elements (code blocks, lists, bold, links).

### 5. Topics API Endpoint (`src/api/routes/topics.py`)

`GET /api/topics` returns `{"topics": ["modelos", "herramientas", ...]}` from `Settings.topics`. No auth required. Register in `src/api/app.py`.

### 6. NewsService Topics (`web/src/app/services/news.service.ts`)

Add `getTopics()` method. Chat and search pages consume it instead of hardcoded arrays.

### 7. Layout Width (`web/src/app/app.ts`)

Change `main.with-nav` from `max-width: 800px` to `max-width: 1024px`.

## File Map

| File | Action |
|---|---|
| `web/src/app/components/news-item-card.ts` | Create |
| `web/src/app/pages/dashboard.ts` | Modify (use card, clickable topics) |
| `web/src/app/pages/archive.ts` | Modify (use card, topic dropdown) |
| `web/src/app/pages/search.ts` | Modify (use card, topics from API) |
| `web/src/app/pages/chat.ts` | Modify (markdown rendering, topics from API) |
| `web/src/app/app.ts` | Modify (layout width 1024px) |
| `web/src/app/services/news.service.ts` | Modify (add getTopics()) |
| `src/api/routes/topics.py` | Create |
| `src/api/app.py` | Modify (register topics router) |
| `tests/unit/test_topics_api.py` | Create |
| `tests/e2e/test_dashboard.py` | Modify (topic filter test) |

## Verification

1. `pytest tests/` — all tests pass (including new topics API test)
2. `cd web && npx ng build` — Angular build succeeds
3. Dashboard topic chips are clickable and filter the list
4. Chat renders markdown (bold, lists, code blocks) correctly
5. GitHub and HuggingFace badges have distinct colors
6. Layout is wider (1024px)

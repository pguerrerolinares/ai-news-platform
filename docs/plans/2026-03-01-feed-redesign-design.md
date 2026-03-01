# Feed Redesign — Design Document

**Status**: Draft
**Date**: 2026-03-01

## Problem

Current navigation (Latest / Trending / Search / Chat) creates confusion:
- "Latest" and "Trending" show overlapping content in different arrangements
- "Featured" card in Latest duplicates "Top Scored" in Trending
- "Gaining Traction" naming is vague
- Users want a quick 30-second scan, not a chronological dump

## Solution

Three clear sections replacing the current four:

| Section | Purpose | Mental model |
|---------|---------|-------------|
| **Feed** (`/`) | Twitter-like timeline, relevance-sorted, balanced across content types | "What's happening now?" |
| **Top** (`/top`) | Leaderboard by time period | "What's been most important?" |
| **Search** (`/search`) | Find specific news | "I'm looking for X" |

**Removed**: Chat page, Trending page. Chat can be re-added later as a floating panel if needed.

## Content Type Balance

Topics map to three content families (priority order):

| Family | Topics | Priority |
|--------|--------|----------|
| News | models, products, regulation, agents | Highest |
| Projects | tools, open_source | Medium |
| Papers | papers | Lower |

The feed sorting algorithm should ensure variety: `relevance = score × recency_decay`. Natural score distribution across topics provides balance. Topic filter chips let users focus on specific areas.

## Section 1: Feed (Home)

### Layout

```
┌─────────────────────────────────────────────────────┐
│  AI News  |  Feed · Top · Search    [☀] [⚙] [→]    │  header
├─────────────────────────────────────────────────────┤
│                                                     │
│  ┌─────────────────────────────────────────────┐    │
│  │ [All] [Models] [Tools] [Papers] [Products]  │    │  ToggleGroup
│  │ [Open Source] [Agents] [Regulation]          │    │  (horizontal scroll on mobile)
│  └─────────────────────────────────────────────┘    │
│                                                     │
│  ┌─────────────────────────────────────────────┐    │
│  │  GPT-5 announced with multimodal...         │    │  Card
│  │  OpenAI Blog · 3h ago                       │    │  - title (font-medium)
│  │  [Models] [rss]                    ↑ 42     │    │  - source + relative time
│  └─────────────────────────────────────────────┘    │  - topic Badge + source Badge
│                                                     │  - score indicator
│  ┌─────────────────────────────────────────────┐    │
│  │  LangGraph 0.5 released...                  │    │
│  │  GitHub · 5h ago                             │    │
│  │  [Tools] [github]                  ↑ 38     │    │
│  └─────────────────────────────────────────────┘    │
│                                                     │
│           ···  infinite scroll  ···                  │
└─────────────────────────────────────────────────────┘
```

### Components

| Element | shadcn Component | Notes |
|---------|-----------------|-------|
| Topic filter | `ToggleGroup` (type="single") | "all" as default, wrap in `ScrollArea` horizontal on mobile |
| News card | `Card` | Simplified: title + meta line + badges + score |
| Topic label | `Badge` (variant="outline") | Colored per topic |
| Source label | `Badge` (variant="secondary") | Colored per source (existing SOURCE_COLORS) |
| Score | Text with `IconArrowUp` | Right-aligned, muted unless high |
| Loading | `Skeleton` cards | 3 skeleton cards on initial load |
| Infinite scroll | IntersectionObserver | Keep existing pattern |

### Backend

New query parameter on `GET /api/items/latest`:
- `sort=relevance` → `ORDER BY score DESC NULLS LAST, effective_date DESC`
- `sort=recent` → `ORDER BY effective_date DESC` (current behavior, fallback)

Default: `sort=relevance`.

No new endpoint needed — just a sort parameter.

## Section 2: Top

### Layout

```
┌─────────────────────────────────────────────────────┐
│                                                     │
│  Top                                                │
│  The most relevant news                             │
│                                                     │
│  ┌──────────────────────────────────────┐           │
│  │ [24h] [1w] [1m] [3m] [1y] [All]     │           │  Tabs
│  └──────────────────────────────────────┘           │
│                                                     │
│  ┌──────────────────────────────────────┐           │
│  │ [All] [Models] [Tools] [Papers] ...  │           │  ToggleGroup
│  └──────────────────────────────────────┘           │
│                                                     │
│  ┌───────┐ ┌───────┐ ┌───────┐                     │
│  │ #1    │ │ #2    │ │ #3    │                     │  Grid of Cards
│  │ ↑85   │ │ ↑72   │ │ ↑64   │                     │  (fixed count, no infinite scroll)
│  └───────┘ └───────┘ └───────┘                     │
│  ┌───────┐ ┌───────┐ ┌───────┐                     │
│  │ #4    │ │ #5    │ │ #6    │                     │
│  └───────┘ └───────┘ └───────┘                     │
└─────────────────────────────────────────────────────┘
```

### Components

| Element | shadcn Component | Notes |
|---------|-----------------|-------|
| Time period | `Tabs` / `TabsList` / `TabsTrigger` | 24h, 1w, 1m, 3m, 1y, All |
| Topic filter | `ToggleGroup` | Same as Feed |
| Cards | `Card` | Same card component as Feed, with ranking number overlay |
| Empty state | Centered muted text | "No items for this period" |

### Backend

Reuse `GET /api/items/top` with `days` parameter:
- 24h → `days=1`
- 1w → `days=7`
- 1m → `days=30`
- 3m → `days=90`
- 1y → `days=365`
- All → `days=3650` (or new `all=true` param)

Add topic filter support (already exists as `topic` query param).

## Section 3: Search

Keep current implementation. No changes needed.

## Section 4: Navigation

### Header

```
[AI News]  |  Feed · Top · Search          [☀] [⚙] [↪]
```

- 3 nav links with animated active indicator (keep existing `motion.span layoutId`)
- Right side: theme toggle, settings icon, logout icon
- Mobile: hamburger → Sheet with 3 links

### Routes

| Route | Component | Auth |
|-------|-----------|------|
| `/` | Feed | Required |
| `/top` | Top | Required |
| `/search` | Search | Required |
| `/settings` | Settings | Required |
| `/login` | Login | Public |

### Removed

- `/trending` route and page
- `/chat` route and page
- Chat component and dependencies (can be re-added as floating panel later)

## Migration Plan

1. Add `sort` query param to `/api/items/latest` endpoint
2. Refactor `Dashboard.tsx` → `Feed.tsx` (topic chips, relevance sort, simplified cards)
3. Refactor `Trending.tsx` → `Top.tsx` (time period tabs, topic filter)
4. Update `App.tsx` routes
5. Update `app-nav.tsx` links
6. Remove Chat page and unused imports
7. Update i18n keys

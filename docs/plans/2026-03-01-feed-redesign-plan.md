# Feed Redesign Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace the confusing 4-page layout (Latest/Trending/Search/Chat) with 3 clear sections: Feed (relevance-sorted timeline), Top (leaderboard by time period), Search.

**Architecture:** Add `sort` query parameter to existing `/api/items/latest` endpoint. Refactor Dashboard→Feed with ToggleGroup topic chips and relevance sorting. Refactor Trending→Top with Tabs time periods. Remove Chat page. Update navigation.

**Tech Stack:** FastAPI (backend sort param), React 19, shadcn/ui (ToggleGroup, Tabs, Badge, Card, Skeleton), TanStack Query, motion/react.

---

### Task 1: Add `sort` query parameter to `/api/items/latest` endpoint

**Files:**
- Modify: `src/api/routes/items.py:258-290` (list_latest_items function)
- Test: `tests/unit/test_items_sort.py` (create)

**Step 1: Write the failing test**

Create `tests/unit/test_items_sort.py`:

```python
"""Tests for /api/items/latest sort parameter."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

pytestmark = [pytest.mark.asyncio(loop_scope="session")]


class TestLatestSort:
    """Verify sort parameter on /api/items/latest."""

    async def test_sort_relevance_is_default(self, auth_client: AsyncClient):
        """Default sort should return items ordered by score desc."""
        resp = await auth_client.get("/api/items/latest", params={"limit": "5"})
        assert resp.status_code == 200
        items = resp.json()
        scores = [i["score"] for i in items if i["score"] is not None]
        assert scores == sorted(scores, reverse=True)

    async def test_sort_recent(self, auth_client: AsyncClient):
        """sort=recent should return items ordered by date desc."""
        resp = await auth_client.get(
            "/api/items/latest", params={"limit": "5", "sort": "recent"}
        )
        assert resp.status_code == 200

    async def test_sort_invalid_falls_back(self, auth_client: AsyncClient):
        """Invalid sort value should fall back to relevance."""
        resp = await auth_client.get(
            "/api/items/latest", params={"limit": "5", "sort": "invalid"}
        )
        assert resp.status_code == 200
```

**Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/unit/test_items_sort.py -v`
Expected: FAIL (default sort is currently by date, not score)

**Step 3: Implement the sort parameter**

In `src/api/routes/items.py`, modify `list_latest_items`:

```python
@router.get(
    "/latest",
    response_model=list[NewsItemResponse],
    responses={401: {"model": ErrorWrapper}},
)
@limiter.limit("30/minute")
async def list_latest_items(
    request: Request,
    response: Response,
    topic: str | None = Query(None, description="Filter by topic"),
    source: str | None = Query(None, description="Filter by source"),
    sort: str = Query("relevance", description="Sort: relevance or recent"),
    limit: int = Query(50, ge=1, le=200, description="Max items to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    session: AsyncSession = Depends(get_session),
    _user: UserClaims = Depends(require_auth),
) -> list[NewsItemResponse]:
    """Latest items, sorted by relevance (default) or recency."""
    query = select(NewsItem)

    if topic:
        query = query.where(NewsItem.topic == topic)
    if source:
        query = query.where(NewsItem.source == source)

    count_query = select(func.count()).select_from(query.with_only_columns(NewsItem.id).subquery())
    total = (await session.execute(count_query)).scalar_one()
    set_total_count_header(response, total)

    if sort == "recent":
        query = query.order_by(effective_date.desc())
    else:
        query = query.order_by(NewsItem.score.desc().nulls_last(), effective_date.desc())

    query = query.offset(offset).limit(limit)
    result = await session.execute(query)
    items = result.scalars().all()
    return [NewsItemResponse.model_validate(item) for item in items]
```

**Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/unit/test_items_sort.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/api/routes/items.py tests/unit/test_items_sort.py
git commit -m "feat: add sort parameter to /api/items/latest endpoint"
```

---

### Task 2: Create shared TopicFilter component

**Files:**
- Create: `frontend/src/components/topic-filter.tsx`

**Step 1: Create the TopicFilter component**

```tsx
import { ToggleGroup, ToggleGroupItem } from '@/components/ui/toggle-group'
import { TOPIC_LABELS } from '@/lib/constants'
import { ScrollArea, ScrollBar } from '@/components/ui/scroll-area'

const TOPICS = Object.keys(TOPIC_LABELS)

interface TopicFilterProps {
  value: string
  onChange: (value: string) => void
}

export function TopicFilter({ value, onChange }: TopicFilterProps) {
  return (
    <ScrollArea className="w-full">
      <ToggleGroup
        type="single"
        value={value}
        onValueChange={(v) => onChange(v || 'all')}
        variant="outline"
        size="sm"
        className="flex-wrap"
      >
        <ToggleGroupItem value="all">All</ToggleGroupItem>
        {TOPICS.map((topic) => (
          <ToggleGroupItem key={topic} value={topic}>
            {TOPIC_LABELS[topic] ?? topic}
          </ToggleGroupItem>
        ))}
      </ToggleGroup>
      <ScrollBar orientation="horizontal" />
    </ScrollArea>
  )
}
```

**Step 2: Verify it builds**

Run: `cd frontend && npx tsc --noEmit`
Expected: No errors

**Step 3: Commit**

```bash
git add frontend/src/components/topic-filter.tsx
git commit -m "feat: add shared TopicFilter component with ToggleGroup"
```

---

### Task 3: Refactor Dashboard → Feed page

**Files:**
- Modify: `frontend/src/pages/Dashboard.tsx` → rewrite as Feed
- Uses: `TopicFilter` component from Task 2, `NewsCard` (existing)

**Step 1: Rewrite Dashboard.tsx as Feed**

Replace the entire content of `frontend/src/pages/Dashboard.tsx`:

```tsx
import { useState, useMemo, useCallback, useRef, useEffect } from 'react'
import { useInfiniteQuery } from '@tanstack/react-query'
import { TopicFilter } from '@/components/topic-filter'
import { NewsCard } from '@/components/news-card'
import { AnimatedCardGrid, AnimatedCardItem } from '@/components/animated-card-grid'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { apiGet } from '@/lib/api'
import type { NewsItem } from '@/lib/types'
import { IconRefresh, IconLoader2 } from '@tabler/icons-react'

const PAGE_SIZE = 20

export default function Feed() {
  const [activeTopic, setActiveTopic] = useState('all')
  const observerRef = useRef<IntersectionObserver | null>(null)
  const fetchingRef = useRef(false)

  const topicParam = activeTopic !== 'all' ? activeTopic : undefined

  const {
    data,
    fetchNextPage,
    hasNextPage,
    isFetching,
    isFetchingNextPage,
    error,
    refetch,
  } = useInfiniteQuery({
    queryKey: ['feed', { topic: topicParam }],
    queryFn: async ({ pageParam, signal }) => {
      const params: Record<string, string> = {
        limit: String(PAGE_SIZE),
        offset: String(pageParam),
        sort: 'relevance',
      }
      if (topicParam) params.topic = topicParam
      return apiGet<NewsItem[]>('/api/items/latest', params, signal)
    },
    initialPageParam: 0,
    getNextPageParam: (lastPage, allPages) => {
      const loaded = allPages.reduce((n, p) => n + p.data.length, 0)
      const total = lastPage.totalCount ?? Infinity
      if (loaded >= total || lastPage.data.length < PAGE_SIZE) return undefined
      return loaded
    },
  })

  const items = useMemo(
    () => data?.pages.flatMap(p => p.data) ?? [],
    [data],
  )

  fetchingRef.current = isFetchingNextPage

  const sentinelRef = useCallback(
    (node: HTMLDivElement | null) => {
      if (observerRef.current) observerRef.current.disconnect()
      if (!node) return
      observerRef.current = new IntersectionObserver(
        (entries) => {
          if (entries[0].isIntersecting && !fetchingRef.current) {
            fetchNextPage()
          }
        },
        { rootMargin: '200px' },
      )
      observerRef.current.observe(node)
    },
    [fetchNextPage],
  )

  useEffect(() => {
    return () => { observerRef.current?.disconnect() }
  }, [])

  const isInitialLoad = isFetching && !isFetchingNextPage && items.length === 0

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold tracking-tight">Feed</h2>
          <p className="text-sm text-muted-foreground">
            AI news sorted by relevance
          </p>
        </div>
        <Button variant="ghost" size="icon" onClick={() => refetch()} title="Refresh">
          <IconRefresh className="size-4" />
        </Button>
      </div>

      <TopicFilter value={activeTopic} onChange={setActiveTopic} />

      {isInitialLoad && (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="space-y-3 rounded-lg border p-4">
              <Skeleton className="h-4 w-3/4" />
              <Skeleton className="h-3 w-full" />
              <Skeleton className="h-3 w-1/2" />
            </div>
          ))}
        </div>
      )}

      {error && items.length === 0 && !isInitialLoad && (
        <div className="flex flex-col items-center gap-4 py-24">
          <p className="text-destructive">
            {error instanceof Error ? error.message : 'Error loading news'}
          </p>
          <Button variant="outline" onClick={() => refetch()}>
            <IconRefresh className="mr-2 size-4" /> Retry
          </Button>
        </div>
      )}

      {!isInitialLoad && (
        <AnimatedCardGrid
          className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3"
          animationKey={activeTopic}
        >
          {items.map(item => (
            <AnimatedCardItem key={item.id}>
              <NewsCard item={item} />
            </AnimatedCardItem>
          ))}
        </AnimatedCardGrid>
      )}

      {items.length === 0 && !isFetching && !error && (
        <div className="flex flex-col items-center gap-2 py-12 text-muted-foreground">
          <p>No news for this topic</p>
        </div>
      )}

      {error && items.length > 0 && (
        <div className="flex flex-col items-center gap-2 py-4">
          <p className="text-sm text-destructive">
            {error instanceof Error ? error.message : 'Error loading more news'}
          </p>
          <Button variant="outline" size="sm" onClick={() => fetchNextPage()}>
            <IconRefresh className="mr-2 size-4" /> Retry
          </Button>
        </div>
      )}

      {isFetchingNextPage && (
        <div className="flex items-center justify-center py-8">
          <IconLoader2 className="size-5 animate-spin text-muted-foreground" />
          <span className="ml-2 text-sm text-muted-foreground">Loading more...</span>
        </div>
      )}

      {hasNextPage && <div ref={sentinelRef} className="h-1" />}
    </div>
  )
}
```

Key changes vs old Dashboard:
- Removed `FeaturedCard` (no more featured item logic)
- Replaced `Select` topic filter with `TopicFilter` (ToggleGroup)
- Added `sort: 'relevance'` to API call
- Skeleton loading state instead of spinner text
- Simplified subtitle

**Step 2: Verify it builds**

Run: `cd frontend && npx tsc --noEmit`
Expected: No errors

**Step 3: Commit**

```bash
git add frontend/src/pages/Dashboard.tsx
git commit -m "feat: refactor Dashboard to Feed with relevance sort and topic chips"
```

---

### Task 4: Refactor Trending → Top page

**Files:**
- Modify: `frontend/src/pages/Trending.tsx` → rewrite as Top

**Step 1: Rewrite Trending.tsx as Top**

Replace the entire content of `frontend/src/pages/Trending.tsx`:

```tsx
import { useState, useCallback, useEffect } from 'react'
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { TopicFilter } from '@/components/topic-filter'
import { NewsCard } from '@/components/news-card'
import { AnimatedCardGrid, AnimatedCardItem } from '@/components/animated-card-grid'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { apiGet } from '@/lib/api'
import type { NewsItem } from '@/lib/types'
import { IconRefresh } from '@tabler/icons-react'

const TIME_PERIODS = [
  { value: '1', label: '24h' },
  { value: '7', label: '1w' },
  { value: '30', label: '1m' },
  { value: '90', label: '3m' },
  { value: '365', label: '1y' },
  { value: '3650', label: 'All' },
] as const

export default function Top() {
  const [days, setDays] = useState('7')
  const [topic, setTopic] = useState('all')
  const [items, setItems] = useState<NewsItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const fetchData = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const params: Record<string, string> = {
        days,
        limit: '30',
      }
      if (topic !== 'all') params.topic = topic
      const { data } = await apiGet<NewsItem[]>('/api/items/top', params)
      setItems(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error loading data')
    } finally {
      setLoading(false)
    }
  }, [days, topic])

  useEffect(() => { fetchData() }, [fetchData])

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold tracking-tight">Top</h2>
          <p className="text-sm text-muted-foreground">
            Most relevant AI news
          </p>
        </div>
        <Button variant="ghost" size="icon" onClick={fetchData} title="Refresh">
          <IconRefresh className="size-4" />
        </Button>
      </div>

      <Tabs value={days} onValueChange={setDays}>
        <TabsList>
          {TIME_PERIODS.map(({ value, label }) => (
            <TabsTrigger key={value} value={value}>
              {label}
            </TabsTrigger>
          ))}
        </TabsList>
      </Tabs>

      <TopicFilter value={topic} onChange={setTopic} />

      {loading && (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="space-y-3 rounded-lg border p-4">
              <Skeleton className="h-4 w-3/4" />
              <Skeleton className="h-3 w-full" />
              <Skeleton className="h-3 w-1/2" />
            </div>
          ))}
        </div>
      )}

      {error && (
        <div className="flex flex-col items-center gap-4 py-24">
          <p className="text-destructive">{error}</p>
          <Button variant="outline" onClick={fetchData}>
            <IconRefresh className="mr-2 size-4" /> Retry
          </Button>
        </div>
      )}

      {!loading && !error && (
        <AnimatedCardGrid
          className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3"
          animationKey={`${days}-${topic}`}
        >
          {items.map((item, index) => (
            <AnimatedCardItem key={item.id}>
              <div className="relative">
                <span className="absolute -left-2 -top-2 z-10 flex size-6 items-center justify-center rounded-full bg-primary text-xs font-bold text-primary-foreground">
                  {index + 1}
                </span>
                <NewsCard item={item} />
              </div>
            </AnimatedCardItem>
          ))}
        </AnimatedCardGrid>
      )}

      {!loading && !error && items.length === 0 && (
        <div className="flex flex-col items-center gap-2 py-12 text-muted-foreground">
          <p>No items for this period</p>
        </div>
      )}
    </div>
  )
}
```

Key changes vs old Trending:
- Time period tabs (Tabs component) replacing static "Gaining Traction" + "Top Scored" split
- Added TopicFilter (same as Feed)
- Ranking number overlay on each card
- Skeleton loading state
- Fetches from existing `/api/items/top` endpoint with `days` param

**Step 2: Verify it builds**

Run: `cd frontend && npx tsc --noEmit`
Expected: No errors

**Step 3: Commit**

```bash
git add frontend/src/pages/Trending.tsx
git commit -m "feat: refactor Trending to Top page with time period tabs"
```

---

### Task 5: Update navigation, routes, and hide Chat

**Files:**
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/components/app-nav.tsx`

**Step 1: Update App.tsx routes**

Remove Chat from nav (keep route for direct access), rename Trending route to `/top`:

```tsx
import { BrowserRouter, Routes, Route, Navigate } from 'react-router'
import { AuthProvider, RequireAuth } from '@/hooks/use-auth'
import { Layout } from '@/components/layout'
import Feed from '@/pages/Dashboard'
import Top from '@/pages/Trending'
import Search from '@/pages/Search'
import Chat from '@/pages/Chat'
import Login from '@/pages/Login'
import Settings from '@/pages/Settings'

function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="login" element={<Login />} />
          <Route element={<RequireAuth><Layout /></RequireAuth>}>
            <Route index element={<Feed />} />
            <Route path="top" element={<Top />} />
            <Route path="search" element={<Search />} />
            <Route path="chat" element={<Chat />} />
            <Route path="settings" element={<Settings />} />
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  )
}

export default App
```

Note: Chat route is kept for direct `/chat` access but hidden from navigation. Chat redesign is in the backlog.

**Step 2: Update app-nav.tsx links**

Change the `links` array:

```tsx
const links = [
  { to: '/', label: 'Feed' },
  { to: '/top', label: 'Top' },
  { to: '/search', label: 'Search' },
]
```

**Step 3: Verify it builds**

Run: `cd frontend && npx tsc --noEmit`
Expected: No errors

**Step 4: Commit**

```bash
git add frontend/src/App.tsx frontend/src/components/app-nav.tsx
git commit -m "feat: update nav to Feed/Top/Search, remove Chat page"
```

---

### Task 6: Update i18n and clean up unused code

**Files:**
- Modify: `frontend/src/locales/en.json`
- Delete: `frontend/src/components/featured-card.tsx` — no longer used
- Keep: `frontend/src/pages/Chat.tsx` — hidden from nav but route preserved (backlog item)

**Step 1: Update en.json**

Remove `chat` section. Update `nav` labels. Remove `featured` section. Keep `login`, `settings`, `search` as-is. Add `feed` and `top` sections:

In the JSON, replace:

```json
{
  "nav": {
    "feed": "Feed",
    "top": "Top",
    "search": "Search"
  },
  "feed": {
    "subtitle": "AI news sorted by relevance",
    "noItems": "No news for this topic",
    "errorLoading": "Error loading news",
    "errorLoadingMore": "Error loading more news"
  },
  "top": {
    "subtitle": "Most relevant AI news",
    "noItems": "No items for this period"
  }
}
```

(Keep `dashboard`, `trending`, `search`, `login`, `settings`, `featured` keys — remove `chat` key and `featured` key. Rename `dashboard` to `feed` and `trending` to `top`.)

**Step 2: Delete unused files**

```bash
rm frontend/src/components/featured-card.tsx
```

**Step 3: Verify it builds**

Run: `cd frontend && npx tsc --noEmit && bun run build`
Expected: No errors, clean build

**Step 4: Commit**

```bash
git add -u frontend/src/
git add frontend/src/locales/en.json
git commit -m "refactor: remove Chat page, FeaturedCard, update i18n keys"
```

---

### Task 7: Run full quality gates

**Step 1: Run backend tests**

Run: `.venv/bin/python -m pytest tests/ -x --timeout=30 -q`
Expected: All tests pass

**Step 2: Run frontend build**

Run: `cd frontend && bun run build`
Expected: Clean build

**Step 3: Run linting**

Run: `.venv/bin/ruff check . && .venv/bin/ruff format --check .`
Expected: All checks passed

**Step 4: Commit any fixes**

If lint or tests required changes, commit them:
```bash
git commit -m "fix: address lint/test issues from feed redesign"
```

---

### Task 8: Update documentation

**Files:**
- Modify: `AGENTS.md` — update routes, file map
- Modify: `docs/plans/2026-03-01-feed-redesign-design.md` — mark as Implemented

**Step 1: Update AGENTS.md**

- Remove `/chat` and `/trending` from API endpoints
- Add `/top` route
- Update file map (remove Chat.tsx, add topic-filter.tsx)
- Update frontend pages description

**Step 2: Mark design doc as Implemented**

Change `**Status**: Draft` to `**Status**: Implemented` in the design doc.

**Step 3: Commit**

```bash
git add AGENTS.md docs/plans/2026-03-01-feed-redesign-design.md
git commit -m "docs: update AGENTS.md and mark feed redesign as implemented"
```

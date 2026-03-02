# Timeline Section Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a `/timeline` page with a heatmap calendar and topic-grouped items per date.

**Architecture:** Backend adds `date_from`/`date_to` params to 2 stats endpoints. Frontend adds 3 new components: calendar heatmap, topic group, and Timeline page. All wired via existing API client.

**Tech Stack:** Python/FastAPI (backend), React 19 + TypeScript + Tailwind (frontend), Shadcn UI components, Framer Motion animations.

---

### Task 1: Backend — Add date_from/date_to to `/stats/by-date`

**Files:**
- Modify: `src/api/routes/stats.py` (the `stats_by_date` endpoint)
- Test: `tests/unit/test_stats_api.py`

**Step 1: Write the failing tests**

In `tests/unit/test_stats_api.py`, add to the `TestStatsByDate` class:

```python
async def test_by_date_with_date_range(self, api_client: AsyncClient) -> None:
    resp = await api_client.get(
        "/api/stats/by-date",
        params={"date_from": "2026-01-01", "date_to": "2026-01-31"},
    )
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)

async def test_by_date_date_from_without_date_to_rejected(
    self, api_client: AsyncClient
) -> None:
    resp = await api_client.get(
        "/api/stats/by-date", params={"date_from": "2026-01-01"}
    )
    assert resp.status_code == 422

async def test_by_date_invalid_date_format_rejected(
    self, api_client: AsyncClient
) -> None:
    resp = await api_client.get(
        "/api/stats/by-date",
        params={"date_from": "not-a-date", "date_to": "2026-01-31"},
    )
    assert resp.status_code == 422

async def test_by_date_date_range_ignores_days(
    self, api_client: AsyncClient
) -> None:
    """When date_from/date_to are provided, days param is ignored."""
    resp = await api_client.get(
        "/api/stats/by-date",
        params={"date_from": "2026-01-01", "date_to": "2026-01-31", "days": "7"},
    )
    assert resp.status_code == 200
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/test_stats_api.py::TestStatsByDate -v`
Expected: FAIL — `date_from` and `date_to` params not recognized (422 for valid ones).

**Step 3: Implement the date range params**

In `src/api/routes/stats.py`, modify the `stats_by_date` endpoint signature and body. Add `date_from` and `date_to` as optional `date` query params. When both are provided, build the date filter from them instead of `days`. Validate that both must be provided together using a manual check that returns 422.

```python
from datetime import date as date_type

@router.get("/by-date", response_model=list[StatsDateResponse])
@limiter.limit("30/minute")
async def stats_by_date(
    request: Request,
    session: AsyncSession = Depends(get_session),
    _user: UserClaims = Depends(require_auth),
    days: int = Query(default=30, ge=1, le=365),
    date_from: date_type | None = Query(default=None),
    date_to: date_type | None = Query(default=None),
) -> list[StatsDateResponse]:
    if (date_from is None) != (date_to is None):
        raise HTTPException(
            status_code=422,
            detail="date_from and date_to must both be provided or both omitted",
        )

    eff_date = func.date(effective_date)

    if date_from and date_to:
        from_dt = datetime.combine(date_from, time.min, tzinfo=UTC)
        to_dt = datetime.combine(date_to, time(23, 59, 59), tzinfo=UTC)
        date_filter = (effective_date >= from_dt) & (effective_date <= to_dt)
    else:
        since = datetime.combine(
            datetime.now(tz=UTC).date() - timedelta(days=days), time.min, tzinfo=UTC
        )
        date_filter = effective_date >= since

    result = await session.execute(
        select(
            eff_date.label("date"),
            func.count(NewsItem.id).label("count"),
        )
        .where(date_filter)
        .group_by(eff_date)
        .order_by(eff_date.desc())
    )
    return [StatsDateResponse(date=row.date, count=row.count) for row in result.all()]
```

Note: Import `HTTPException` from `fastapi` if not already imported. Import `date as date_type` from `datetime`.

**Step 4: Run tests to verify they pass**

Run: `pytest tests/unit/test_stats_api.py::TestStatsByDate -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add src/api/routes/stats.py tests/unit/test_stats_api.py
git commit -m "feat: add date_from/date_to params to /stats/by-date endpoint"
```

---

### Task 2: Backend — Add date_from/date_to to `/stats/by-topic-date`

**Files:**
- Modify: `src/api/routes/stats.py` (the `stats_by_topic_date` endpoint)
- Test: `tests/unit/test_stats_api.py`

**Step 1: Write the failing tests**

In `tests/unit/test_stats_api.py`, add to the `TestStatsByTopicDate` class (or create it):

```python
async def test_by_topic_date_with_date_range(self, api_client: AsyncClient) -> None:
    resp = await api_client.get(
        "/api/stats/by-topic-date",
        params={"date_from": "2026-01-01", "date_to": "2026-01-31"},
    )
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)

async def test_by_topic_date_date_from_without_date_to_rejected(
    self, api_client: AsyncClient
) -> None:
    resp = await api_client.get(
        "/api/stats/by-topic-date", params={"date_from": "2026-01-01"}
    )
    assert resp.status_code == 422
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/test_stats_api.py::TestStatsByTopicDate -v`
Expected: FAIL

**Step 3: Implement the date range params**

Apply the same pattern from Task 1 to `stats_by_topic_date`. Add `date_from`/`date_to` params, validate both-or-neither, build the date filter accordingly. The query is the same structure but with `.group_by(eff_date, NewsItem.topic)`.

```python
@router.get("/by-topic-date", response_model=list[StatsGroupDateResponse])
@limiter.limit("30/minute")
async def stats_by_topic_date(
    request: Request,
    session: AsyncSession = Depends(get_session),
    _user: UserClaims = Depends(require_auth),
    days: int = Query(default=30, ge=1, le=365),
    date_from: date_type | None = Query(default=None),
    date_to: date_type | None = Query(default=None),
) -> list[StatsGroupDateResponse]:
    if (date_from is None) != (date_to is None):
        raise HTTPException(
            status_code=422,
            detail="date_from and date_to must both be provided or both omitted",
        )

    eff_date = func.date(effective_date)

    if date_from and date_to:
        from_dt = datetime.combine(date_from, time.min, tzinfo=UTC)
        to_dt = datetime.combine(date_to, time(23, 59, 59), tzinfo=UTC)
        date_filter = (effective_date >= from_dt) & (effective_date <= to_dt)
    else:
        since = datetime.combine(
            (datetime.now(tz=UTC) - timedelta(days=days)).date(), time.min, tzinfo=UTC
        )
        date_filter = effective_date >= since

    result = await session.execute(
        select(
            eff_date.label("date"),
            NewsItem.topic.label("group"),
            func.count(NewsItem.id).label("count"),
        )
        .where(date_filter & NewsItem.topic.isnot(None))
        .group_by(eff_date, NewsItem.topic)
        .order_by(eff_date.asc(), NewsItem.topic.asc())
    )
    return [
        StatsGroupDateResponse(date=row.date, group=row.group, count=row.count)
        for row in result.all()
    ]
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/unit/test_stats_api.py -v -k "topic_date"`
Expected: ALL PASS

**Step 5: Run full backend quality gate**

Run: `ruff check src/api/routes/stats.py && ruff format --check src/api/routes/stats.py && pyright src/api/routes/stats.py && pytest tests/unit/test_stats_api.py -v`
Expected: All clean

**Step 6: Commit**

```bash
git add src/api/routes/stats.py tests/unit/test_stats_api.py
git commit -m "feat: add date_from/date_to params to /stats/by-topic-date endpoint"
```

---

### Task 3: Frontend — Add route and nav link

**Files:**
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/components/app-nav.tsx`
- Create: `frontend/src/pages/Timeline.tsx` (placeholder)

**Step 1: Create placeholder Timeline page**

```tsx
export default function Timeline() {
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold tracking-tight">Timeline</h1>
      <p className="text-muted-foreground">Coming soon.</p>
    </div>
  )
}
```

**Step 2: Add route to App.tsx**

Import `Timeline` lazily and add route inside the authenticated `<Route>` group, after the search route:

```tsx
const Timeline = lazy(() => import('./pages/Timeline'))
// In the Routes:
<Route path="timeline" element={<Timeline />} />
```

Check how other pages are imported — if they use `lazy()`, follow the same pattern. If they're direct imports, use direct import.

**Step 3: Add nav link to app-nav.tsx**

Add to the `links` array, after the Search entry:

```tsx
{ to: '/timeline', label: 'Timeline' },
```

**Step 4: Verify it renders**

Run: `cd frontend && npm run build`
Expected: Build succeeds with no errors.

**Step 5: Commit**

```bash
git add frontend/src/pages/Timeline.tsx frontend/src/App.tsx frontend/src/components/app-nav.tsx
git commit -m "feat: add Timeline route and nav link (placeholder page)"
```

---

### Task 4: Frontend — Add API types for stats responses

**Files:**
- Modify: `frontend/src/lib/types.ts`

**Step 1: Add stats response types**

Check if these types already exist in `types.ts`. If not, add:

```tsx
export interface StatsDateItem {
  date: string
  count: number
}

export interface StatsGroupDateItem {
  date: string
  group: string
  count: number
}
```

**Step 2: Verify build**

Run: `cd frontend && npm run build`
Expected: Build succeeds.

**Step 3: Commit**

```bash
git add frontend/src/lib/types.ts
git commit -m "feat: add StatsDateItem and StatsGroupDateItem types"
```

---

### Task 5: Frontend — Calendar heatmap component

**Files:**
- Create: `frontend/src/components/calendar-heatmap.tsx`

**Step 1: Build the calendar heatmap component**

This component renders a month calendar grid with:
- Month/year header with `<` and `>` navigation buttons
- Day-of-week headers (Mo Tu We Th Fr Sa Su)
- Date cells with activity dots (relative to month's max)
- Selected date highlighting
- Click handler for date selection

Props:
```tsx
interface CalendarHeatmapProps {
  /** Counts per date for the displayed month, e.g. {"2026-03-01": 5, "2026-03-02": 42} */
  dateCounts: Record<string, number>
  /** Currently selected date as ISO string (YYYY-MM-DD) */
  selectedDate: string
  /** Currently displayed year */
  year: number
  /** Currently displayed month (1-12) */
  month: number
  /** Called when user clicks a date */
  onDateSelect: (dateStr: string) => void
  /** Called when user navigates to a different month */
  onMonthChange: (year: number, month: number) => void
  /** Whether heatmap data is loading */
  loading?: boolean
}
```

Implementation notes:
- Use `Button` from shadcn for nav arrows (variant="ghost", size="icon")
- Use `ChevronLeft`, `ChevronRight` from lucide-react
- Compute `maxCount` from `dateCounts` values for relative scaling
- 3 dot levels: none (0), small (`opacity-40`), large (`opacity-100`)
- Selected date gets `bg-primary text-primary-foreground` ring
- Future dates are disabled (no click, muted text)
- Use `Skeleton` components when `loading` is true
- Calendar grid: CSS grid with 7 columns

**Step 2: Verify build**

Run: `cd frontend && npm run build`
Expected: Build succeeds.

**Step 3: Commit**

```bash
git add frontend/src/components/calendar-heatmap.tsx
git commit -m "feat: add CalendarHeatmap component with activity dots"
```

---

### Task 6: Frontend — Topic group component

**Files:**
- Create: `frontend/src/components/topic-group.tsx`

**Step 1: Build the topic group component**

Collapsible section showing a topic name, item count badge, and NewsCard list.

Props:
```tsx
interface TopicGroupProps {
  topic: string
  items: NewsItem[]
  defaultExpanded?: boolean
}
```

Implementation notes:
- Header row: topic label (from `TOPIC_LABELS`), count badge, chevron icon
- Click header to toggle expanded/collapsed
- Use `motion.div` from framer-motion for smooth height animation (or just CSS transition)
- Items rendered as vertical `NewsCard` list
- Use `ChevronDown` icon that rotates when collapsed

```tsx
import { useState } from 'react'
import { ChevronDown } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { NewsCard } from '@/components/news-card'
import { TOPIC_LABELS } from '@/lib/constants'
import type { NewsItem } from '@/lib/types'

interface TopicGroupProps {
  topic: string
  items: NewsItem[]
  defaultExpanded?: boolean
}

export function TopicGroup({ topic, items, defaultExpanded = false }: TopicGroupProps) {
  const [expanded, setExpanded] = useState(defaultExpanded)
  const label = TOPIC_LABELS[topic] ?? topic

  return (
    <div className="border-b border-border">
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex w-full items-center gap-2 py-3 text-left hover:bg-accent/50 transition-colors"
      >
        <ChevronDown
          className={`h-4 w-4 text-muted-foreground transition-transform ${
            expanded ? '' : '-rotate-90'
          }`}
        />
        <span className="font-medium">{label}</span>
        <Badge variant="secondary" className="ml-auto">
          {items.length}
        </Badge>
      </button>
      {expanded && (
        <div className="pb-2">
          {items.map((item) => (
            <NewsCard key={item.id} item={item} />
          ))}
        </div>
      )}
    </div>
  )
}
```

**Step 2: Verify build**

Run: `cd frontend && npm run build`
Expected: Build succeeds.

**Step 3: Commit**

```bash
git add frontend/src/components/topic-group.tsx
git commit -m "feat: add TopicGroup collapsible component"
```

---

### Task 7: Frontend — Timeline page (wire everything together)

**Files:**
- Modify: `frontend/src/pages/Timeline.tsx` (replace placeholder)

**Step 1: Implement the full Timeline page**

Replace the placeholder with the full implementation:

```tsx
import { useState, useCallback, useEffect } from 'react'
import { Calendar } from 'lucide-react'
import { Skeleton } from '@/components/ui/skeleton'
import { CalendarHeatmap } from '@/components/calendar-heatmap'
import { TopicGroup } from '@/components/topic-group'
import { NewsCard } from '@/components/news-card'
import { apiGet } from '@/lib/api'
import type { NewsItem, StatsDateItem, StatsGroupDateItem } from '@/lib/types'

function toISODate(d: Date): string {
  return d.toISOString().split('T')[0]
}

function monthRange(year: number, month: number) {
  const from = `${year}-${String(month).padStart(2, '0')}-01`
  const lastDay = new Date(year, month, 0).getDate()
  const to = `${year}-${String(month).padStart(2, '0')}-${String(lastDay).padStart(2, '0')}`
  return { from, to }
}

export default function Timeline() {
  const today = new Date()
  const [year, setYear] = useState(today.getFullYear())
  const [month, setMonth] = useState(today.getMonth() + 1)
  const [selectedDate, setSelectedDate] = useState(toISODate(today))
  const [dateCounts, setDateCounts] = useState<Record<string, number>>({})
  const [topicDateCounts, setTopicDateCounts] = useState<StatsGroupDateItem[]>([])
  const [items, setItems] = useState<NewsItem[]>([])
  const [loadingCalendar, setLoadingCalendar] = useState(true)
  const [loadingItems, setLoadingItems] = useState(true)

  // Fetch heatmap data for the displayed month
  const fetchMonthStats = useCallback(async (y: number, m: number) => {
    setLoadingCalendar(true)
    const { from, to } = monthRange(y, m)
    const [dateRes, topicRes] = await Promise.all([
      apiGet<StatsDateItem[]>('/api/stats/by-date', { date_from: from, date_to: to }),
      apiGet<StatsGroupDateItem[]>('/api/stats/by-topic-date', { date_from: from, date_to: to }),
    ])
    const counts: Record<string, number> = {}
    for (const item of dateRes.data) {
      counts[item.date] = item.count
    }
    setDateCounts(counts)
    setTopicDateCounts(topicRes.data)
    setLoadingCalendar(false)
  }, [])

  // Fetch items for the selected date
  const fetchItems = useCallback(async (dateStr: string) => {
    setLoadingItems(true)
    const { data } = await apiGet<NewsItem[]>(`/api/items/by-date/${dateStr}`)
    setItems(data)
    setLoadingItems(false)
  }, [])

  // On mount + month change: fetch stats
  useEffect(() => {
    fetchMonthStats(year, month)
  }, [year, month, fetchMonthStats])

  // On date select: fetch items
  useEffect(() => {
    fetchItems(selectedDate)
  }, [selectedDate, fetchItems])

  const handleMonthChange = (newYear: number, newMonth: number) => {
    setYear(newYear)
    setMonth(newMonth)
  }

  const handleDateSelect = (dateStr: string) => {
    setSelectedDate(dateStr)
  }

  // Group items by topic, sorted by count descending
  const groupedByTopic = items.reduce<Record<string, NewsItem[]>>((acc, item) => {
    const topic = item.topic ?? 'uncategorized'
    if (!acc[topic]) acc[topic] = []
    acc[topic].push(item)
    return acc
  }, {})
  const sortedTopics = Object.entries(groupedByTopic).sort((a, b) => b[1].length - a[1].length)

  // Format selected date for display
  const displayDate = new Date(selectedDate + 'T00:00:00').toLocaleDateString('en-US', {
    weekday: 'long',
    year: 'numeric',
    month: 'long',
    day: 'numeric',
  })

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-2">
        <Calendar className="h-5 w-5 text-muted-foreground" />
        <h1 className="text-2xl font-bold tracking-tight">Timeline</h1>
      </div>

      <CalendarHeatmap
        dateCounts={dateCounts}
        selectedDate={selectedDate}
        year={year}
        month={month}
        onDateSelect={handleDateSelect}
        onMonthChange={handleMonthChange}
        loading={loadingCalendar}
      />

      <div className="flex items-baseline justify-between">
        <h2 className="text-lg font-semibold">{displayDate}</h2>
        {!loadingItems && (
          <span className="text-sm text-muted-foreground">
            {items.length} {items.length === 1 ? 'item' : 'items'}
          </span>
        )}
      </div>

      {loadingItems ? (
        <div className="space-y-6">
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="space-y-2 border-b border-border pb-4">
              <Skeleton className="h-5 w-32" />
              <Skeleton className="h-5 w-3/4" />
              <Skeleton className="h-4 w-full" />
            </div>
          ))}
        </div>
      ) : items.length === 0 ? (
        <p className="py-12 text-center text-muted-foreground">No items for this date.</p>
      ) : (
        <div>
          {sortedTopics.map(([topic, topicItems], i) => (
            <TopicGroup
              key={topic}
              topic={topic}
              items={topicItems}
              defaultExpanded={i < 2}
            />
          ))}
        </div>
      )}
    </div>
  )
}
```

**Step 2: Verify build**

Run: `cd frontend && npm run build`
Expected: Build succeeds with no errors.

**Step 3: Commit**

```bash
git add frontend/src/pages/Timeline.tsx
git commit -m "feat: implement Timeline page with calendar heatmap and topic groups"
```

---

### Task 8: Backend — Run full quality gate

**Files:** None (verification only)

**Step 1: Run ruff, pyright, and all tests**

Run: `ruff check . && ruff format --check . && pyright . && pytest tests/ -x --timeout=30`
Expected: All pass. Fix any issues found.

**Step 2: Run frontend build**

Run: `cd frontend && npm run build`
Expected: Clean build.

---

### Task 9: Final commit and cleanup

**Step 1: Verify git status is clean**

Run: `git status`
Expected: All changes committed, working tree clean.

**Step 2: Update AGENTS.md if the file map section needs the new page listed**

Check `AGENTS.md` for a file map section. If it lists frontend pages, add `Timeline.tsx`. If it doesn't list individual pages, skip this.

**Step 3: Mark design doc task as done**

In `docs/plans/ideas-backlog.md`, mark the Timeline section item with `[x]`.

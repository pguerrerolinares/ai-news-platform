# Card Uniformity & Layout Fixes — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Unify card design across Feed, Top, and Search pages with a Twitter-style flat layout, add sticky topic filter, and fix horizontal padding.

**Architecture:** Replace both `NewsCard` (Shadcn Card wrapper) and `FeedCard` (flat article) with a single Twitter-style `NewsCard` component. Make `TopicFilter` sticky below the navbar. All pages share the same card component.

**Tech Stack:** React 19, Tailwind CSS, Shadcn UI (Badge only), tabler-icons-react

**Design doc:** `docs/plans/2026-03-01-card-uniformity-design.md`

---

### Task 1: Rework `NewsCard` to Twitter-style flat layout

**Files:**
- Modify: `frontend/src/components/news-card.tsx` (complete rewrite)

**Step 1: Rewrite `news-card.tsx`**

Replace the entire file with:

```tsx
import { Badge } from '@/components/ui/badge'
import { SOURCE_COLORS, TOPIC_LABELS, safeUrl } from '@/lib/constants'
import type { NewsItem } from '@/lib/types'
import { IconTrendingUp } from '@tabler/icons-react'

function timeAgo(dateStr: string | null): string {
  if (!dateStr) return ''
  const diff = Date.now() - new Date(dateStr).getTime()
  const minutes = Math.floor(diff / 60000)
  if (minutes < 60) return `${minutes}m`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours}h`
  const days = Math.floor(hours / 24)
  return `${days}d`
}

function extractDomain(url: string | null): string {
  if (!url) return ''
  try {
    return new URL(url).hostname.replace('www.', '')
  } catch {
    return ''
  }
}

export function NewsCard({ item }: { item: NewsItem }) {
  const href = safeUrl(item.url)
  const domain = extractDomain(item.url)

  return (
    <article className="border-b border-border pb-4 transition-colors hover:bg-accent/50">
      <div className="flex items-center gap-1.5 text-xs text-muted-foreground mb-1.5">
        <Badge variant="outline" className={`text-xs ${SOURCE_COLORS[item.source] ?? ''}`}>
          {item.source}
        </Badge>
        {domain && (
          <>
            <span>·</span>
            <span>{domain}</span>
          </>
        )}
        {item.published_at && (
          <>
            <span>·</span>
            <span>{timeAgo(item.published_at)}</span>
          </>
        )}
      </div>

      <h3 className="text-base font-semibold leading-snug mb-1 line-clamp-2">
        {href ? (
          <a
            href={href}
            target="_blank"
            rel="noopener noreferrer"
            className="hover:underline"
          >
            {item.title}
          </a>
        ) : (
          item.title
        )}
      </h3>

      {item.summary && (
        <p className="text-sm text-muted-foreground line-clamp-2 mb-1.5">
          {item.summary}
        </p>
      )}

      <div className="flex items-center gap-2">
        {item.topic && (
          <Badge variant="secondary" className="text-xs">
            {TOPIC_LABELS[item.topic] ?? item.topic}
          </Badge>
        )}
        {item.score != null && (
          <span className="ml-auto flex items-center gap-0.5 text-xs font-semibold text-muted-foreground">
            <IconTrendingUp className="size-3" />
            {item.score.toLocaleString()}
          </span>
        )}
      </div>
    </article>
  )
}
```

**Step 2: Verify build**

Run: `cd frontend && npm run build`
Expected: Build succeeds (Search page already imports NewsCard)

**Step 3: Commit**

```bash
git add frontend/src/components/news-card.tsx
git commit -m "refactor: rework NewsCard to Twitter-style flat layout"
```

---

### Task 2: Update Dashboard (Feed) to use `NewsCard`

**Files:**
- Modify: `frontend/src/pages/Dashboard.tsx` (lines 4, 124)

**Step 1: Replace FeedCard import with NewsCard**

Change line 4:
```tsx
// FROM:
import { FeedCard } from '@/components/feed-card'
// TO:
import { NewsCard } from '@/components/news-card'
```

**Step 2: Replace FeedCard usage with NewsCard**

Change line 124:
```tsx
// FROM:
<FeedCard key={item.id} item={item} />
// TO:
<NewsCard key={item.id} item={item} />
```

**Step 3: Add horizontal padding to container**

Change line 79:
```tsx
// FROM:
<div className="mx-auto max-w-2xl space-y-6">
// TO:
<div className="mx-auto max-w-2xl space-y-6 px-4">
```

**Step 4: Verify build**

Run: `cd frontend && npm run build`
Expected: Build succeeds

**Step 5: Commit**

```bash
git add frontend/src/pages/Dashboard.tsx
git commit -m "refactor: use NewsCard in Feed page, add horizontal padding"
```

---

### Task 3: Update Trending (Top) to use `NewsCard` and remove rank numbers

**Files:**
- Modify: `frontend/src/pages/Trending.tsx` (lines 1-4, 48, 98-110)

**Step 1: Clean up imports**

```tsx
// FROM:
import { FeedCard } from '@/components/feed-card'
// TO:
import { NewsCard } from '@/components/news-card'
```

Remove the unused `Tabs`, `TabsList`, `TabsTrigger` imports from line 2 if the time-period tabs are NOT part of our changes (keep them — they're separate from TopicFilter).

**Step 2: Add horizontal padding to container**

Change line 48:
```tsx
// FROM:
<div className="mx-auto max-w-2xl space-y-6">
// TO:
<div className="mx-auto max-w-2xl space-y-6 px-4">
```

**Step 3: Remove rank numbers and use NewsCard directly**

Replace lines 98-110:
```tsx
// FROM:
{items.map((item, index) => (
  <div key={item.id} className="flex gap-3">
    <span className="flex size-7 shrink-0 items-center justify-center rounded-full bg-primary text-xs font-bold text-primary-foreground mt-1">
      {index + 1}
    </span>
    <div className="flex-1">
      <FeedCard item={item} />
    </div>
  </div>
))}

// TO:
{items.map(item => (
  <NewsCard key={item.id} item={item} />
))}
```

**Step 4: Verify build**

Run: `cd frontend && npm run build`
Expected: Build succeeds

**Step 5: Commit**

```bash
git add frontend/src/pages/Trending.tsx
git commit -m "refactor: use NewsCard in Top page, remove rank numbers, add padding"
```

---

### Task 4: Delete `FeedCard`

**Files:**
- Delete: `frontend/src/components/feed-card.tsx`

**Step 1: Verify no remaining imports of FeedCard**

Run: `grep -r "feed-card\|FeedCard" frontend/src/`
Expected: No matches (Dashboard and Trending already updated)

**Step 2: Delete the file**

```bash
rm frontend/src/components/feed-card.tsx
```

**Step 3: Verify build**

Run: `cd frontend && npm run build`
Expected: Build succeeds with no broken imports

**Step 4: Commit**

```bash
git add frontend/src/components/feed-card.tsx
git commit -m "refactor: delete FeedCard component, replaced by unified NewsCard"
```

---

### Task 5: Make TopicFilter sticky with horizontal-only scroll

**Files:**
- Modify: `frontend/src/components/topic-filter.tsx`

**Step 1: Add sticky positioning and backdrop**

Replace the outer wrapper:
```tsx
// FROM:
<ScrollArea className="w-full">

// TO:
<ScrollArea className="sticky top-14 z-40 w-full bg-background/80 py-2 backdrop-blur-sm">
```

**Step 2: Verify build**

Run: `cd frontend && npm run build`
Expected: Build succeeds

**Step 3: Verify visually**

Run: `cd frontend && npm run dev`
- Navigate to Feed and Top pages
- Scroll down — TopicFilter should stick below the navbar
- Swipe/scroll topic tabs horizontally — should work
- Vertical drag on tabs — should NOT move them

**Step 4: Commit**

```bash
git add frontend/src/components/topic-filter.tsx
git commit -m "feat: make TopicFilter sticky below navbar"
```

---

### Task 6: Final verification and cleanup

**Step 1: Full build check**

Run: `cd frontend && npm run build`
Expected: Clean build, no warnings about unused imports

**Step 2: Visual verification checklist**

Run: `cd frontend && npm run dev`

- [ ] Feed page: cards use Twitter-style layout with border-bottom
- [ ] Top page: cards identical to Feed, no rank numbers
- [ ] Search page: cards identical to Feed and Top
- [ ] TopicFilter sticks below navbar on scroll (Feed + Top)
- [ ] TopicFilter scrolls horizontally only
- [ ] Cards have proper padding from screen edges on mobile
- [ ] Hover on card shows subtle background highlight
- [ ] Card links open in new tab
- [ ] Source badge, domain, and time display correctly

**Step 3: Run E2E tests**

Run: `cd frontend && npx playwright test`
Expected: All existing E2E tests pass

**Step 4: Final commit if any cleanup needed**

```bash
git commit -m "refactor: card uniformity cleanup"
```

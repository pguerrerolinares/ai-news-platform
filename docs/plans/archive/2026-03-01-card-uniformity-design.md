# Card Uniformity & Layout Fixes — Design Document

**Date**: 2026-03-01
**Status**: Approved

## Problem

1. Two different card components (`NewsCard` and `FeedCard`) with inconsistent styling across Feed, Top, and Search pages
2. No horizontal padding on mobile — content touches screen edges
3. TopicFilter tab bar scrolls away with content instead of staying fixed

## Design Decisions

### Unified Twitter-style card (`NewsCard`)

Replace both `NewsCard` (Shadcn Card wrapper) and `FeedCard` (flat article) with a single Twitter-style flat layout:

```
[Source badge] · domain.com · 3h
Title of the article (link, line-clamp-2)
Summary text preview (line-clamp-2)
[AI] [LLM]                    ↑ 234
─────────────────────────────────────
```

- **Line 1**: Source badge (outline) + domain + relative time, inline with `·` separators
- **Line 2**: Title as clickable link, `font-semibold`, `line-clamp-2`
- **Line 3**: Summary in `text-muted-foreground`, `line-clamp-2`
- **Line 4**: Topic badges (left) + score with trending icon (right)
- **Separator**: `border-b border-border` on the article element
- **Hover**: CSS-only `hover:bg-accent/50` background highlight (no framer-motion)
- **No Card wrapper**: flat article element, no Shadcn Card component

### Delete `FeedCard`

Remove `feed-card.tsx` entirely. All pages use `NewsCard`.

### Trending page: remove rank numbers

The numbered circles (1, 2, 3...) are removed. Cards display identically to Feed.

### Sticky TopicFilter

- Position: `sticky top-14 z-40` (below the 56px navbar)
- Background: `bg-background/80 backdrop-blur-sm` for readability
- Scroll: horizontal only (already uses `ScrollBar orientation="horizontal"`)
- Padding: `py-2` for breathing room

### Page padding

- Add `px-4` to the `max-w-2xl` container on Feed and Top pages

## Files Changed

| File | Change |
|------|--------|
| `frontend/src/components/news-card.tsx` | Rework to Twitter-style flat layout |
| `frontend/src/components/feed-card.tsx` | **Delete** |
| `frontend/src/pages/Dashboard.tsx` | Import `NewsCard` instead of `FeedCard` |
| `frontend/src/pages/Trending.tsx` | Import `NewsCard`, remove rank number circles |
| `frontend/src/pages/Search.tsx` | Already uses `NewsCard` — adapts automatically |
| `frontend/src/components/topic-filter.tsx` | Add sticky positioning + backdrop |

## Alternatives Considered

- **Approach B (new ArticleCard)**: More churn for same result. Rejected — YAGNI.
- **Approach C (keep both, align styles)**: Violates DRY. Rejected.
- **Shadcn Card wrapper (hybrid)**: User preferred full Twitter-style without Card borders.

# Infinite Scroll — Design Document

**Date**: 2026-02-27
**Scope**: Dashboard page only
**Approach**: TanStack Query (`useInfiniteQuery`)

## Problem

The custom `useInfiniteScroll` hook has multiple issues:
- `JSON.stringify(params)` as useMemo dep with eslint-disable (fragile hack)
- No AbortController — in-flight requests not cancelled on unmount or param change
- IntersectionObserver recreated on every `hasMore`/`fetchPage` change
- No observer cleanup on unmount
- Race condition: stale responses can overwrite fresh data when params change mid-flight
- Flat 5s backoff on error — doesn't scale, no user control

These caused a re-render loop flooding the API with requests (429 errors) on page load.

## Decision

Replace custom hook with `@tanstack/react-query` `useInfiniteQuery`. Industry-standard library that handles caching, deduplication, cancellation, and pagination out of the box.

## Design

### Infrastructure

- **Dependency**: `@tanstack/react-query`
- **QueryClientProvider** in `main.tsx` with:
  - `staleTime: 60_000` (1 min)
  - `retry: false` (user has manual retry button)
  - `refetchOnWindowFocus: false`
- **`apiGet` change**: Add optional `signal?: AbortSignal` parameter (backward compatible)

### Dashboard changes

- **Query key**: `['items-today', { topic }]`
  - Topic change → automatic cancellation + refetch from page 0
- **Pagination**: `getNextPageParam` uses `X-Total-Count` header to determine if more pages exist
- **Sentinel**: `IntersectionObserver` via `useCallback` ref, calls `fetchNextPage()`
- **Error handling**: Inline error with "Reintentar" button → calls `refetch()` or `fetchNextPage()`
- **Page size**: 10 items per page

### Files changed

| Action | File |
|--------|------|
| Install | `@tanstack/react-query` in `package.json` |
| Create QueryClientProvider | `main.tsx` |
| Add `signal?` param | `lib/api.ts` |
| Rewrite with `useInfiniteQuery` | `Dashboard.tsx` |
| Delete | `hooks/use-infinite-scroll.ts` |

### What we eliminate

- All manual state management (loading, loadingMore, error, hasMore)
- offsetRef, loadingRef, pausedUntilRef, observerRef
- The entire `use-infinite-scroll.ts` file
- JSON.stringify hack with eslint-disable

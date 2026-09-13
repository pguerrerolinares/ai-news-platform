# Infinite Scroll with TanStack Query — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace the buggy custom infinite scroll hook with TanStack Query's `useInfiniteQuery` on the Dashboard page.

**Architecture:** Install `@tanstack/react-query`, wrap app in `QueryClientProvider`, add `AbortSignal` support to `apiGet`, rewrite Dashboard to use `useInfiniteQuery` with `IntersectionObserver` sentinel, delete the old hook.

**Tech Stack:** React 19, TanStack Query v5, TypeScript, Vite/Bun

---

### Task 1: Install @tanstack/react-query

**Files:**
- Modify: `frontend/package.json`

**Step 1: Install the dependency**

Run from `frontend/`:
```bash
bun add @tanstack/react-query
```

**Step 2: Verify installation**

Run: `cd frontend && bun run build`
Expected: Build succeeds, `@tanstack/react-query` in `package.json` dependencies.

**Step 3: Commit**

```bash
git add frontend/package.json frontend/bun.lock
git commit -m "feat: add @tanstack/react-query dependency"
```

---

### Task 2: Add AbortSignal support to apiGet

**Files:**
- Modify: `frontend/src/lib/api.ts` (lines 42-96)

**Step 1: Add `signal` parameter to `request` function**

In `frontend/src/lib/api.ts`, modify the `request` function signature and the `fetch` call:

```typescript
async function request<T>(
  path: string,
  options: RequestInit = {},
  retry = true,
): Promise<{ data: T; totalCount: number | null; response: Response }> {
  const url = `${BASE_URL}${path}`
  const res = await fetch(url, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...authHeaders(),
      ...options.headers,
    },
  })
```

No changes needed to `request` — it already accepts `options: RequestInit` which includes `signal`.

**Step 2: Add `signal` parameter to `apiGet`**

Change `apiGet` from:
```typescript
export async function apiGet<T>(
  path: string,
  params?: Record<string, string>,
): Promise<{ data: T; totalCount: number | null }> {
  const query = params ? '?' + new URLSearchParams(params).toString() : ''
  const { data, totalCount } = await request<T>(`${path}${query}`)
  return { data, totalCount }
}
```

To:
```typescript
export async function apiGet<T>(
  path: string,
  params?: Record<string, string>,
  signal?: AbortSignal,
): Promise<{ data: T; totalCount: number | null }> {
  const query = params ? '?' + new URLSearchParams(params).toString() : ''
  const { data, totalCount } = await request<T>(`${path}${query}`, { signal })
  return { data, totalCount }
}
```

**Step 3: Verify build**

Run: `cd frontend && bun run build`
Expected: Build succeeds. Existing callers of `apiGet` are unaffected (signal is optional).

**Step 4: Commit**

```bash
git add frontend/src/lib/api.ts
git commit -m "feat: add AbortSignal support to apiGet"
```

---

### Task 3: Set up QueryClientProvider

**Files:**
- Modify: `frontend/src/main.tsx`

**Step 1: Wrap app in QueryClientProvider**

Replace `frontend/src/main.tsx` content with:

```typescript
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ThemeProvider } from '@/hooks/use-theme'
import './index.css'
import App from './App.tsx'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 60_000,
      retry: false,
      refetchOnWindowFocus: false,
    },
  },
})

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <ThemeProvider>
        <App />
      </ThemeProvider>
    </QueryClientProvider>
  </StrictMode>,
)
```

**Step 2: Verify build**

Run: `cd frontend && bun run build`
Expected: Build succeeds.

**Step 3: Commit**

```bash
git add frontend/src/main.tsx
git commit -m "feat: set up QueryClientProvider in app entry point"
```

---

### Task 4: Rewrite Dashboard with useInfiniteQuery

**Files:**
- Rewrite: `frontend/src/pages/Dashboard.tsx`

**Step 1: Rewrite Dashboard.tsx**

Replace the entire file with:

```tsx
import { useState, useMemo, useCallback, useRef, useEffect } from 'react'
import { useInfiniteQuery } from '@tanstack/react-query'
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '@/components/ui/select'
import { TOPIC_LABELS } from '@/lib/constants'
import { NewsCard } from '@/components/news-card'
import { FeaturedCard } from '@/components/featured-card'
import { AnimatedCardGrid, AnimatedCardItem } from '@/components/animated-card-grid'
import { Button } from '@/components/ui/button'
import { motion } from 'motion/react'
import { useReducedMotion } from '@/hooks/use-reduced-motion'
import { apiGet } from '@/lib/api'
import type { NewsItem } from '@/lib/types'
import { IconRefresh, IconLoader2 } from '@tabler/icons-react'

const TOPICS = Object.keys(TOPIC_LABELS)
const PAGE_SIZE = 10

export default function Dashboard() {
  const [activeTopic, setActiveTopic] = useState<string>('all')
  const reduced = useReducedMotion()
  const observerRef = useRef<IntersectionObserver | null>(null)

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
    queryKey: ['items-today', { topic: topicParam }],
    queryFn: async ({ pageParam, signal }) => {
      const params: Record<string, string> = {
        limit: String(PAGE_SIZE),
        offset: String(pageParam),
      }
      if (topicParam) params.topic = topicParam
      return apiGet<NewsItem[]>('/api/items/today', params, signal)
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

  const featured = useMemo(
    () => items.length > 0
      ? [...items].sort((a, b) => (b.score ?? 0) - (a.score ?? 0))[0]
      : null,
    [items],
  )

  const filtered = useMemo(() => {
    return featured ? items.filter(i => i.id !== featured.id) : items
  }, [items, featured])

  const sentinelRef = useCallback(
    (node: HTMLDivElement | null) => {
      if (observerRef.current) observerRef.current.disconnect()
      if (!node) return

      observerRef.current = new IntersectionObserver(
        (entries) => {
          if (entries[0].isIntersecting && hasNextPage && !isFetchingNextPage) {
            fetchNextPage()
          }
        },
        { rootMargin: '200px' },
      )
      observerRef.current.observe(node)
    },
    [hasNextPage, isFetchingNextPage, fetchNextPage],
  )

  // Cleanup observer on unmount
  useEffect(() => {
    return () => { observerRef.current?.disconnect() }
  }, [])

  const isInitialLoad = isFetching && !isFetchingNextPage && items.length === 0

  if (isInitialLoad) {
    return (
      <div className="flex items-center justify-center py-24">
        <IconLoader2 className="size-5 animate-spin text-muted-foreground" />
        <span className="ml-2 text-muted-foreground">Cargando noticias...</span>
      </div>
    )
  }

  if (error && items.length === 0) {
    return (
      <div className="flex flex-col items-center gap-4 py-24">
        <p className="text-destructive">
          {error instanceof Error ? error.message : 'Error al cargar noticias'}
        </p>
        <Button variant="outline" onClick={() => refetch()}>
          <IconRefresh className="mr-2 size-4" /> Reintentar
        </Button>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold tracking-tight">Latest</h2>
          <p className="text-sm text-muted-foreground">
            {items.length} noticias de {items.filter(i => i.trending).length} trending
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="ghost" size="icon" onClick={() => refetch()} title="Refrescar">
            <IconRefresh className="size-4" />
          </Button>
          <Select value={activeTopic} onValueChange={setActiveTopic}>
            <SelectTrigger className="w-[180px]">
              <SelectValue placeholder="Filtrar por topic" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">Todos los topics</SelectItem>
              {TOPICS.map(topic => (
                <SelectItem key={topic} value={topic}>
                  {TOPIC_LABELS[topic] ?? topic}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>

      {activeTopic === 'all' && featured && (
        <motion.div
          initial={reduced ? false : { opacity: 0, y: 30 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, ease: 'easeOut' }}
        >
          <FeaturedCard item={featured} />
        </motion.div>
      )}

      <AnimatedCardGrid
        className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3"
        animationKey={activeTopic}
      >
        {filtered.map(item => (
          <AnimatedCardItem key={item.id}>
            <NewsCard item={item} />
          </AnimatedCardItem>
        ))}
      </AnimatedCardGrid>

      {filtered.length === 0 && !isFetchingNextPage && (
        <div className="flex flex-col items-center gap-2 py-12 text-muted-foreground">
          <p>No hay noticias para este topic</p>
        </div>
      )}

      {error && items.length > 0 && (
        <div className="flex flex-col items-center gap-2 py-4">
          <p className="text-sm text-destructive">
            {error instanceof Error ? error.message : 'Error al cargar mas noticias'}
          </p>
          <Button variant="outline" size="sm" onClick={() => fetchNextPage()}>
            <IconRefresh className="mr-2 size-4" /> Reintentar
          </Button>
        </div>
      )}

      {isFetchingNextPage && (
        <div className="flex items-center justify-center py-8">
          <IconLoader2 className="size-5 animate-spin text-muted-foreground" />
          <span className="ml-2 text-sm text-muted-foreground">Cargando mas...</span>
        </div>
      )}

      {hasNextPage && <div ref={sentinelRef} className="h-1" />}
    </div>
  )
}
```

**Step 2: Verify build**

Run: `cd frontend && bun run build`
Expected: Build succeeds with no type errors.

**Step 3: Commit**

```bash
git add frontend/src/pages/Dashboard.tsx
git commit -m "feat: rewrite Dashboard with useInfiniteQuery

Replace custom useInfiniteScroll hook with TanStack Query.
Fixes re-render loop that caused 429 request floods.
Topic filter now queries the server directly instead of filtering locally."
```

---

### Task 5: Delete old hook

**Files:**
- Delete: `frontend/src/hooks/use-infinite-scroll.ts`

**Step 1: Verify no other imports**

Run: `grep -r "use-infinite-scroll" frontend/src/`
Expected: No results (Dashboard no longer imports it after Task 4).

**Step 2: Delete the file**

```bash
rm frontend/src/hooks/use-infinite-scroll.ts
```

**Step 3: Verify build**

Run: `cd frontend && bun run build`
Expected: Build succeeds.

**Step 4: Commit**

```bash
git add frontend/src/hooks/use-infinite-scroll.ts
git commit -m "refactor: delete unused custom infinite scroll hook"
```

---

### Task 6: Final verification

**Step 1: Full build check**

Run: `cd frontend && bun run build`
Expected: Build succeeds with zero errors.

**Step 2: Lint check**

Run: `cd frontend && bun run lint`
Expected: No lint errors.

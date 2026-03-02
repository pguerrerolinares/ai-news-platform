import { useState, useMemo, useCallback, useRef, useEffect } from 'react'
import { useInfiniteQuery } from '@tanstack/react-query'
import { TopicFilter } from '@/components/topic-filter'
import { NewsCard } from '@/components/news-card'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { apiGet } from '@/lib/api'
import type { NewsItem } from '@/lib/types'
import { IconRefresh, IconLoader2 } from '@tabler/icons-react'

const PAGE_SIZE = 20

export default function Top() {
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
    <div className="mx-auto max-w-2xl space-y-6 px-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold tracking-tight">Top</h2>
          <p className="text-sm text-muted-foreground">
            Most relevant AI news
          </p>
        </div>
        <Button variant="ghost" size="icon" onClick={() => refetch()} title="Refresh">
          <IconRefresh className="size-4" />
        </Button>
      </div>

      <TopicFilter value={activeTopic} onChange={setActiveTopic} />

      {isInitialLoad && (
        <div className="space-y-6">
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="space-y-2 border-b border-border pb-4">
              <div className="flex gap-2">
                <Skeleton className="h-5 w-20 rounded-full" />
                <Skeleton className="h-5 w-16 rounded-full" />
              </div>
              <Skeleton className="h-5 w-3/4" />
              <Skeleton className="h-4 w-full" />
              <Skeleton className="h-3 w-1/4" />
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

      {!isInitialLoad && items.length > 0 && (
        <div className="space-y-4">
          {items.map(item => (
            <NewsCard key={item.id} item={item} />
          ))}
        </div>
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

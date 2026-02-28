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
    queryKey: ['items-latest', { topic: topicParam }],
    queryFn: async ({ pageParam, signal }) => {
      const params: Record<string, string> = {
        limit: String(PAGE_SIZE),
        offset: String(pageParam),
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

  const featured = useMemo(
    () => activeTopic === 'all' && items.length > 0
      ? [...items].sort((a, b) => (b.score ?? 0) - (a.score ?? 0))[0]
      : null,
    [items, activeTopic],
  )

  const filtered = useMemo(() => {
    return featured ? items.filter(i => i.id !== featured.id) : items
  }, [items, featured])

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

  // Cleanup observer on unmount
  useEffect(() => {
    return () => { observerRef.current?.disconnect() }
  }, [])

  const isInitialLoad = isFetching && !isFetchingNextPage && items.length === 0

  if (isInitialLoad) {
    return (
      <div className="flex items-center justify-center py-24">
        <IconLoader2 className="size-5 animate-spin text-muted-foreground" />
        <span className="ml-2 text-muted-foreground">Loading news...</span>
      </div>
    )
  }

  if (error && items.length === 0) {
    return (
      <div className="flex flex-col items-center gap-4 py-24">
        <p className="text-destructive">
          {error instanceof Error ? error.message : 'Error loading news'}
        </p>
        <Button variant="outline" onClick={() => refetch()}>
          <IconRefresh className="mr-2 size-4" /> Retry
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
            {items.length} news from {items.filter(i => i.trending).length} trending
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="ghost" size="icon" onClick={() => refetch()} title="Refresh">
            <IconRefresh className="size-4" />
          </Button>
          <Select value={activeTopic} onValueChange={setActiveTopic}>
            <SelectTrigger className="w-[180px]">
              <SelectValue placeholder="Filter by topic" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All topics</SelectItem>
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

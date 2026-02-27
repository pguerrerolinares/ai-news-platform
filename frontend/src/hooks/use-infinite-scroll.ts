import { useCallback, useEffect, useRef, useState } from 'react'
import { apiGet } from '@/lib/api'
import type { NewsItem } from '@/lib/types'

const PAGE_SIZE = 10

interface UseInfiniteScrollOptions {
  endpoint: string
  params?: Record<string, string>
  pageSize?: number
}

interface UseInfiniteScrollResult {
  items: NewsItem[]
  loading: boolean
  loadingMore: boolean
  error: string
  hasMore: boolean
  sentinelRef: (node: HTMLDivElement | null) => void
  refresh: () => void
}

export function useInfiniteScroll({
  endpoint,
  params = {},
  pageSize = PAGE_SIZE,
}: UseInfiniteScrollOptions): UseInfiniteScrollResult {
  const [items, setItems] = useState<NewsItem[]>([])
  const [loading, setLoading] = useState(true)
  const [loadingMore, setLoadingMore] = useState(false)
  const [error, setError] = useState('')
  const [hasMore, setHasMore] = useState(true)
  const offsetRef = useRef(0)
  const observerRef = useRef<IntersectionObserver | null>(null)
  const loadingRef = useRef(false)

  const fetchPage = useCallback(async (offset: number, append: boolean) => {
    if (loadingRef.current) return
    loadingRef.current = true

    if (append) {
      setLoadingMore(true)
    } else {
      setLoading(true)
    }
    setError('')

    try {
      const allParams = { ...params, limit: String(pageSize), offset: String(offset) }
      const { data, totalCount } = await apiGet<NewsItem[]>(endpoint, allParams)

      setItems(prev => append ? [...prev, ...data] : data)
      offsetRef.current = offset + data.length

      const total = totalCount ?? Infinity
      setHasMore(offset + data.length < total && data.length === pageSize)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error al cargar noticias')
    } finally {
      setLoading(false)
      setLoadingMore(false)
      loadingRef.current = false
    }
  }, [endpoint, params, pageSize])

  const refresh = useCallback(() => {
    offsetRef.current = 0
    setItems([])
    setHasMore(true)
    fetchPage(0, false)
  }, [fetchPage])

  useEffect(() => { refresh() }, [refresh])

  const sentinelRef = useCallback((node: HTMLDivElement | null) => {
    if (observerRef.current) observerRef.current.disconnect()
    if (!node) return

    observerRef.current = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting && hasMore && !loadingRef.current) {
          fetchPage(offsetRef.current, true)
        }
      },
      { rootMargin: '200px' },
    )
    observerRef.current.observe(node)
  }, [hasMore, fetchPage])

  return { items, loading, loadingMore, error, hasMore, sentinelRef, refresh }
}

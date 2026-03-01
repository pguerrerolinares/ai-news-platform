import { useState, useCallback, useEffect } from 'react'
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { TopicFilter } from '@/components/topic-filter'
import { NewsCard } from '@/components/news-card'
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
    <div className="mx-auto max-w-2xl space-y-6 px-4">
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
        <TabsList className="h-auto bg-transparent p-0">
          {TIME_PERIODS.map(({ value, label }) => (
            <TabsTrigger
              key={value}
              value={value}
              className="data-[state=active]:bg-primary data-[state=active]:text-primary-foreground rounded-full px-3 py-1 text-sm"
            >
              {label}
            </TabsTrigger>
          ))}
        </TabsList>
      </Tabs>

      <TopicFilter value={topic} onChange={setTopic} />

      {loading && (
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

      {error && (
        <div className="flex flex-col items-center gap-4 py-24">
          <p className="text-destructive">{error}</p>
          <Button variant="outline" onClick={fetchData}>
            <IconRefresh className="mr-2 size-4" /> Retry
          </Button>
        </div>
      )}

      {!loading && !error && items.length > 0 && (
        <div className="space-y-4">
          {items.map(item => (
            <NewsCard key={item.id} item={item} />
          ))}
        </div>
      )}

      {!loading && !error && items.length === 0 && (
        <div className="flex flex-col items-center gap-2 py-12 text-muted-foreground">
          <p>No items for this period</p>
        </div>
      )}
    </div>
  )
}

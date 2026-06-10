import { useState, useCallback } from 'react'
import { Input } from '@/components/ui/input'
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '@/components/ui/select'
import { TOPIC_LABELS } from '@/lib/constants'
import { NewsCard } from '@/components/news-card'
import { AnimatedCardGrid, AnimatedCardItem } from '@/components/animated-card-grid'
import { Button } from '@/components/ui/button'
import { apiGet } from '@/lib/api'
import type { NewsItem } from '@/lib/types'
import { IconSearch, IconRefresh } from '@tabler/icons-react'

const TOPICS = Object.keys(TOPIC_LABELS)
const SORT_MAP: Record<string, string> = {
  relevance: 'relevance',
  date: 'date',
  score: 'score',
}

export default function Search() {
  const [query, setQuery] = useState('')
  const [topic, setTopic] = useState('all')
  const [sortBy, setSortBy] = useState('relevance')
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')
  const [results, setResults] = useState<NewsItem[]>([])
  const [totalCount, setTotalCount] = useState<number | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [searched, setSearched] = useState(false)

  const search = useCallback(async () => {
    if (!query.trim()) return
    setLoading(true)
    setError('')
    setSearched(true)
    try {
      const params: Record<string, string> = {
        q: query.trim(),
        sort_by: SORT_MAP[sortBy] ?? 'relevance',
        limit: '30',
      }
      if (topic !== 'all') params.topic = topic
      if (dateFrom) params.date_from = dateFrom
      if (dateTo) params.date_to = dateTo
      const { data, totalCount: count } = await apiGet<NewsItem[]>('/api/search', params)
      setResults(data)
      setTotalCount(count)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Search failed')
      setResults([])
      setTotalCount(null)
    } finally {
      setLoading(false)
    }
  }, [query, topic, sortBy, dateFrom, dateTo])

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === 'Enter') search()
  }

  return (
    <div className="mx-auto max-w-2xl space-y-6 px-4">
      <div>
        <h2 className="text-2xl font-bold tracking-tight">Search</h2>
        <p className="text-sm text-muted-foreground">Search through AI news</p>
      </div>

      {/* Row 1: query + search button */}
      <div className="flex flex-col gap-3 sm:flex-row">
        <div className="relative flex-1">
          <IconSearch className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="Search news..."
            value={query}
            onChange={e => setQuery(e.target.value)}
            onKeyDown={handleKeyDown}
            className="pl-9"
            aria-label="Search news"
          />
        </div>
        <Button onClick={search} disabled={loading || !query.trim()}>
          <IconSearch className="mr-2 size-4" />
          Search
        </Button>
      </div>

      {/* Row 2: filters */}
      <div className="flex flex-col gap-3 sm:flex-row sm:flex-wrap">
        <Select value={topic} onValueChange={setTopic}>
          <SelectTrigger className="w-full sm:w-[160px]">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All topics</SelectItem>
            {TOPICS.map(t => (
              <SelectItem key={t} value={t}>{TOPIC_LABELS[t] ?? t}</SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Select value={sortBy} onValueChange={setSortBy}>
          <SelectTrigger className="w-full sm:w-[160px]">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="relevance">Relevance</SelectItem>
            <SelectItem value="date">Date</SelectItem>
            <SelectItem value="score">Score</SelectItem>
          </SelectContent>
        </Select>
        <Input
          type="date"
          value={dateFrom}
          onChange={e => setDateFrom(e.target.value)}
          aria-label="From date"
          className="w-full sm:w-[160px] [color-scheme:dark]"
          title="From date"
        />
        <Input
          type="date"
          value={dateTo}
          onChange={e => setDateTo(e.target.value)}
          aria-label="To date"
          className="w-full sm:w-[160px] [color-scheme:dark]"
          title="To date"
        />
      </div>

      {error && (
        <div className="flex flex-col items-center gap-4 py-8">
          <p className="text-destructive">{error}</p>
          <Button variant="outline" onClick={search}>
            <IconRefresh className="mr-2 size-4" /> Retry
          </Button>
        </div>
      )}

      {searched && !loading && !error && (
        <p className="text-sm text-muted-foreground">
          {totalCount ?? results.length} result{(totalCount ?? results.length) !== 1 ? 's' : ''} for &quot;{query}&quot;
        </p>
      )}

      {loading && (
        <div className="flex items-center justify-center py-12">
          <p className="text-muted-foreground">Searching...</p>
        </div>
      )}

      {!loading && results.length > 0 && (
        <AnimatedCardGrid className="grid gap-4 sm:grid-cols-2" animationKey={`${query}-${topic}-${sortBy}-${dateFrom}-${dateTo}`}>
          {results.map(item => (
            <AnimatedCardItem key={item.id}>
              <NewsCard item={item} />
            </AnimatedCardItem>
          ))}
        </AnimatedCardGrid>
      )}

      {searched && !loading && !error && results.length === 0 && (
        <div className="flex flex-col items-center gap-2 py-12 text-muted-foreground">
          <p>No results found for &quot;{query}&quot;</p>
        </div>
      )}

      {!searched && (
        <div className="flex flex-col items-center gap-2 py-12 text-muted-foreground">
          <IconSearch className="size-8" />
          <p>Type and press Enter or Search</p>
        </div>
      )}
    </div>
  )
}

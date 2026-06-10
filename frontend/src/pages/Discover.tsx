import { useState, useCallback } from 'react'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { NewsCard } from '@/components/news-card'
import { apiGet } from '@/lib/api'
import type { NewsItem } from '@/lib/types'
import { IconSearch, IconRefresh, IconNetwork } from '@tabler/icons-react'

// ── Related items sub-component ─────────────────────────────────────────────

interface RelatedPanelProps {
  parentId: string
}

function RelatedPanel({ parentId }: RelatedPanelProps) {
  const [items, setItems] = useState<NewsItem[] | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [fetched, setFetched] = useState(false)

  const load = useCallback(async () => {
    if (fetched) return
    setLoading(true)
    setError('')
    setFetched(true)
    try {
      const { data } = await apiGet<NewsItem[]>(`/api/items/${parentId}/similar`, { limit: '5' })
      setItems(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load related items')
      setItems([])
    } finally {
      setLoading(false)
    }
  }, [parentId, fetched])

  // Lazy-load on first mount (called when the panel is opened by the parent)
  // The parent controls visibility; this component fetches once on first render.
  useState(() => { load() })

  if (loading) {
    return (
      <div className="mt-3 space-y-3 rounded-md border border-border bg-accent/30 p-3">
        {Array.from({ length: 3 }).map((_, i) => (
          <div key={i} className="space-y-1.5">
            <Skeleton className="h-3 w-3/4" />
            <Skeleton className="h-3 w-1/2" />
          </div>
        ))}
      </div>
    )
  }

  if (error) {
    return (
      <div className="mt-3 rounded-md border border-border bg-accent/30 p-3">
        <p className="text-xs text-destructive">{error}</p>
      </div>
    )
  }

  if (!items || items.length === 0) {
    return (
      <div className="mt-3 rounded-md border border-border bg-accent/30 p-3">
        <p className="text-xs text-muted-foreground">No similar items found.</p>
      </div>
    )
  }

  return (
    <div className="mt-3 rounded-md border border-border bg-accent/30 p-3 space-y-3">
      <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
        Similar items
      </p>
      {items.map(related => (
        <NewsCard key={related.id} item={related} />
      ))}
    </div>
  )
}

// ── Result card with Related toggle ─────────────────────────────────────────

interface ResultCardProps {
  item: NewsItem
}

function ResultCard({ item }: ResultCardProps) {
  const [showRelated, setShowRelated] = useState(false)

  return (
    <div>
      <NewsCard item={item} />
      <div className="mt-2">
        <Button
          variant="ghost"
          size="sm"
          className="h-7 gap-1.5 text-xs text-muted-foreground hover:text-foreground"
          onClick={() => setShowRelated(prev => !prev)}
          aria-expanded={showRelated}
        >
          <IconNetwork className="size-3.5" />
          {showRelated ? 'Hide related' : 'Related'}
        </Button>
      </div>
      {showRelated && <RelatedPanel parentId={item.id} />}
    </div>
  )
}

// ── Main Discover page ───────────────────────────────────────────────────────

export default function Discover() {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<NewsItem[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [searched, setSearched] = useState(false)

  const search = useCallback(async () => {
    if (!query.trim()) return
    setLoading(true)
    setError('')
    setSearched(true)
    setResults([])
    try {
      const { data } = await apiGet<NewsItem[]>('/api/search/semantic', {
        q: query.trim(),
        limit: '20',
      })
      setResults(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Semantic search failed')
    } finally {
      setLoading(false)
    }
  }, [query])

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === 'Enter') search()
  }

  return (
    <div className="mx-auto max-w-2xl space-y-6 px-4">
      <div>
        <h2 className="text-2xl font-bold tracking-tight">Discover</h2>
        <p className="text-sm text-muted-foreground">
          Explore AI news by meaning — not keywords
        </p>
      </div>

      {/* Search row */}
      <div className="flex flex-col gap-3 sm:flex-row">
        <div className="relative flex-1">
          <IconSearch className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="Describe what you're looking for..."
            value={query}
            onChange={e => setQuery(e.target.value)}
            onKeyDown={handleKeyDown}
            className="pl-9"
            aria-label="Semantic search"
          />
        </div>
        <Button onClick={search} disabled={loading || !query.trim()}>
          <IconSearch className="mr-2 size-4" />
          Search
        </Button>
      </div>

      {/* Error */}
      {error && (
        <div className="flex flex-col items-center gap-4 py-8">
          <p className="text-destructive">{error}</p>
          <Button variant="outline" onClick={search}>
            <IconRefresh className="mr-2 size-4" /> Retry
          </Button>
        </div>
      )}

      {/* Result count */}
      {searched && !loading && !error && (
        <p className="text-sm text-muted-foreground">
          {results.length} result{results.length !== 1 ? 's' : ''} for &quot;{query}&quot;
        </p>
      )}

      {/* Loading skeletons */}
      {loading && (
        <div className="space-y-6">
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="space-y-2 border-b border-border pb-4">
              <Skeleton className="h-3 w-24" />
              <Skeleton className="h-5 w-full" />
              <Skeleton className="h-4 w-3/4" />
              <Skeleton className="h-4 w-1/3" />
            </div>
          ))}
        </div>
      )}

      {/* Results */}
      {!loading && results.length > 0 && (
        <div className="space-y-6">
          {results.map(item => (
            <ResultCard key={item.id} item={item} />
          ))}
        </div>
      )}

      {/* No results */}
      {searched && !loading && !error && results.length === 0 && (
        <div className="flex flex-col items-center gap-2 py-12 text-muted-foreground">
          <p>No results found for &quot;{query}&quot;</p>
        </div>
      )}

      {/* Empty state */}
      {!searched && (
        <div className="flex flex-col items-center gap-2 py-12 text-muted-foreground">
          <IconNetwork className="size-8" />
          <p>Describe what you&apos;re looking for</p>
          <p className="text-xs">Results are ranked by semantic similarity, not keywords</p>
        </div>
      )}
    </div>
  )
}

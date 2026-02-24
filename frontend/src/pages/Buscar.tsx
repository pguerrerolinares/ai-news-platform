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
  relevancia: 'relevance',
  fecha: 'date',
  score: 'score',
}

export default function Buscar() {
  const [query, setQuery] = useState('')
  const [topic, setTopic] = useState('all')
  const [sortBy, setSortBy] = useState('relevancia')
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
      const { data, totalCount: count } = await apiGet<NewsItem[]>('/api/search', params)
      setResults(data)
      setTotalCount(count)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error en la busqueda')
      setResults([])
      setTotalCount(null)
    } finally {
      setLoading(false)
    }
  }, [query, topic, sortBy])

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === 'Enter') search()
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold tracking-tight">Buscar</h2>
        <p className="text-sm text-muted-foreground">Busca entre las noticias de IA</p>
      </div>

      <div className="flex flex-col gap-3 sm:flex-row">
        <div className="relative flex-1">
          <IconSearch className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="Buscar noticias..."
            value={query}
            onChange={e => setQuery(e.target.value)}
            onKeyDown={handleKeyDown}
            className="pl-9"
            aria-label="Buscar noticias"
          />
        </div>
        <Select value={topic} onValueChange={setTopic}>
          <SelectTrigger className="w-full sm:w-[160px]">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">Todos</SelectItem>
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
            <SelectItem value="relevancia">Relevancia</SelectItem>
            <SelectItem value="fecha">Fecha</SelectItem>
            <SelectItem value="score">Score</SelectItem>
          </SelectContent>
        </Select>
        <Button onClick={search} disabled={loading || !query.trim()}>
          <IconSearch className="mr-2 size-4" />
          Buscar
        </Button>
      </div>

      {error && (
        <div className="flex flex-col items-center gap-4 py-8">
          <p className="text-destructive">{error}</p>
          <Button variant="outline" onClick={search}>
            <IconRefresh className="mr-2 size-4" /> Reintentar
          </Button>
        </div>
      )}

      {searched && !loading && !error && (
        <p className="text-sm text-muted-foreground">
          {totalCount ?? results.length} resultado{(totalCount ?? results.length) !== 1 ? 's' : ''} para &quot;{query}&quot;
        </p>
      )}

      {loading && (
        <div className="flex items-center justify-center py-12">
          <p className="text-muted-foreground">Buscando...</p>
        </div>
      )}

      {!loading && results.length > 0 && (
        <AnimatedCardGrid className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3" animationKey={`${query}-${topic}-${sortBy}`}>
          {results.map(item => (
            <AnimatedCardItem key={item.id}>
              <NewsCard item={item} />
            </AnimatedCardItem>
          ))}
        </AnimatedCardGrid>
      )}

      {searched && !loading && !error && results.length === 0 && (
        <div className="flex flex-col items-center gap-2 py-12 text-muted-foreground">
          <p>No se encontraron resultados para &quot;{query}&quot;</p>
        </div>
      )}

      {!searched && (
        <div className="flex flex-col items-center gap-2 py-12 text-muted-foreground">
          <IconSearch className="size-8" />
          <p>Escribe y pulsa Enter o Buscar</p>
        </div>
      )}
    </div>
  )
}

import { useState, useMemo } from 'react'
import { Input } from '@/components/ui/input'
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '@/components/ui/select'
import { MOCK_ITEMS, MOCK_TOPICS } from '@/lib/mock-data'
import { TOPIC_LABELS } from '@/lib/constants'
import { NewsCard } from '@/components/news-card'
import { AnimatedCardGrid, AnimatedCardItem } from '@/components/animated-card-grid'
import { IconSearch } from '@tabler/icons-react'

export default function Buscar() {
  const [query, setQuery] = useState('')
  const [topic, setTopic] = useState('all')
  const [sortBy, setSortBy] = useState('relevancia')

  const results = useMemo(() => {
    const q = query.toLowerCase()
    let items = q
      ? MOCK_ITEMS.filter(
          i => i.title.toLowerCase().includes(q) || (i.summary ?? '').toLowerCase().includes(q)
        )
      : []

    if (topic !== 'all') {
      items = items.filter(i => i.topic === topic)
    }

    if (sortBy === 'fecha') {
      return [...items].sort((a, b) => (b.published_at ?? '').localeCompare(a.published_at ?? ''))
    } else if (sortBy === 'score') {
      return [...items].sort((a, b) => (b.score ?? 0) - (a.score ?? 0))
    }
    return items
  }, [query, topic, sortBy])

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold tracking-tight">Buscar</h2>
        <p className="text-sm text-muted-foreground">Busca entre las noticias de IA</p>
      </div>

      {/* Search controls */}
      <div className="flex flex-col gap-3 sm:flex-row">
        <div className="relative flex-1">
          <IconSearch className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="Buscar noticias..."
            value={query}
            onChange={e => setQuery(e.target.value)}
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
            {MOCK_TOPICS.map(t => (
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
      </div>

      {/* Results */}
      {query && (
        <p className="text-sm text-muted-foreground">
          {results.length} resultado{results.length !== 1 ? 's' : ''} para &quot;{query}&quot;
        </p>
      )}

      {results.length > 0 && (
        <AnimatedCardGrid className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3" animationKey={`${query}-${topic}-${sortBy}`}>
          {results.map(item => (
            <AnimatedCardItem key={item.id}>
              <NewsCard item={item} />
            </AnimatedCardItem>
          ))}
        </AnimatedCardGrid>
      )}

      {query && results.length === 0 && (
        <div className="flex flex-col items-center gap-2 py-12 text-muted-foreground">
          <p>No se encontraron resultados para &quot;{query}&quot;</p>
        </div>
      )}

      {!query && (
        <div className="flex flex-col items-center gap-2 py-12 text-muted-foreground">
          <IconSearch className="size-8" />
          <p>Escribe para buscar noticias</p>
        </div>
      )}
    </div>
  )
}

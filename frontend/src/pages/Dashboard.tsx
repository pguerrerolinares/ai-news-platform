import { useState, useMemo } from 'react'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { MOCK_ITEMS, MOCK_TOPICS } from '@/lib/mock-data'
import { TOPIC_LABELS } from '@/lib/constants'
import { NewsCard } from '@/components/news-card'
import { FeaturedCard } from '@/components/featured-card'

export default function Dashboard() {
  const [activeTopic, setActiveTopic] = useState<string>('all')

  const featured = useMemo(
    () => [...MOCK_ITEMS].sort((a, b) => (b.score ?? 0) - (a.score ?? 0))[0],
    [],
  )

  const filtered = useMemo(() => {
    const rest = MOCK_ITEMS.filter(i => i.id !== featured.id)
    return activeTopic !== 'all' ? rest.filter(i => i.topic === activeTopic) : rest
  }, [activeTopic, featured.id])

  return (
    <div className="space-y-6">
      {/* Header row */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold tracking-tight">Latest</h2>
          <p className="text-sm text-muted-foreground">
            {MOCK_ITEMS.length} noticias de {MOCK_ITEMS.filter(i => i.trending).length} trending
          </p>
        </div>
        <Select value={activeTopic} onValueChange={setActiveTopic}>
          <SelectTrigger className="w-[180px]">
            <SelectValue placeholder="Filtrar por topic" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">Todos los topics</SelectItem>
            {MOCK_TOPICS.map(topic => (
              <SelectItem key={topic} value={topic}>
                {TOPIC_LABELS[topic] ?? topic}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {/* Featured */}
      {activeTopic === 'all' && <FeaturedCard item={featured} />}

      {/* News grid */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {filtered.map(item => (
          <NewsCard key={item.id} item={item} />
        ))}
      </div>

      {filtered.length === 0 && (
        <div className="flex flex-col items-center gap-2 py-12 text-muted-foreground">
          <p>No hay noticias para este topic</p>
        </div>
      )}
    </div>
  )
}

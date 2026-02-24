import { useState, useMemo, useEffect, useCallback } from 'react'
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '@/components/ui/select'
import { TOPIC_LABELS } from '@/lib/constants'
import { NewsCard } from '@/components/news-card'
import { FeaturedCard } from '@/components/featured-card'
import { AnimatedCardGrid, AnimatedCardItem } from '@/components/animated-card-grid'
import { Button } from '@/components/ui/button'
import { apiGet } from '@/lib/api'
import type { NewsItem } from '@/lib/types'
import { motion } from 'motion/react'
import { useReducedMotion } from '@/hooks/use-reduced-motion'
import { IconRefresh } from '@tabler/icons-react'

const TOPICS = Object.keys(TOPIC_LABELS)

export default function Dashboard() {
  const [items, setItems] = useState<NewsItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [activeTopic, setActiveTopic] = useState<string>('all')
  const reduced = useReducedMotion()

  const fetchItems = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const { data } = await apiGet<NewsItem[]>('/api/items/today', { limit: '50' })
      setItems(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error al cargar noticias')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { fetchItems() }, [fetchItems])

  const featured = useMemo(
    () => items.length > 0 ? [...items].sort((a, b) => (b.score ?? 0) - (a.score ?? 0))[0] : null,
    [items],
  )

  const filtered = useMemo(() => {
    const rest = featured ? items.filter(i => i.id !== featured.id) : items
    return activeTopic !== 'all' ? rest.filter(i => i.topic === activeTopic) : rest
  }, [items, activeTopic, featured])

  if (loading) {
    return (
      <div className="flex items-center justify-center py-24">
        <p className="text-muted-foreground">Cargando noticias...</p>
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex flex-col items-center gap-4 py-24">
        <p className="text-destructive">{error}</p>
        <Button variant="outline" onClick={fetchItems}>
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

      {activeTopic === 'all' && featured && (
        <motion.div
          initial={reduced ? false : { opacity: 0, y: 30 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, ease: 'easeOut' }}
        >
          <FeaturedCard item={featured} />
        </motion.div>
      )}

      <AnimatedCardGrid className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3" animationKey={activeTopic}>
        {filtered.map(item => (
          <AnimatedCardItem key={item.id}>
            <NewsCard item={item} />
          </AnimatedCardItem>
        ))}
      </AnimatedCardGrid>

      {filtered.length === 0 && (
        <div className="flex flex-col items-center gap-2 py-12 text-muted-foreground">
          <p>No hay noticias para este topic</p>
        </div>
      )}
    </div>
  )
}

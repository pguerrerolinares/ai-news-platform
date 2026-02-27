import { useState, useMemo } from 'react'
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
import { useInfiniteScroll } from '@/hooks/use-infinite-scroll'
import { IconRefresh, IconLoader2 } from '@tabler/icons-react'

const TOPICS = Object.keys(TOPIC_LABELS)

export default function Dashboard() {
  const [activeTopic, setActiveTopic] = useState<string>('all')
  const reduced = useReducedMotion()

  const {
    items, loading, loadingMore, error, hasMore, sentinelRef, refresh,
  } = useInfiniteScroll({ endpoint: '/api/items/today', pageSize: 20 })

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
        <Button variant="outline" onClick={refresh}>
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
        <div className="flex items-center gap-2">
          <Button variant="ghost" size="icon" onClick={refresh} title="Refrescar">
            <IconRefresh className="size-4" />
          </Button>
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

      {filtered.length === 0 && !loadingMore && (
        <div className="flex flex-col items-center gap-2 py-12 text-muted-foreground">
          <p>No hay noticias para este topic</p>
        </div>
      )}

      {loadingMore && (
        <div className="flex items-center justify-center py-8">
          <IconLoader2 className="size-5 animate-spin text-muted-foreground" />
          <span className="ml-2 text-sm text-muted-foreground">Cargando mas...</span>
        </div>
      )}

      {hasMore && <div ref={sentinelRef} className="h-1" />}
    </div>
  )
}

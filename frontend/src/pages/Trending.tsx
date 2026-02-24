import { useState, useEffect, useCallback } from 'react'
import { NewsCard } from '@/components/news-card'
import { AnimatedCardGrid, AnimatedCardItem } from '@/components/animated-card-grid'
import { Button } from '@/components/ui/button'
import { apiGet } from '@/lib/api'
import type { NewsItem } from '@/lib/types'
import { IconRefresh } from '@tabler/icons-react'

export default function Trending() {
  const [trendingItems, setTrendingItems] = useState<NewsItem[]>([])
  const [topScored, setTopScored] = useState<NewsItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const fetchData = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const [trending, top] = await Promise.all([
        apiGet<NewsItem[]>('/api/items/trending', { limit: '20' }),
        apiGet<NewsItem[]>('/api/items/top', { limit: '20' }),
      ])
      setTrendingItems(trending.data)
      setTopScored(top.data)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error al cargar datos')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { fetchData() }, [fetchData])

  if (loading) {
    return (
      <div className="flex items-center justify-center py-24">
        <p className="text-muted-foreground">Cargando trending...</p>
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex flex-col items-center gap-4 py-24">
        <p className="text-destructive">{error}</p>
        <Button variant="outline" onClick={fetchData}>
          <IconRefresh className="mr-2 size-4" /> Reintentar
        </Button>
      </div>
    )
  }

  return (
    <div className="space-y-8">
      <section className="space-y-4">
        <div>
          <h2 className="text-2xl font-bold tracking-tight">En movimiento</h2>
          <p className="text-sm text-muted-foreground">
            {trendingItems.length} noticias generando traccion ahora
          </p>
        </div>
        <AnimatedCardGrid className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3" animationKey="trending">
          {trendingItems.map(item => (
            <AnimatedCardItem key={item.id}>
              <NewsCard item={item} />
            </AnimatedCardItem>
          ))}
        </AnimatedCardGrid>
        {trendingItems.length === 0 && (
          <p className="py-8 text-center text-muted-foreground">No hay noticias trending</p>
        )}
      </section>

      <section className="space-y-4">
        <div>
          <h2 className="text-2xl font-bold tracking-tight">Top puntuados</h2>
          <p className="text-sm text-muted-foreground">Las noticias con mayor puntuacion</p>
        </div>
        <AnimatedCardGrid className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3" animationKey="top">
          {topScored.map(item => (
            <AnimatedCardItem key={item.id}>
              <NewsCard item={item} />
            </AnimatedCardItem>
          ))}
        </AnimatedCardGrid>
      </section>
    </div>
  )
}

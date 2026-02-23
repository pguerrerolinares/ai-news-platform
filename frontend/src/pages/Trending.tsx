import { useMemo } from 'react'
import { MOCK_ITEMS } from '@/lib/mock-data'
import { NewsCard } from '@/components/news-card'
import { AnimatedCardGrid, AnimatedCardItem } from '@/components/animated-card-grid'

export default function Trending() {
  const trendingItems = useMemo(
    () => [...MOCK_ITEMS.filter(i => i.trending)].sort((a, b) => (b.score ?? 0) - (a.score ?? 0)),
    [],
  )

  const topScored = useMemo(
    () => [...MOCK_ITEMS].sort((a, b) => (b.score ?? 0) - (a.score ?? 0)).slice(0, 10),
    [],
  )

  return (
    <div className="space-y-8">
      {/* Trending section */}
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
      </section>

      {/* Top scored section */}
      <section className="space-y-4">
        <div>
          <h2 className="text-2xl font-bold tracking-tight">Top puntuados</h2>
          <p className="text-sm text-muted-foreground">
            Las noticias con mayor puntuacion
          </p>
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

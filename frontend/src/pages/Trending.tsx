import { MOCK_ITEMS } from '@/lib/mock-data'
import { NewsCard } from '@/components/news-card'

export default function Trending() {
  const trendingItems = MOCK_ITEMS.filter(i => i.trending)
    .sort((a, b) => (b.score ?? 0) - (a.score ?? 0))
  const topScored = [...MOCK_ITEMS]
    .sort((a, b) => (b.score ?? 0) - (a.score ?? 0))
    .slice(0, 10)

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
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {trendingItems.map(item => (
            <NewsCard key={item.id} item={item} />
          ))}
        </div>
      </section>

      {/* Top scored section */}
      <section className="space-y-4">
        <div>
          <h2 className="text-2xl font-bold tracking-tight">Top puntuados</h2>
          <p className="text-sm text-muted-foreground">
            Las noticias con mayor puntuacion
          </p>
        </div>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {topScored.map(item => (
            <NewsCard key={item.id} item={item} />
          ))}
        </div>
      </section>
    </div>
  )
}

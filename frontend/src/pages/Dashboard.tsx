import { useState } from 'react'
import { Card, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { MOCK_BRIEFING, MOCK_ITEMS, MOCK_TOPICS } from '@/lib/mock-data'
import type { NewsItem } from '@/lib/types'
import {
  IconFlame,
  IconExternalLink,
  IconClock,
  IconFilter,
  IconTrendingUp,
} from '@tabler/icons-react'

const SOURCE_COLORS: Record<string, string> = {
  hackernews: 'bg-orange-500/10 text-orange-500 border-orange-500/20',
  github: 'bg-purple-500/10 text-purple-500 border-purple-500/20',
  arxiv: 'bg-red-500/10 text-red-500 border-red-500/20',
  reddit: 'bg-blue-500/10 text-blue-500 border-blue-500/20',
  rss: 'bg-yellow-500/10 text-yellow-500 border-yellow-500/20',
  huggingface: 'bg-amber-500/10 text-amber-500 border-amber-500/20',
}

const TOPIC_LABELS: Record<string, string> = {
  modelos: 'Modelos',
  herramientas: 'Herramientas',
  papers: 'Papers',
  productos: 'Productos',
  open_source: 'Open Source',
  agentes: 'Agentes',
  regulacion: 'Regulacion',
}

function formatTime(dateStr: string | null) {
  if (!dateStr) return ''
  const d = new Date(dateStr)
  return d.toLocaleTimeString('es-ES', { hour: '2-digit', minute: '2-digit' })
}

function NewsCard({ item }: { item: NewsItem }) {
  return (
    <Card className="group flex flex-col transition-colors hover:border-primary/30">
      <CardHeader className="flex-1 space-y-2">
        <div className="flex items-center gap-2">
          <Badge variant="outline" className={SOURCE_COLORS[item.source] ?? ''}>
            {item.source}
          </Badge>
          {item.topic && (
            <Badge variant="secondary" className="text-xs">
              {TOPIC_LABELS[item.topic] ?? item.topic}
            </Badge>
          )}
          {item.trending && (
            <IconFlame className="ml-auto size-4 text-orange-500" />
          )}
        </div>
        <CardTitle className="line-clamp-2 text-sm font-semibold leading-snug">
          {item.url ? (
            <a
              href={item.url}
              target="_blank"
              rel="noopener noreferrer"
              className="hover:underline"
            >
              {item.title}
            </a>
          ) : (
            item.title
          )}
        </CardTitle>
        <CardDescription className="line-clamp-2 text-xs">
          {item.summary}
        </CardDescription>
      </CardHeader>
      <CardFooter className="flex items-center gap-3 text-xs text-muted-foreground">
        {item.score != null && (
          <span className="flex items-center gap-1 font-medium text-foreground">
            <IconTrendingUp className="size-3" />
            {item.score.toLocaleString()}
          </span>
        )}
        {item.author && <span>{item.author}</span>}
        <span className="ml-auto flex items-center gap-1">
          <IconClock className="size-3" />
          {formatTime(item.published_at)}
        </span>
      </CardFooter>
    </Card>
  )
}

function FeaturedCard({ item }: { item: NewsItem }) {
  return (
    <Card className="border-primary/30 bg-gradient-to-br from-primary/5 to-transparent">
      <CardHeader className="space-y-3">
        <div className="flex items-center gap-2 flex-wrap">
          <Badge variant="outline" className={SOURCE_COLORS[item.source] ?? ''}>
            {item.source}
          </Badge>
          {item.topic && (
            <Badge variant="secondary">
              {TOPIC_LABELS[item.topic] ?? item.topic}
            </Badge>
          )}
          {item.trending && (
            <Badge className="bg-orange-500/10 text-orange-500 border-orange-500/20">
              <IconFlame className="mr-1 size-3" />
              Trending
            </Badge>
          )}
          {item.score != null && (
            <span className="ml-auto flex items-center gap-1 text-sm font-bold text-foreground">
              <IconTrendingUp className="size-4" />
              {item.score.toLocaleString()}
            </span>
          )}
        </div>
        <CardTitle className="text-xl font-bold leading-tight">
          {item.url ? (
            <a
              href={item.url}
              target="_blank"
              rel="noopener noreferrer"
              className="hover:underline inline-flex items-start gap-2"
            >
              {item.title}
              <IconExternalLink className="mt-1 size-4 shrink-0 opacity-50" />
            </a>
          ) : (
            item.title
          )}
        </CardTitle>
        <CardDescription className="text-sm leading-relaxed">
          {item.summary}
        </CardDescription>
      </CardHeader>
      <CardFooter className="text-xs text-muted-foreground gap-3">
        {item.author && <span>por {item.author}</span>}
        <span className="flex items-center gap-1">
          <IconClock className="size-3" />
          {formatTime(item.published_at)}
        </span>
      </CardFooter>
    </Card>
  )
}

export default function Dashboard() {
  const [activeTopic, setActiveTopic] = useState<string | null>(null)
  const briefing = MOCK_BRIEFING

  const topicCounts = MOCK_ITEMS.reduce<Record<string, number>>((acc, item) => {
    if (item.topic) acc[item.topic] = (acc[item.topic] ?? 0) + 1
    return acc
  }, {})

  const featured = [...MOCK_ITEMS].sort((a, b) => (b.score ?? 0) - (a.score ?? 0))[0]
  const rest = MOCK_ITEMS.filter(i => i.id !== featured.id)
  const filtered = activeTopic ? rest.filter(i => i.topic === activeTopic) : rest

  const stats = [
    { label: 'Extraidas', value: briefing.total_items },
    { label: 'Dedup', value: briefing.items_after_dedup },
    { label: 'Filtradas', value: briefing.items_filtered },
    { label: 'Trending', value: briefing.trending_count },
    { label: 'Duracion', value: briefing.duration_seconds ? `${briefing.duration_seconds}s` : '—' },
  ]

  return (
    <div className="space-y-6">
      {/* Date + Stats summary */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold tracking-tight">Hoy en IA</h2>
          <p className="text-sm text-muted-foreground">{briefing.date}</p>
        </div>
        <div className="hidden items-center gap-4 text-sm text-muted-foreground sm:flex">
          {stats.map(s => (
            <div key={s.label} className="text-center">
              <p className="text-lg font-bold tabular-nums text-foreground">{s.value ?? '—'}</p>
              <p className="text-xs">{s.label}</p>
            </div>
          ))}
        </div>
      </div>

      {/* Mobile stats */}
      <div className="grid grid-cols-5 gap-2 sm:hidden">
        {stats.map(s => (
          <Card key={s.label} className="px-2 py-2 text-center">
            <p className="text-xs text-muted-foreground">{s.label}</p>
            <p className="text-lg font-bold tabular-nums">{s.value ?? '—'}</p>
          </Card>
        ))}
      </div>

      {/* Topic filters */}
      <div className="flex flex-wrap items-center gap-2">
        <IconFilter className="size-4 text-muted-foreground" />
        <Button
          variant={activeTopic === null ? 'default' : 'outline'}
          size="sm"
          onClick={() => setActiveTopic(null)}
        >
          Todas ({MOCK_ITEMS.length})
        </Button>
        {MOCK_TOPICS.map(topic => (
          <Button
            key={topic}
            variant={activeTopic === topic ? 'default' : 'outline'}
            size="sm"
            onClick={() => setActiveTopic(activeTopic === topic ? null : topic)}
          >
            {TOPIC_LABELS[topic] ?? topic}
            <span className="ml-1 opacity-60">{topicCounts[topic] ?? 0}</span>
          </Button>
        ))}
      </div>

      {/* Featured */}
      {!activeTopic && <FeaturedCard item={featured} />}

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

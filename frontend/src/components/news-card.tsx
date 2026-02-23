import { Card, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { SOURCE_COLORS, TOPIC_LABELS, formatTime } from '@/lib/constants'
import type { NewsItem } from '@/lib/types'
import {
  IconFlame,
  IconClock,
  IconTrendingUp,
} from '@tabler/icons-react'

export function NewsCard({ item }: { item: NewsItem }) {
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

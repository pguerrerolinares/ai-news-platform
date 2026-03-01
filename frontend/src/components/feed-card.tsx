import { Badge } from '@/components/ui/badge'
import { SOURCE_COLORS, TOPIC_LABELS, safeUrl } from '@/lib/constants'
import type { NewsItem } from '@/lib/types'
import { IconTrendingUp } from '@tabler/icons-react'
import { motion } from 'motion/react'
import { useReducedMotion } from '@/hooks/use-reduced-motion'

function timeAgo(dateStr: string | null): string {
  if (!dateStr) return ''
  const diff = Date.now() - new Date(dateStr).getTime()
  const minutes = Math.floor(diff / 60000)
  if (minutes < 60) return `${minutes}m`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours}h`
  const days = Math.floor(hours / 24)
  return `${days}d`
}

function extractDomain(url: string | null): string {
  if (!url) return ''
  try {
    return new URL(url).hostname.replace('www.', '')
  } catch {
    return ''
  }
}

export function FeedCard({ item }: { item: NewsItem }) {
  const href = safeUrl(item.url)
  const reduced = useReducedMotion()
  const domain = extractDomain(item.url)

  return (
    <motion.article
      whileHover={reduced ? undefined : { y: -1 }}
      transition={{ duration: 0.15 }}
      className="group border-b border-border pb-4"
    >
      <div className="flex items-center gap-2 mb-1.5">
        <Badge variant="outline" className={`text-xs ${SOURCE_COLORS[item.source] ?? ''}`}>
          {item.source}
        </Badge>
        {item.topic && (
          <Badge variant="secondary" className="text-xs">
            {TOPIC_LABELS[item.topic] ?? item.topic}
          </Badge>
        )}
        {item.score != null && (
          <span className="ml-auto flex items-center gap-0.5 text-xs font-semibold text-muted-foreground">
            <IconTrendingUp className="size-3" />
            {item.score.toLocaleString()}
          </span>
        )}
      </div>

      <h3 className="text-base font-semibold leading-snug mb-1">
        {href ? (
          <a
            href={href}
            target="_blank"
            rel="noopener noreferrer"
            className="hover:underline"
          >
            {item.title}
          </a>
        ) : (
          item.title
        )}
      </h3>

      {item.summary && (
        <p className="text-sm text-muted-foreground line-clamp-2 mb-1.5">
          {item.summary}
        </p>
      )}

      <div className="flex items-center gap-1 text-xs text-muted-foreground">
        {domain && <span>{domain}</span>}
        {domain && item.published_at && <span>·</span>}
        {item.published_at && <span>{timeAgo(item.published_at)}</span>}
      </div>
    </motion.article>
  )
}

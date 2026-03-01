import { Badge } from '@/components/ui/badge'
import { SOURCE_COLORS, TOPIC_LABELS, safeUrl } from '@/lib/constants'
import type { NewsItem } from '@/lib/types'
import { IconTrendingUp } from '@tabler/icons-react'
import {
  SiYcombinator,
  SiGithub,
  SiArxiv,
  SiReddit,
  SiRss,
  SiHuggingface,
} from '@icons-pack/react-simple-icons'
import type { ComponentType, SVGProps } from 'react'

const SOURCE_ICONS: Record<string, ComponentType<SVGProps<SVGSVGElement>>> = {
  hackernews: SiYcombinator,
  github: SiGithub,
  arxiv: SiArxiv,
  reddit: SiReddit,
  rss: SiRss,
  huggingface: SiHuggingface,
}

function timeAgo(dateStr: string | null): string {
  if (!dateStr) return ''
  const diff = Date.now() - new Date(dateStr).getTime()
  const minutes = Math.floor(diff / 60000)
  if (minutes < 1) return 'now'
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

export function NewsCard({ item }: { item: NewsItem }) {
  const href = safeUrl(item.url)
  const domain = extractDomain(item.url)

  return (
    <article className="border-b border-border pb-4 transition-colors hover:bg-accent/50">
      <div className="flex items-center gap-1.5 text-xs text-muted-foreground mb-1.5">
        {SOURCE_ICONS[item.source] ? (
          (() => {
            const Icon = SOURCE_ICONS[item.source]
            return <Icon className="size-4" />
          })()
        ) : (
          <Badge variant="outline" className={`text-xs ${SOURCE_COLORS[item.source] ?? ''}`}>
            {item.source}
          </Badge>
        )}
        {domain && (
          <>
            <span>·</span>
            <span>{domain}</span>
          </>
        )}
        {item.published_at && (
          <>
            <span>·</span>
            <span>{timeAgo(item.published_at)}</span>
          </>
        )}
      </div>

      <h3 className="text-base font-semibold leading-snug mb-1 line-clamp-2">
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

      <div className="flex items-center gap-2">
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
    </article>
  )
}

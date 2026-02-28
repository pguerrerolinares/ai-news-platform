import { Card, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { SOURCE_COLORS, TOPIC_LABELS, formatTime, safeUrl } from '@/lib/constants'
import type { NewsItem } from '@/lib/types'
import {
  IconFlame,
  IconExternalLink,
  IconClock,
  IconTrendingUp,
} from '@tabler/icons-react'
import { motion } from 'motion/react'
import { useReducedMotion } from '@/hooks/use-reduced-motion'
import { useTranslation } from 'react-i18next'

export function FeaturedCard({ item }: { item: NewsItem }) {
  const href = safeUrl(item.url)
  const reduced = useReducedMotion()
  const { t } = useTranslation()

  return (
    <motion.div
      whileHover={reduced ? undefined : { y: -3 }}
      whileTap={reduced ? undefined : { scale: 0.99 }}
      transition={{ duration: 0.2 }}
    >
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
            {href ? (
              <a
                href={href}
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
          {item.author && <span>{t('featured.by')} {item.author}</span>}
          <span className="flex items-center gap-1">
            <IconClock className="size-3" />
            {formatTime(item.published_at)}
          </span>
        </CardFooter>
      </Card>
    </motion.div>
  )
}

import { useState } from 'react'
import { Badge } from '@/components/ui/badge'
import { NewsCard } from '@/components/news-card'
import { TOPIC_LABELS } from '@/lib/constants'
import { IconChevronDown } from '@tabler/icons-react'
import type { NewsItem } from '@/lib/types'

interface TopicGroupProps {
  topic: string
  items: NewsItem[]
  defaultExpanded?: boolean
}

export function TopicGroup({ topic, items, defaultExpanded }: TopicGroupProps) {
  const [open, setOpen] = useState(defaultExpanded ?? false)
  const label = TOPIC_LABELS[topic] ?? topic

  return (
    <div className="rounded-lg border border-border">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center gap-2 px-4 py-3 text-left transition-colors hover:bg-accent/50"
      >
        <span className="text-sm font-semibold">{label}</span>
        <Badge variant="secondary" className="text-xs">
          {items.length}
        </Badge>
        <IconChevronDown
          className={`ml-auto size-4 text-muted-foreground transition-transform ${
            open ? 'rotate-180' : ''
          }`}
        />
      </button>
      {open && (
        <div className="space-y-2 px-4 pb-3">
          {items.map((item) => (
            <NewsCard key={item.id} item={item} />
          ))}
        </div>
      )}
    </div>
  )
}

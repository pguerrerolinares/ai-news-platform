import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { TOPIC_LABELS } from '@/lib/constants'
import { ScrollArea, ScrollBar } from '@/components/ui/scroll-area'

const TOPICS = Object.keys(TOPIC_LABELS)

interface TopicFilterProps {
  value: string
  onChange: (value: string) => void
}

export function TopicFilter({ value, onChange }: TopicFilterProps) {
  return (
    <ScrollArea className="sticky top-14 z-40 w-full bg-background/80 py-2 backdrop-blur-sm">
      <Tabs value={value} onValueChange={onChange}>
        <TabsList className="h-auto bg-transparent p-0">
          <TabsTrigger
            value="all"
            className="data-[state=active]:bg-primary data-[state=active]:text-primary-foreground rounded-full px-3 py-1 text-sm"
          >
            All
          </TabsTrigger>
          {TOPICS.map((topic) => (
            <TabsTrigger
              key={topic}
              value={topic}
              className="data-[state=active]:bg-primary data-[state=active]:text-primary-foreground rounded-full px-3 py-1 text-sm"
            >
              {TOPIC_LABELS[topic] ?? topic}
            </TabsTrigger>
          ))}
        </TabsList>
      </Tabs>
      <ScrollBar orientation="horizontal" />
    </ScrollArea>
  )
}

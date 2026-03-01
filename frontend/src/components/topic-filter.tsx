import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { TOPIC_LABELS } from '@/lib/constants'

const TOPICS = Object.keys(TOPIC_LABELS)

interface TopicFilterProps {
  value: string
  onChange: (value: string) => void
}

export function TopicFilter({ value, onChange }: TopicFilterProps) {
  return (
    <div className="w-full overflow-x-auto overflow-y-hidden py-2">
      <Tabs value={value} onValueChange={onChange}>
        <TabsList className="inline-flex h-auto w-max bg-transparent p-0">
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
    </div>
  )
}

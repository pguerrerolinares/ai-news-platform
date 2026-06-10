import { PillTabs } from '@/components/pill-tabs'
import { TOPIC_LABELS } from '@/lib/constants'

const TOPIC_ITEMS = [
  { value: 'all', label: 'All' },
  ...Object.entries(TOPIC_LABELS).map(([value, label]) => ({ value, label })),
]

interface TopicFilterProps {
  value: string
  onChange: (value: string) => void
}

export function TopicFilter({ value, onChange }: TopicFilterProps) {
  return <PillTabs items={TOPIC_ITEMS} value={value} onValueChange={onChange} />
}

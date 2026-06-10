import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { cn } from '@/lib/utils'

export interface PillTabsItem {
  value: string
  label: string
}

export interface PillTabsProps {
  items: PillTabsItem[]
  value: string
  onValueChange: (value: string) => void
  className?: string
}

export function PillTabs({ items, value, onValueChange, className }: PillTabsProps) {
  return (
    <div className={cn('w-full overflow-x-auto overflow-y-hidden py-2 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden', className)}>
      <Tabs value={value} onValueChange={onValueChange}>
        <TabsList className="inline-flex h-auto w-max bg-transparent p-0 gap-1">
          {items.map((item) => (
            <TabsTrigger
              key={item.value}
              value={item.value}
              className="data-[state=active]:bg-primary data-[state=active]:text-primary-foreground data-[state=active]:shadow-none data-[state=active]:border-transparent rounded-full px-3 py-1 text-sm shrink-0 whitespace-nowrap"
            >
              {item.label}
            </TabsTrigger>
          ))}
        </TabsList>
      </Tabs>
    </div>
  )
}

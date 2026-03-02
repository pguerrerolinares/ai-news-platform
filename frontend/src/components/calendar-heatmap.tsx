import { useMemo, useState } from 'react'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { IconChevronLeft, IconChevronRight } from '@tabler/icons-react'
import type { StatsDateItem } from '@/lib/types'

const WEEKDAY_LABELS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']

interface CalendarHeatmapProps {
  data: StatsDateItem[]
  loading?: boolean
  onSelectDate?: (date: string) => void
  selectedDate?: string | null
  onMonthChange?: (date: Date) => void
}

/** Build a map from ISO date string to count. */
function buildCountMap(data: StatsDateItem[]): Map<string, number> {
  const map = new Map<string, number>()
  for (const item of data) {
    map.set(item.date, (map.get(item.date) ?? 0) + item.count)
  }
  return map
}

/** Get all days in a given month as Date objects. */
function getDaysInMonth(year: number, month: number): Date[] {
  const days: Date[] = []
  const d = new Date(year, month, 1)
  while (d.getMonth() === month) {
    days.push(new Date(d))
    d.setDate(d.getDate() + 1)
  }
  return days
}

/** Map a count to an intensity level 0-4 for styling. */
function getIntensity(count: number, maxCount: number): number {
  if (count === 0 || maxCount === 0) return 0
  const ratio = count / maxCount
  if (ratio <= 0.25) return 1
  if (ratio <= 0.5) return 2
  if (ratio <= 0.75) return 3
  return 4
}

const INTENSITY_CLASSES = [
  'bg-muted',
  'bg-primary/20',
  'bg-primary/40',
  'bg-primary/60',
  'bg-primary/90',
] as const

function toISODate(d: Date): string {
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}

export function CalendarHeatmap({
  data,
  loading = false,
  onSelectDate,
  selectedDate,
  onMonthChange,
}: CalendarHeatmapProps) {
  const [viewDate, setViewDate] = useState(() => new Date())

  const year = viewDate.getFullYear()
  const month = viewDate.getMonth()

  const monthLabel = viewDate.toLocaleString('en-US', {
    month: 'long',
    year: 'numeric',
  })

  const changeMonth = (newDate: Date) => {
    setViewDate(newDate)
    onMonthChange?.(newDate)
  }

  const prevMonth = () => changeMonth(new Date(year, month - 1, 1))
  const nextMonth = () => changeMonth(new Date(year, month + 1, 1))

  const days = useMemo(() => getDaysInMonth(year, month), [year, month])
  const countMap = useMemo(() => buildCountMap(data), [data])
  const maxCount = useMemo(
    () => Math.max(0, ...Array.from(countMap.values())),
    [countMap],
  )

  // Monday-based offset: 0=Mon ... 6=Sun
  const firstDayOffset = (days[0].getDay() + 6) % 7

  if (loading) {
    return (
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <Skeleton className="h-6 w-32" />
          <div className="flex gap-1">
            <Skeleton className="size-8 rounded" />
            <Skeleton className="size-8 rounded" />
          </div>
        </div>
        <div className="grid grid-cols-7 gap-1">
          {Array.from({ length: 35 }).map((_, i) => (
            <Skeleton key={i} className="aspect-square rounded" />
          ))}
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <span className="text-sm font-medium">{monthLabel}</span>
        <div className="flex gap-1">
          <Button
            variant="ghost"
            size="icon"
            className="size-8"
            onClick={prevMonth}
            aria-label="Previous month"
          >
            <IconChevronLeft className="size-4" />
          </Button>
          <Button
            variant="ghost"
            size="icon"
            className="size-8"
            onClick={nextMonth}
            aria-label="Next month"
          >
            <IconChevronRight className="size-4" />
          </Button>
        </div>
      </div>

      <div className="grid grid-cols-7 gap-1 text-center text-xs text-muted-foreground">
        {WEEKDAY_LABELS.map((d) => (
          <span key={d}>{d}</span>
        ))}
      </div>

      <div className="grid grid-cols-7 gap-1">
        {Array.from({ length: firstDayOffset }).map((_, i) => (
          <div key={`empty-${i}`} />
        ))}
        {days.map((d) => {
          const iso = toISODate(d)
          const count = countMap.get(iso) ?? 0
          const intensity = getIntensity(count, maxCount)
          const isSelected = selectedDate === iso
          const today = new Date()
          today.setHours(0, 0, 0, 0)
          const isFuture = d > today

          return (
            <button
              key={iso}
              type="button"
              disabled={isFuture}
              onClick={() => !isFuture && onSelectDate?.(iso)}
              title={`${iso}: ${count} items`}
              className={`aspect-square rounded text-[10px] transition-colors ${INTENSITY_CLASSES[intensity]} ${
                isSelected
                  ? 'ring-2 ring-primary ring-offset-1 ring-offset-background'
                  : ''
              } ${isFuture ? 'opacity-30 cursor-not-allowed' : 'hover:ring-1 hover:ring-foreground/30'}`}
            >
              {d.getDate()}
            </button>
          )
        })}
      </div>

      <div className="flex items-center justify-end gap-1.5 text-xs text-muted-foreground">
        <span>Less</span>
        {INTENSITY_CLASSES.map((cls, i) => (
          <span
            key={i}
            className={`inline-block size-3 rounded-sm ${cls}`}
          />
        ))}
        <span>More</span>
      </div>
    </div>
  )
}

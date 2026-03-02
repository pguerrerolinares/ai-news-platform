import { useState, useEffect, useCallback, useMemo } from 'react'
import { CalendarHeatmap } from '@/components/calendar-heatmap'
import { TopicFilter } from '@/components/topic-filter'
import { NewsCard } from '@/components/news-card'
import { Skeleton } from '@/components/ui/skeleton'
import { Button } from '@/components/ui/button'
import { apiGet } from '@/lib/api'
import { IconRefresh } from '@tabler/icons-react'
import type { StatsDateItem, StatsGroupDateItem, NewsItem } from '@/lib/types'

/** Get first and last day of the month containing `date`. */
function monthRange(date: Date): { from: string; to: string } {
  const y = date.getFullYear()
  const m = date.getMonth()
  const first = new Date(y, m, 1)
  const last = new Date(y, m + 1, 0)
  const fmt = (d: Date) =>
    `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
  return { from: fmt(first), to: fmt(last) }
}

export default function Timeline() {
  const [viewDate, setViewDate] = useState(() => new Date())
  const [heatmapData, setHeatmapData] = useState<StatsDateItem[]>([])
  const [heatmapLoading, setHeatmapLoading] = useState(true)

  const [selectedDate, setSelectedDate] = useState<string | null>(
    () => new Date().toISOString().split('T')[0],
  )
  const [dayItems, setDayItems] = useState<NewsItem[]>([])
  const [dayLoading, setDayLoading] = useState(false)
  const [dayError, setDayError] = useState('')

  const [topicData, setTopicData] = useState<StatsGroupDateItem[]>([])

  const range = useMemo(() => monthRange(viewDate), [viewDate])

  // Fetch heatmap + topic stats for the visible month
  const fetchMonthData = useCallback(async () => {
    setHeatmapLoading(true)
    try {
      const [heatRes, topicRes] = await Promise.all([
        apiGet<StatsDateItem[]>('/api/stats/by-date', {
          date_from: range.from,
          date_to: range.to,
        }),
        apiGet<StatsGroupDateItem[]>('/api/stats/by-topic-date', {
          date_from: range.from,
          date_to: range.to,
        }),
      ])
      setHeatmapData(heatRes.data)
      setTopicData(topicRes.data)
    } catch {
      setHeatmapData([])
      setTopicData([])
    } finally {
      setHeatmapLoading(false)
    }
  }, [range.from, range.to])

  useEffect(() => {
    fetchMonthData()
  }, [fetchMonthData])

  // Fetch items for today on mount
  useEffect(() => {
    if (selectedDate) {
      fetchDayItems(selectedDate)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Fetch items for the selected date
  const fetchDayItems = useCallback(async (date: string) => {
    setDayLoading(true)
    setDayError('')
    try {
      const { data } = await apiGet<NewsItem[]>(`/api/items/by-date/${date}`, {
        limit: '100',
      })
      setDayItems(data)
    } catch (err) {
      setDayError(err instanceof Error ? err.message : 'Error loading items')
      setDayItems([])
    } finally {
      setDayLoading(false)
    }
  }, [])

  const handleSelectDate = useCallback(
    (date: string) => {
      if (selectedDate === date) {
        setSelectedDate(null)
        setDayItems([])
        return
      }
      setSelectedDate(date)
      setActiveTopic('all')
      fetchDayItems(date)
    },
    [selectedDate, fetchDayItems],
  )

  // Sync the heatmap's internal month with our viewDate
  const handleHeatmapMonthChange = useCallback((date: Date) => {
    setViewDate(date)
    setSelectedDate(null)
    setDayItems([])
  }, [])

  const [activeTopic, setActiveTopic] = useState('all')

  // Filter items by selected topic
  const filteredItems = useMemo(() => {
    if (activeTopic === 'all') return dayItems
    return dayItems.filter((item) => (item.topic ?? 'uncategorized') === activeTopic)
  }, [dayItems, activeTopic])

  // Topic summary for the selected date from stats data
  const dateSummary = useMemo(() => {
    if (!selectedDate) return null
    const filtered = topicData.filter((d) => d.date === selectedDate)
    const total = filtered.reduce((sum, d) => sum + d.count, 0)
    return { total, topics: filtered.length }
  }, [selectedDate, topicData])

  return (
    <div className="mx-auto max-w-2xl space-y-6 px-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold tracking-tight">Timeline</h2>
          <p className="text-sm text-muted-foreground">
            Activity heatmap and topic breakdown over time
          </p>
        </div>
        <Button variant="ghost" size="icon" onClick={fetchMonthData} title="Refresh">
          <IconRefresh className="size-4" />
        </Button>
      </div>

      <CalendarHeatmap
        data={heatmapData}
        loading={heatmapLoading}
        selectedDate={selectedDate}
        onSelectDate={handleSelectDate}
        onMonthChange={handleHeatmapMonthChange}
      />

      {selectedDate && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-lg font-semibold">{selectedDate}</h3>
            {dateSummary && (
              <span className="text-sm text-muted-foreground">
                {dateSummary.total} items across {dateSummary.topics} topics
              </span>
            )}
          </div>

          {dayLoading && (
            <div className="space-y-3">
              {Array.from({ length: 3 }).map((_, i) => (
                <Skeleton key={i} className="h-20 w-full rounded-lg" />
              ))}
            </div>
          )}

          {dayError && (
            <div className="flex flex-col items-center gap-4 py-12">
              <p className="text-destructive">{dayError}</p>
              <Button
                variant="outline"
                onClick={() => fetchDayItems(selectedDate)}
              >
                <IconRefresh className="mr-2 size-4" /> Retry
              </Button>
            </div>
          )}

          {!dayLoading && !dayError && dayItems.length === 0 && (
            <p className="py-8 text-center text-muted-foreground">
              No items for this date
            </p>
          )}

          {!dayLoading && !dayError && dayItems.length > 0 && (
            <>
              <TopicFilter value={activeTopic} onChange={setActiveTopic} />
              <div className="space-y-4">
                {filteredItems.map((item) => (
                  <NewsCard key={item.id} item={item} />
                ))}
              </div>
              {filteredItems.length === 0 && (
                <p className="py-8 text-center text-muted-foreground">
                  No items for this topic
                </p>
              )}
            </>
          )}
        </div>
      )}

    </div>
  )
}

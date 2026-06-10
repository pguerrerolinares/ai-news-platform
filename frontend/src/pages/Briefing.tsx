import { useState, useEffect, useCallback } from 'react'
import { NewsCard } from '@/components/news-card'
import { Skeleton } from '@/components/ui/skeleton'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { apiGet } from '@/lib/api'
import { IconChevronLeft, IconChevronRight, IconRefresh } from '@tabler/icons-react'
import type { Briefing } from '@/lib/types'

function formatDate(date: Date): string {
  const y = date.getFullYear()
  const m = String(date.getMonth() + 1).padStart(2, '0')
  const d = String(date.getDate()).padStart(2, '0')
  return `${y}-${m}-${d}`
}

function addDays(date: Date, days: number): Date {
  const d = new Date(date)
  d.setDate(d.getDate() + days)
  return d
}

function displayDate(dateStr: string): string {
  // Parse as local date to avoid timezone-shift display issues
  const [y, m, d] = dateStr.split('-').map(Number)
  return new Date(y, m - 1, d).toLocaleDateString('en-US', {
    weekday: 'long',
    year: 'numeric',
    month: 'long',
    day: 'numeric',
  })
}

function formatGeneratedAt(iso: string): string {
  return new Date(iso).toLocaleString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export default function BriefingPage() {
  const [currentDate, setCurrentDate] = useState<Date>(() => new Date())
  const [briefing, setBriefing] = useState<Briefing | null>(null)
  const [loading, setLoading] = useState(false)
  const [notFound, setNotFound] = useState(false)
  const [error, setError] = useState('')

  const dateStr = formatDate(currentDate)

  const fetchBriefing = useCallback(async (date: string) => {
    setLoading(true)
    setNotFound(false)
    setError('')
    setBriefing(null)
    try {
      const { data } = await apiGet<Briefing>(`/api/briefings/${date}`)
      setBriefing(data)
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Error loading briefing'
      if (msg.includes('404') || msg.toLowerCase().includes('not found')) {
        setNotFound(true)
      } else {
        setError(msg)
      }
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchBriefing(dateStr)
  }, [dateStr, fetchBriefing])

  const isToday = formatDate(new Date()) === dateStr

  return (
    <div className="mx-auto max-w-2xl space-y-6 px-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold tracking-tight">Daily Briefing</h2>
          <p className="text-sm text-muted-foreground">
            Pipeline run summary and news items for a given day
          </p>
        </div>
        <Button
          variant="ghost"
          size="icon"
          onClick={() => fetchBriefing(dateStr)}
          title="Refresh"
        >
          <IconRefresh className="size-4" />
        </Button>
      </div>

      {/* Date navigation */}
      <div className="flex items-center justify-between rounded-lg border border-border bg-card px-4 py-2">
        <Button
          variant="ghost"
          size="icon"
          className="size-8"
          onClick={() => setCurrentDate((d) => addDays(d, -1))}
          aria-label="Previous day"
        >
          <IconChevronLeft className="size-4" />
        </Button>

        <div className="flex flex-col items-center gap-1">
          <p className="text-sm font-semibold">{displayDate(dateStr)}</p>
          <Input
            type="date"
            value={dateStr}
            max={formatDate(new Date())}
            onChange={(e) => {
              const val = e.target.value
              if (!val) return
              const [y, m, d] = val.split('-').map(Number)
              setCurrentDate(new Date(y, m - 1, d))
            }}
            className="h-7 w-36 cursor-pointer px-2 py-0 text-xs"
            aria-label="Pick a date"
          />
        </div>

        <Button
          variant="ghost"
          size="icon"
          className="size-8"
          onClick={() => setCurrentDate((d) => addDays(d, 1))}
          disabled={isToday}
          aria-label="Next day"
        >
          <IconChevronRight className="size-4" />
        </Button>
      </div>

      {/* Loading */}
      {loading && (
        <div className="space-y-4">
          <Skeleton className="h-28 w-full rounded-lg" />
          <div className="space-y-3">
            {Array.from({ length: 4 }).map((_, i) => (
              <Skeleton key={i} className="h-20 w-full rounded-lg" />
            ))}
          </div>
        </div>
      )}

      {/* Error */}
      {!loading && error && (
        <div className="flex flex-col items-center gap-4 py-12">
          <p className="text-destructive">{error}</p>
          <Button variant="outline" onClick={() => fetchBriefing(dateStr)}>
            <IconRefresh className="mr-2 size-4" /> Retry
          </Button>
        </div>
      )}

      {/* Not found / empty state */}
      {!loading && notFound && (
        <div className="flex flex-col items-center gap-2 py-16">
          <p className="text-lg font-medium">No briefing for this date</p>
          <p className="text-sm text-muted-foreground">
            The pipeline hasn't run for {displayDate(dateStr)} yet.
          </p>
        </div>
      )}

      {/* Briefing content */}
      {!loading && !error && briefing && (
        <div className="space-y-6">
          {/* Stats summary card */}
          {briefing.generated_at != null ? (
            <div className="rounded-lg border border-border bg-card p-4 space-y-4">
              <div className="flex items-start justify-between gap-2">
                <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide">
                  Pipeline Summary
                </h3>
                <span className="text-xs text-muted-foreground">
                  Generated {formatGeneratedAt(briefing.generated_at)}
                </span>
              </div>

              <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
                <StatCell label="Extracted" value={briefing.items_extracted} />
                <StatCell label="After dedup" value={briefing.items_after_dedup} />
                <StatCell label="Filtered" value={briefing.items_filtered} />
                <StatCell label="Total items" value={briefing.total_items} />
                <StatCell label="Trending" value={briefing.trending_count} />
                {briefing.duration_seconds != null && (
                  <div className="flex flex-col gap-0.5">
                    <span className="text-xs text-muted-foreground">Duration</span>
                    <span className="text-lg font-bold tabular-nums">
                      {briefing.duration_seconds.toFixed(1)}s
                    </span>
                  </div>
                )}
              </div>

              {briefing.sources_used && briefing.sources_used.sources.length > 0 && (
                <div className="space-y-1.5">
                  <span className="text-xs text-muted-foreground">Sources</span>
                  <div className="flex flex-wrap gap-1.5">
                    {briefing.sources_used.sources.map((src) => (
                      <Badge key={src} variant="secondary" className="text-xs">
                        {src}
                      </Badge>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ) : (
            <div className="rounded-lg border border-border bg-card px-4 py-3">
              <p className="text-xs text-muted-foreground">
                No pipeline summary recorded for this date.
              </p>
            </div>
          )}

          {/* Items list */}
          {briefing.items.length === 0 ? (
            <p className="py-8 text-center text-muted-foreground">
              No items in this briefing
            </p>
          ) : (
            <div className="space-y-4">
              <p className="text-sm text-muted-foreground">
                {briefing.items.length} item{briefing.items.length !== 1 ? 's' : ''}
              </p>
              {briefing.items.map((item) => (
                <NewsCard key={item.id} item={item} />
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

function StatCell({ label, value }: { label: string; value: number | null }) {
  return (
    <div className="flex flex-col gap-0.5">
      <span className="text-xs text-muted-foreground">{label}</span>
      <span className="text-lg font-bold tabular-nums">
        {value ?? '—'}
      </span>
    </div>
  )
}

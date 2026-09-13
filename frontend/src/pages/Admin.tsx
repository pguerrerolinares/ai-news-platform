import React, { useState, useEffect, useCallback, useMemo, useRef } from 'react'
import { apiGet } from '@/lib/api'
import type { SourceFreshness, PipelineRun, AuditReport, AuditDailyRow, HealthAlert } from '@/lib/types'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Button } from '@/components/ui/button'
import {
  Table,
  TableHeader,
  TableBody,
  TableRow,
  TableHead,
  TableCell,
} from '@/components/ui/table'
import { IconRefresh, IconChevronDown } from '@tabler/icons-react'
import {
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
  ChartLegend,
  ChartLegendContent,
  type ChartConfig,
} from '@/components/ui/chart'
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
} from 'recharts'

// ── helpers ──────────────────────────────────────────────────────────────────

function relativeTime(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime()
  const m = Math.floor(diff / 60_000)
  if (m < 60) return `${m}m ago`
  const h = Math.floor(m / 60)
  if (h < 24) return `${h}h ago`
  return `${Math.floor(h / 24)}d ago`
}

function fmtTime(iso: string): string {
  return new Date(iso).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}

function fmtTimeFull(iso: string): string {
  return new Date(iso).toLocaleString([], {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  })
}

function fmtDuration(s: number | null): string {
  if (s == null) return '—'
  if (s < 60) return `${s.toFixed(1)}s`
  return `${Math.floor(s / 60)}m ${Math.round(s % 60)}s`
}

// A palette of chart colours that works on both light and dark themes.
// Using HSL-based CSS variables from the shadcn theme where possible.
const SOURCE_COLORS = [
  'hsl(var(--chart-1))',
  'hsl(var(--chart-2))',
  'hsl(var(--chart-3))',
  'hsl(var(--chart-4))',
  'hsl(var(--chart-5))',
  '#a78bfa',
  '#34d399',
  '#fb923c',
]

// ── sub-components ────────────────────────────────────────────────────────────

function HealthDot({ status }: { status: SourceFreshness['status'] }) {
  const color =
    status === 'ok'
      ? 'bg-green-500'
      : status === 'stale'
        ? 'bg-amber-400'
        : 'bg-red-500'
  return <span className={`inline-block size-2 rounded-full ${color} shrink-0`} />
}

function FreshnessStrip({ data }: { data: SourceFreshness[] }) {
  if (data.length === 0)
    return <p className="text-sm text-muted-foreground">No sources found.</p>

  return (
    <div className="flex flex-wrap gap-2">
      {data.map((s) => (
        <Badge
          key={s.source}
          variant="outline"
          className="flex items-center gap-1.5 py-1 px-2.5 text-xs font-normal"
        >
          <HealthDot status={s.status} />
          <span className="font-medium">{s.source}</span>
          <span className="text-muted-foreground">
            {s.hours_ago != null ? `${s.hours_ago.toFixed(1)}h` : 'never'}
          </span>
        </Badge>
      ))}
    </div>
  )
}

type RunStatus = 'all' | 'success' | 'empty' | 'error' | 'interrupted' | 'degraded'

const AMBER_BADGE_CLASS = 'border-amber-400 text-amber-600 dark:text-amber-400'

function statusBadge(
  status: PipelineRun['status'],
): { variant: 'default' | 'secondary' | 'destructive' | 'outline'; className?: string } {
  if (status === 'success') return { variant: 'default' }
  if (status === 'error') return { variant: 'destructive' }
  if (status === 'empty') return { variant: 'secondary' }
  // interrupted, degraded
  return { variant: 'outline', className: AMBER_BADGE_CLASS }
}

function funnelText(run: PipelineRun): string {
  return [
    run.items_extracted,
    run.items_after_dedup,
    run.items_seen_filtered,
    run.items_classified,
    run.items_validated,
    run.items_stored,
  ].join('→')
}

// ── Run detail (inline) ───────────────────────────────────────────────────────

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false)
  const handleCopy = () => {
    void navigator.clipboard.writeText(text)
    setCopied(true)
    setTimeout(() => setCopied(false), 1500)
  }
  return (
    <button
      onClick={handleCopy}
      className="ml-1.5 rounded px-1.5 py-0.5 text-[10px] font-medium bg-muted hover:bg-muted/80 text-muted-foreground transition-colors shrink-0"
      title="Copy to clipboard"
    >
      {copied ? 'copied' : 'copy'}
    </button>
  )
}

function FunnelCell({ label, value }: { label: string; value: number }) {
  return (
    <div className="flex flex-col items-center rounded-md border bg-muted/30 px-3 py-2 gap-0.5">
      <span className="text-[10px] text-muted-foreground uppercase tracking-wide">{label}</span>
      <span className="text-sm font-mono font-semibold tabular-nums">{value}</span>
    </div>
  )
}

function RunDetailInline({ run }: { run: PipelineRun }) {
  return (
    <div className="flex flex-col gap-4 px-3 py-4 bg-muted/10 border-t">
      {/* Header row: timestamp + duration */}
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1">
        <span className="text-xs font-mono text-foreground">
          {fmtTimeFull(run.started_at)}
        </span>
        <span className="text-xs text-muted-foreground">({relativeTime(run.started_at)})</span>
        <span className="text-xs">
          Duration:{' '}
          <span className="font-mono font-semibold">{fmtDuration(run.duration_seconds)}</span>
        </span>
      </div>

      {/* Sources */}
      <div>
        <p className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground mb-1.5">
          Sources
        </p>
        <div className="flex flex-wrap gap-1.5">
          {run.sources.length > 0
            ? run.sources.map((s) => (
                <Badge key={s} variant="outline" className="text-xs font-normal">
                  {s}
                </Badge>
              ))
            : <span className="text-xs text-muted-foreground">—</span>
          }
        </div>
      </div>

      {/* Funnel — responsive grid, stacks to 2 cols on mobile */}
      <div>
        <p className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground mb-1.5">
          Pipeline Funnel
        </p>
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-6 gap-2">
          <FunnelCell label="Extracted" value={run.items_extracted} />
          <FunnelCell label="After dedup" value={run.items_after_dedup} />
          <FunnelCell label="Seen filt." value={run.items_seen_filtered} />
          <FunnelCell label="Classified" value={run.items_classified} />
          <FunnelCell label="Validated" value={run.items_validated} />
          <FunnelCell label="Stored" value={run.items_stored} />
        </div>
      </div>

      {/* Error message — prominent, full-width, wraps on mobile */}
      {run.error_message && (
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-wide text-destructive mb-1.5">
            Error
          </p>
          <pre className="rounded-md bg-destructive/10 border border-destructive/30 p-3 text-[11px] font-mono text-destructive whitespace-pre-wrap break-words leading-relaxed w-full overflow-hidden">
            {run.error_message}
          </pre>
        </div>
      )}

      {/* IDs — each on its own row, wrap on mobile */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground mb-1">
            Correlation ID
          </p>
          {run.correlation_id ? (
            <div className="flex items-start gap-1 min-w-0">
              <code className="text-[11px] font-mono text-foreground break-all min-w-0">
                {run.correlation_id}
              </code>
              <CopyButton text={run.correlation_id} />
            </div>
          ) : (
            <span className="text-xs text-muted-foreground">—</span>
          )}
        </div>
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground mb-1">
            Run ID
          </p>
          <div className="flex items-start gap-1 min-w-0">
            <code className="text-[11px] font-mono text-muted-foreground break-all min-w-0">
              {run.id}
            </code>
            <CopyButton text={run.id} />
          </div>
        </div>
      </div>
    </div>
  )
}

// ── Pipeline table with pagination ────────────────────────────────────────────

const PAGE_SIZE = 25

// Columns: chevron | Time | Status | Duration (hidden xs) | Sources (hidden sm) | Funnel (hidden md)
// At 375px only chevron + Time + Status are visible — no horizontal overflow needed.
const RUNS_COL_SPAN = 6

function PipelineTable({
  runs,
  filter,
  onFilterChange,
  page,
  totalCount,
  onPageChange,
}: {
  runs: PipelineRun[]
  filter: RunStatus
  onFilterChange: (v: RunStatus) => void
  page: number
  totalCount: number | null
  onPageChange: (page: number) => void
}) {
  const [expandedRunId, setExpandedRunId] = useState<string | null>(null)

  const totalPages = totalCount != null ? Math.ceil(totalCount / PAGE_SIZE) : null
  const hasNext = totalPages != null ? page + 1 < totalPages : runs.length === PAGE_SIZE
  const hasPrev = page > 0

  const handleRowClick = (run: PipelineRun) => {
    setExpandedRunId((prev) => (prev === run.id ? null : run.id))
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <p className="text-sm text-muted-foreground">
          {totalCount != null
            ? `${totalCount} total · page ${page + 1}${totalPages != null ? ` / ${totalPages}` : ''}`
            : `${runs.length} runs shown`}
        </p>
        <Select value={filter} onValueChange={(v) => onFilterChange(v as RunStatus)}>
          <SelectTrigger size="sm" className="w-32">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All</SelectItem>
            <SelectItem value="success">Success</SelectItem>
            <SelectItem value="empty">Empty</SelectItem>
            <SelectItem value="error">Error</SelectItem>
            <SelectItem value="interrupted">Interrupted</SelectItem>
            <SelectItem value="degraded">Degraded</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {runs.length === 0 ? (
        <p className="py-6 text-center text-sm text-muted-foreground">No runs match this filter.</p>
      ) : (
        <div className="rounded-lg border [&_[data-slot=table-container]]:overflow-x-hidden">
          <Table className="text-xs">
            <TableHeader className="bg-muted/40">
              <TableRow className="hover:bg-transparent">
                {/* chevron column */}
                <TableHead className="w-6 px-2 py-2 text-muted-foreground" />
                <TableHead className="px-3 py-2 text-muted-foreground font-medium">Time</TableHead>
                <TableHead className="px-3 py-2 text-muted-foreground font-medium">Status</TableHead>
                <TableHead className="px-3 py-2 text-muted-foreground font-medium hidden sm:table-cell">Duration</TableHead>
                <TableHead className="px-3 py-2 text-muted-foreground font-medium hidden sm:table-cell">Sources</TableHead>
                <TableHead
                  className="px-3 py-2 text-muted-foreground font-medium hidden md:table-cell"
                  title="extracted→dedup→seen→classified→validated→stored"
                >
                  Funnel
                </TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {runs.map((run) => {
                const isExpanded = expandedRunId === run.id
                return (
                  <React.Fragment key={run.id}>
                    <TableRow
                      className={`cursor-pointer ${
                        isExpanded
                          ? 'bg-muted/20 border-b-0 hover:bg-muted/20'
                          : 'hover:bg-muted/30'
                      }`}
                      onClick={() => handleRowClick(run)}
                      title="Click to expand run details"
                    >
                      {/* Chevron */}
                      <TableCell className="w-6 px-2 py-2 text-muted-foreground">
                        <IconChevronDown
                          className={`size-3.5 transition-transform duration-200 ${isExpanded ? 'rotate-180' : ''}`}
                        />
                      </TableCell>
                      <TableCell className="px-3 py-2 tabular-nums whitespace-nowrap">
                        {fmtTime(run.started_at)}
                        <span className="ml-1 text-muted-foreground">
                          {relativeTime(run.started_at)}
                        </span>
                      </TableCell>
                      <TableCell className="px-3 py-2">
                        {(() => {
                          const badge = statusBadge(run.status)
                          return (
                            <Badge
                              variant={badge.variant}
                              className={`text-xs ${badge.className ?? ''}`}
                            >
                              {run.status}
                            </Badge>
                          )
                        })()}
                      </TableCell>
                      <TableCell className="px-3 py-2 tabular-nums whitespace-nowrap hidden sm:table-cell">
                        {fmtDuration(run.duration_seconds)}
                      </TableCell>
                      <TableCell className="px-3 py-2 hidden sm:table-cell">
                        {run.sources.join(', ') || '—'}
                      </TableCell>
                      <TableCell className="px-3 py-2 font-mono text-[10px] text-muted-foreground hidden md:table-cell whitespace-nowrap">
                        {funnelText(run)}
                        {run.error_message && (
                          <span className="ml-1 text-destructive">· err</span>
                        )}
                      </TableCell>
                    </TableRow>
                    {isExpanded && (
                      <TableRow className="border-b hover:bg-transparent">
                        <TableCell colSpan={RUNS_COL_SPAN} className="p-0">
                          <RunDetailInline run={run} />
                        </TableCell>
                      </TableRow>
                    )}
                  </React.Fragment>
                )
              })}
            </TableBody>
          </Table>
        </div>
      )}

      {/* Pagination controls */}
      {(hasPrev || hasNext) && (
        <div className="flex items-center justify-between pt-1">
          <Button
            variant="outline"
            size="sm"
            disabled={!hasPrev}
            onClick={() => onPageChange(page - 1)}
          >
            Previous
          </Button>
          <span className="text-xs text-muted-foreground tabular-nums">
            Page {page + 1}{totalPages != null ? ` of ${totalPages}` : ''}
          </span>
          <Button
            variant="outline"
            size="sm"
            disabled={!hasNext}
            onClick={() => onPageChange(page + 1)}
          >
            Next
          </Button>
        </div>
      )}
    </div>
  )
}

// Build recharts-friendly data: one row per date, one key per source
function buildChartData(
  breakdown: AuditDailyRow[],
  sources: string[],
): Array<Record<string, string | number>> {
  const byDate = new Map<string, Record<string, string | number>>()
  for (const row of breakdown) {
    if (!byDate.has(row.date)) byDate.set(row.date, { date: row.date })
    const entry = byDate.get(row.date)!
    entry[row.source] = (entry[row.source] as number ?? 0) + row.count
  }
  // Fill zeros for sources not present on a given date
  for (const entry of byDate.values()) {
    for (const src of sources) {
      if (!(src in entry)) entry[src] = 0
    }
  }
  return Array.from(byDate.values()).sort((a, b) =>
    String(a.date).localeCompare(String(b.date)),
  )
}

function IngestionChart({
  audit,
  days,
  onDaysChange,
}: {
  audit: AuditReport
  days: string
  onDaysChange: (v: string) => void
}) {
  const sources = useMemo(
    () => audit.sources.map((s) => s.source),
    [audit.sources],
  )

  const chartData = useMemo(
    () => buildChartData(audit.daily_breakdown, sources),
    [audit.daily_breakdown, sources],
  )

  const chartConfig = useMemo<ChartConfig>(() => {
    const cfg: ChartConfig = {}
    sources.forEach((src, i) => {
      cfg[src] = { label: src, color: SOURCE_COLORS[i % SOURCE_COLORS.length] }
    })
    return cfg
  }, [sources])

  if (chartData.length === 0)
    return <p className="py-6 text-center text-sm text-muted-foreground">No ingestion data.</p>

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <p className="text-sm text-muted-foreground">Items per day by source</p>
        <Select value={days} onValueChange={onDaysChange}>
          <SelectTrigger size="sm" className="w-24">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="7">7 days</SelectItem>
            <SelectItem value="14">14 days</SelectItem>
            <SelectItem value="30">30 days</SelectItem>
          </SelectContent>
        </Select>
      </div>
      <ChartContainer config={chartConfig} className="h-48 w-full">
        <BarChart data={chartData} margin={{ top: 4, right: 4, left: -16, bottom: 0 }}>
          <CartesianGrid vertical={false} strokeDasharray="3 3" />
          <XAxis
            dataKey="date"
            tickLine={false}
            axisLine={false}
            tickFormatter={(v: string) => v.slice(5)} // MM-DD
            interval="preserveStartEnd"
          />
          <YAxis tickLine={false} axisLine={false} allowDecimals={false} />
          <ChartTooltip content={<ChartTooltipContent />} />
          <ChartLegend content={<ChartLegendContent />} />
          {sources.map((src, i) => (
            <Bar
              key={src}
              dataKey={src}
              stackId="a"
              fill={SOURCE_COLORS[i % SOURCE_COLORS.length]}
              radius={i === sources.length - 1 ? [2, 2, 0, 0] : [0, 0, 0, 0]}
            />
          ))}
        </BarChart>
      </ChartContainer>
    </div>
  )
}

// ── Per-source breakdown table ────────────────────────────────────────────────

function SourceBreakdownTable({ audit }: { audit: AuditReport }) {
  const sorted = useMemo(
    () => [...audit.sources].sort((a, b) => b.count - a.count),
    [audit.sources],
  )

  if (sorted.length === 0)
    return <p className="text-sm text-muted-foreground">No source data.</p>

  const total = audit.total_items

  return (
    <div className="rounded-lg border [&_[data-slot=table-container]]:overflow-x-hidden">
      <Table className="text-xs">
        <TableHeader className="bg-muted/40">
          <TableRow className="hover:bg-transparent">
            <TableHead className="px-3 py-2 text-muted-foreground font-medium">Source</TableHead>
            <TableHead className="px-3 py-2 text-right text-muted-foreground font-medium tabular-nums">Items</TableHead>
            <TableHead className="px-3 py-2 text-right text-muted-foreground font-medium tabular-nums">% of total</TableHead>
            <TableHead className="px-3 py-2 text-muted-foreground font-medium hidden sm:table-cell">Last item</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {sorted.map((row) => {
            const pct = total > 0 ? ((row.count / total) * 100).toFixed(1) : '0.0'
            const lastAt = row.last_item_at ? relativeTime(row.last_item_at) : '—'
            return (
              <TableRow key={row.source} className="hover:bg-muted/20">
                <TableCell className="px-3 py-2 font-medium">{row.source}</TableCell>
                <TableCell className="px-3 py-2 text-right tabular-nums font-mono">
                  {row.count.toLocaleString()}
                </TableCell>
                <TableCell className="px-3 py-2 text-right tabular-nums">
                  <span className="text-muted-foreground">{pct}%</span>
                </TableCell>
                <TableCell className="px-3 py-2 text-muted-foreground hidden sm:table-cell">
                  {lastAt}
                </TableCell>
              </TableRow>
            )
          })}
        </TableBody>
      </Table>
    </div>
  )
}

function fmtDate(iso: string): string {
  // "2026-02-28 17:37:03.242982+00:00" → "2026-02-28"
  return iso.slice(0, 10)
}

function AuditFooter({ audit }: { audit: AuditReport }) {
  const range =
    'oldest' in audit.date_range && audit.date_range.oldest
      ? `${fmtDate(audit.date_range.oldest)} → ${fmtDate(audit.date_range.newest)}`
      : 'no data'

  return (
    <div className="flex flex-wrap gap-4 text-sm text-muted-foreground">
      <span>
        <span className="font-semibold text-foreground">{audit.total_items.toLocaleString()}</span>{' '}
        total items
      </span>
      <span>Range: {range}</span>
      <span>
        <span className="font-semibold text-foreground">
          {audit.duplicates.duplicate_groups}
        </span>{' '}
        duplicate groups /{' '}
        <span className="font-semibold text-foreground">{audit.duplicates.extra_items}</span> extra
        items
      </span>
    </div>
  )
}

// ── Health alerts panel ────────────────────────────────────────────────────────

function HealthAlertsCard({
  alerts,
  loading,
  error,
  checkedAt,
}: {
  alerts: HealthAlert[]
  loading: boolean
  error: string
  checkedAt: string | null
}) {
  const hasCritical = alerts.some((a) => a.severity === 'critical')
  const hasWarning = alerts.some((a) => a.severity === 'warning')
  const borderClass = hasCritical
    ? 'border-destructive/50'
    : hasWarning
      ? 'border-amber-400/50'
      : ''

  return (
    <Card className={borderClass}>
      <CardHeader className="pb-0">
        <CardTitle className="text-base">Health Alerts</CardTitle>
        <CardDescription>
          Derived from pipeline runs, source freshness and configuration · refreshes every 60 s
        </CardDescription>
      </CardHeader>
      <CardContent>
        {loading && checkedAt === null ? (
          <div className="space-y-2">
            <Skeleton className="h-6 w-full" />
            <Skeleton className="h-6 w-full" />
          </div>
        ) : error ? (
          <p className="text-sm text-destructive">Could not load health status.</p>
        ) : alerts.length === 0 ? (
          <div className="flex items-center gap-2 text-sm">
            <HealthDot status="ok" />
            <span>All checks passing</span>
            {checkedAt && (
              <span className="text-muted-foreground">checked {fmtTime(checkedAt)}</span>
            )}
          </div>
        ) : (
          <ul className="space-y-2">
            {alerts.map((a) => (
              <li
                key={a.code}
                data-testid="health-alert"
                data-code={a.code}
                className="flex flex-wrap items-center gap-2 text-sm"
              >
                {a.severity === 'critical' ? (
                  <Badge variant="destructive">CRITICAL</Badge>
                ) : (
                  <Badge variant="outline" className={AMBER_BADGE_CLASS}>
                    WARNING
                  </Badge>
                )}
                <span>{a.message}</span>
                {a.since && (
                  <span className="text-muted-foreground">since {relativeTime(a.since)}</span>
                )}
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  )
}

// ── main page ─────────────────────────────────────────────────────────────────

export default function Admin() {
  // -- health alerts --
  const [health, setHealth] = useState<HealthAlert[]>([])
  const [healthLoading, setHealthLoading] = useState(true)
  const [healthError, setHealthError] = useState('')
  const [healthCheckedAt, setHealthCheckedAt] = useState<string | null>(null)
  const healthInflight = useRef(false)

  // -- freshness --
  const [freshness, setFreshness] = useState<SourceFreshness[]>([])
  const [freshnessLoading, setFreshnessLoading] = useState(true)
  const [freshnessError, setFreshnessError] = useState('')

  // -- pipeline runs --
  const [runs, setRuns] = useState<PipelineRun[]>([])
  const [runsLoading, setRunsLoading] = useState(true)
  const [runsError, setRunsError] = useState('')
  const [runFilter, setRunFilter] = useState<RunStatus>('all')
  const [runsPage, setRunsPage] = useState(0)
  const [runsTotalCount, setRunsTotalCount] = useState<number | null>(null)


  // -- audit --
  const [audit, setAudit] = useState<AuditReport | null>(null)
  const [auditLoading, setAuditLoading] = useState(true)
  const [auditError, setAuditError] = useState('')
  const [auditDays, setAuditDays] = useState('14')

  const fetchHealth = useCallback(async () => {
    if (healthInflight.current) return // don't stack requests (60s interval + manual refresh)
    healthInflight.current = true
    setHealthLoading(true)
    setHealthError('')
    try {
      const { data } = await apiGet<HealthAlert[]>('/api/admin/health')
      setHealth(data)
      setHealthCheckedAt(new Date().toISOString())
    } catch (err) {
      setHealthError(err instanceof Error ? err.message : 'Error loading health')
    } finally {
      setHealthLoading(false)
      healthInflight.current = false
    }
  }, [])

  const fetchFreshness = useCallback(async () => {
    setFreshnessLoading(true)
    setFreshnessError('')
    try {
      const { data } = await apiGet<SourceFreshness[]>('/api/admin/freshness')
      setFreshness(data)
    } catch (err) {
      setFreshnessError(err instanceof Error ? err.message : 'Error loading freshness')
    } finally {
      setFreshnessLoading(false)
    }
  }, [])

  const fetchRuns = useCallback(
    async (status: RunStatus, page: number) => {
      setRunsLoading(true)
      setRunsError('')
      try {
        const params: Record<string, string> = {
          limit: String(PAGE_SIZE),
          offset: String(page * PAGE_SIZE),
        }
        if (status !== 'all') params.status = status
        const { data, totalCount } = await apiGet<PipelineRun[]>('/api/admin/pipeline-runs', params)
        setRuns(data)
        setRunsTotalCount(totalCount)
      } catch (err) {
        setRunsError(err instanceof Error ? err.message : 'Error loading runs')
      } finally {
        setRunsLoading(false)
      }
    },
    [],
  )

  const fetchAudit = useCallback(async (days: string) => {
    setAuditLoading(true)
    setAuditError('')
    try {
      const { data } = await apiGet<AuditReport>('/api/admin/audit', { days })
      setAudit(data)
    } catch (err) {
      setAuditError(err instanceof Error ? err.message : 'Error loading audit')
    } finally {
      setAuditLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchHealth()
    const id = setInterval(fetchHealth, 60_000)
    return () => clearInterval(id)
  }, [fetchHealth])
  useEffect(() => { fetchFreshness() }, [fetchFreshness])
  useEffect(() => { fetchRuns(runFilter, runsPage) }, [fetchRuns, runFilter, runsPage])
  useEffect(() => { fetchAudit(auditDays) }, [fetchAudit, auditDays])

  const handleRunFilterChange = (v: RunStatus) => {
    setRunFilter(v)
    setRunsPage(0) // reset to first page on filter change
  }

  const handleRunsPageChange = (page: number) => {
    setRunsPage(page)
  }

  const handleDaysChange = (v: string) => {
    setAuditDays(v)
  }

  const handleRefreshAll = () => {
    fetchHealth()
    fetchFreshness()
    fetchRuns(runFilter, runsPage)
    fetchAudit(auditDays)
  }

  return (
    <div className="mx-auto max-w-2xl space-y-6 px-4 pb-12">
      {/* Page header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold tracking-tight">Admin</h2>
          <p className="text-sm text-muted-foreground">Pipeline observability dashboard</p>
        </div>
        <Button variant="ghost" size="icon" onClick={handleRefreshAll} title="Refresh all">
          <IconRefresh className="size-4" />
        </Button>
      </div>

      {/* 0 — Health alerts */}
      <HealthAlertsCard
        alerts={health}
        loading={healthLoading}
        error={healthError}
        checkedAt={healthCheckedAt}
      />

      {/* 1 — Source health strip */}
      <Card>
        <CardHeader className="pb-0">
          <CardTitle className="text-base">Source Health</CardTitle>
          <CardDescription>Last item ingested per source</CardDescription>
        </CardHeader>
        <CardContent>
          {freshnessLoading ? (
            <div className="flex flex-wrap gap-2">
              {Array.from({ length: 4 }).map((_, i) => (
                <Skeleton key={i} className="h-6 w-28 rounded-full" />
              ))}
            </div>
          ) : freshnessError ? (
            <p className="text-sm text-destructive">{freshnessError}</p>
          ) : (
            <FreshnessStrip data={freshness} />
          )}
        </CardContent>
      </Card>

      {/* 2 — Pipeline runs table */}
      <Card>
        <CardHeader className="pb-0">
          <CardTitle className="text-base">Pipeline Runs</CardTitle>
          <CardDescription>Click a row to view full run details</CardDescription>
        </CardHeader>
        <CardContent>
          {runsLoading ? (
            <div className="space-y-2">
              {Array.from({ length: 5 }).map((_, i) => (
                <Skeleton key={i} className="h-8 w-full rounded" />
              ))}
            </div>
          ) : runsError ? (
            <p className="text-sm text-destructive">{runsError}</p>
          ) : (
            <PipelineTable
              runs={runs}
              filter={runFilter}
              onFilterChange={handleRunFilterChange}
              page={runsPage}
              totalCount={runsTotalCount}
              onPageChange={handleRunsPageChange}
            />
          )}
        </CardContent>
      </Card>

      {/* 3 — Ingestion chart */}
      <Card>
        <CardHeader className="pb-0">
          <CardTitle className="text-base">Ingestion Chart</CardTitle>
          <CardDescription>Daily items by source</CardDescription>
        </CardHeader>
        <CardContent>
          {auditLoading ? (
            <Skeleton className="h-48 w-full rounded" />
          ) : auditError ? (
            <p className="text-sm text-destructive">{auditError}</p>
          ) : audit ? (
            <IngestionChart audit={audit} days={auditDays} onDaysChange={handleDaysChange} />
          ) : null}
        </CardContent>
      </Card>

      {/* 4 — Per-source breakdown table */}
      {audit && !auditLoading && !auditError && (
        <Card>
          <CardHeader className="pb-0">
            <CardTitle className="text-base">Source Breakdown</CardTitle>
            <CardDescription>Items per source · sorted by volume</CardDescription>
          </CardHeader>
          <CardContent>
            <SourceBreakdownTable audit={audit} />
          </CardContent>
        </Card>
      )}

      {/* 5 — Totals footer */}
      {audit && !auditLoading && !auditError && (
        <Card>
          <CardContent className="pt-6">
            <AuditFooter audit={audit} />
          </CardContent>
        </Card>
      )}
    </div>
  )
}

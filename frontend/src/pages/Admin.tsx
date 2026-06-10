import { useState, useEffect, useCallback, useMemo } from 'react'
import { apiGet } from '@/lib/api'
import type { SourceFreshness, PipelineRun, AuditReport, AuditDailyRow } from '@/lib/types'
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
import { IconRefresh } from '@tabler/icons-react'
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
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
} from '@/components/ui/sheet'

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

type RunStatus = 'all' | 'success' | 'empty' | 'error'

function statusVariant(
  status: PipelineRun['status'],
): 'default' | 'secondary' | 'destructive' | 'outline' {
  if (status === 'success') return 'default'
  if (status === 'error') return 'destructive'
  return 'secondary'
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

// ── Run detail sheet ──────────────────────────────────────────────────────────

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
      className="ml-1.5 rounded px-1.5 py-0.5 text-[10px] font-medium bg-muted hover:bg-muted/80 text-muted-foreground transition-colors"
      title="Copy to clipboard"
    >
      {copied ? 'copied' : 'copy'}
    </button>
  )
}

function FunnelRow({ label, value }: { label: string; value: number }) {
  return (
    <div className="flex items-center justify-between py-1 border-b last:border-0">
      <span className="text-xs text-muted-foreground">{label}</span>
      <span className="text-xs font-mono font-semibold tabular-nums">{value}</span>
    </div>
  )
}

function RunDetailSheet({
  run,
  open,
  onOpenChange,
}: {
  run: PipelineRun | null
  open: boolean
  onOpenChange: (v: boolean) => void
}) {
  if (!run) return null

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="right" className="w-full sm:max-w-md overflow-y-auto">
        <SheetHeader className="pb-2">
          <SheetTitle className="flex items-center gap-2 text-base">
            Run Detail
            <Badge variant={statusVariant(run.status)} className="text-xs">
              {run.status}
            </Badge>
          </SheetTitle>
          <SheetDescription className="font-mono text-xs">
            {fmtTimeFull(run.started_at)}
            <span className="ml-2 text-muted-foreground">({relativeTime(run.started_at)})</span>
          </SheetDescription>
        </SheetHeader>

        <div className="flex flex-col gap-4 px-4 pb-6">
          {/* Timing */}
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mb-1">
              Timing
            </p>
            <p className="text-sm">
              Duration:{' '}
              <span className="font-mono font-semibold">{fmtDuration(run.duration_seconds)}</span>
            </p>
          </div>

          {/* Sources */}
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mb-1">
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

          {/* Funnel */}
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mb-1">
              Pipeline Funnel
            </p>
            <div className="rounded-md border px-3 py-1">
              <FunnelRow label="Extracted" value={run.items_extracted} />
              <FunnelRow label="After dedup" value={run.items_after_dedup} />
              <FunnelRow label="Seen filtered" value={run.items_seen_filtered} />
              <FunnelRow label="Classified" value={run.items_classified} />
              <FunnelRow label="Validated" value={run.items_validated} />
              <FunnelRow label="Stored" value={run.items_stored} />
            </div>
          </div>

          {/* Error message — prominent for error runs */}
          {run.error_message && (
            <div>
              <p className="text-xs font-semibold uppercase tracking-wide text-destructive mb-1">
                Error
              </p>
              <pre className="rounded-md bg-destructive/10 border border-destructive/30 p-3 text-[11px] font-mono text-destructive whitespace-pre-wrap break-all leading-relaxed">
                {run.error_message}
              </pre>
            </div>
          )}

          {/* Correlation ID */}
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mb-1">
              Correlation ID
            </p>
            {run.correlation_id ? (
              <div className="flex items-center gap-1">
                <code className="text-[11px] font-mono text-foreground break-all">
                  {run.correlation_id}
                </code>
                <CopyButton text={run.correlation_id} />
              </div>
            ) : (
              <span className="text-xs text-muted-foreground">—</span>
            )}
          </div>

          {/* Run ID */}
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mb-1">
              Run ID
            </p>
            <div className="flex items-center gap-1">
              <code className="text-[11px] font-mono text-muted-foreground break-all">{run.id}</code>
              <CopyButton text={run.id} />
            </div>
          </div>
        </div>
      </SheetContent>
    </Sheet>
  )
}

// ── Pipeline table with pagination ────────────────────────────────────────────

const PAGE_SIZE = 25

function PipelineTable({
  runs,
  filter,
  onFilterChange,
  page,
  totalCount,
  onPageChange,
  onRunClick,
}: {
  runs: PipelineRun[]
  filter: RunStatus
  onFilterChange: (v: RunStatus) => void
  page: number
  totalCount: number | null
  onPageChange: (page: number) => void
  onRunClick: (run: PipelineRun) => void
}) {
  const totalPages = totalCount != null ? Math.ceil(totalCount / PAGE_SIZE) : null
  const hasNext = totalPages != null ? page + 1 < totalPages : runs.length === PAGE_SIZE
  const hasPrev = page > 0

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
          </SelectContent>
        </Select>
      </div>

      {runs.length === 0 ? (
        <p className="py-6 text-center text-sm text-muted-foreground">No runs match this filter.</p>
      ) : (
        <div className="overflow-x-auto rounded-lg border">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b bg-muted/40 text-muted-foreground">
                <th className="px-3 py-2 text-left font-medium">Time</th>
                <th className="px-3 py-2 text-left font-medium">Status</th>
                <th className="px-3 py-2 text-left font-medium">Duration</th>
                <th className="px-3 py-2 text-left font-medium hidden sm:table-cell">Sources</th>
                <th className="px-3 py-2 text-left font-medium hidden md:table-cell" title="extracted→dedup→seen→classified→validated→stored">Funnel</th>
              </tr>
            </thead>
            <tbody>
              {runs.map((run) => (
                <tr
                  key={run.id}
                  className="border-b last:border-0 hover:bg-muted/30 transition-colors cursor-pointer"
                  onClick={() => onRunClick(run)}
                  title="Click to view run details"
                >
                  <td className="px-3 py-2 tabular-nums whitespace-nowrap">
                    {fmtTime(run.started_at)}
                    <span className="ml-1 text-muted-foreground">
                      {relativeTime(run.started_at)}
                    </span>
                  </td>
                  <td className="px-3 py-2">
                    <Badge variant={statusVariant(run.status)} className="text-xs">
                      {run.status}
                    </Badge>
                  </td>
                  <td className="px-3 py-2 tabular-nums whitespace-nowrap">
                    {fmtDuration(run.duration_seconds)}
                  </td>
                  <td className="px-3 py-2 hidden sm:table-cell">
                    {run.sources.join(', ') || '—'}
                  </td>
                  <td className="px-3 py-2 font-mono text-[10px] text-muted-foreground hidden md:table-cell whitespace-nowrap">
                    {funnelText(run)}
                    {run.error_message && (
                      <span className="ml-1 text-destructive">· err</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
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
    <div className="overflow-x-auto rounded-lg border">
      <table className="w-full text-xs">
        <thead>
          <tr className="border-b bg-muted/40 text-muted-foreground">
            <th className="px-3 py-2 text-left font-medium">Source</th>
            <th className="px-3 py-2 text-right font-medium tabular-nums">Items</th>
            <th className="px-3 py-2 text-right font-medium tabular-nums">% of total</th>
            <th className="px-3 py-2 text-left font-medium hidden sm:table-cell">Last item</th>
          </tr>
        </thead>
        <tbody>
          {sorted.map((row) => {
            const pct = total > 0 ? ((row.count / total) * 100).toFixed(1) : '0.0'
            const lastAt = row.last_item_at
              ? relativeTime(row.last_item_at)
              : '—'
            return (
              <tr key={row.source} className="border-b last:border-0 hover:bg-muted/20 transition-colors">
                <td className="px-3 py-2 font-medium">{row.source}</td>
                <td className="px-3 py-2 text-right tabular-nums font-mono">
                  {row.count.toLocaleString()}
                </td>
                <td className="px-3 py-2 text-right tabular-nums">
                  <span className="text-muted-foreground">{pct}%</span>
                </td>
                <td className="px-3 py-2 text-muted-foreground hidden sm:table-cell">
                  {lastAt}
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
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

// ── main page ─────────────────────────────────────────────────────────────────

export default function Admin() {
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

  // -- run detail sheet --
  const [selectedRun, setSelectedRun] = useState<PipelineRun | null>(null)
  const [sheetOpen, setSheetOpen] = useState(false)

  // -- audit --
  const [audit, setAudit] = useState<AuditReport | null>(null)
  const [auditLoading, setAuditLoading] = useState(true)
  const [auditError, setAuditError] = useState('')
  const [auditDays, setAuditDays] = useState('14')

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

  const handleRunClick = (run: PipelineRun) => {
    setSelectedRun(run)
    setSheetOpen(true)
  }

  const handleDaysChange = (v: string) => {
    setAuditDays(v)
  }

  const handleRefreshAll = () => {
    fetchFreshness()
    fetchRuns(runFilter, runsPage)
    fetchAudit(auditDays)
  }

  return (
    <div className="mx-auto max-w-2xl space-y-6 px-4 pb-12">
      {/* Run detail sheet */}
      <RunDetailSheet
        run={selectedRun}
        open={sheetOpen}
        onOpenChange={setSheetOpen}
      />

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
              onRunClick={handleRunClick}
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

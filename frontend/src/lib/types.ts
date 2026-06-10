export interface NewsItem {
  id: string;
  title: string;
  summary: string | null;
  url: string | null;
  source: string;
  topic: string | null;
  relevance_score: number | null;
  dev_value_score: number | null;
  credibility_score: number | null;
  priority: number | null;
  trending: boolean;
  published_at: string | null;
  created_at: string;
  author: string | null;
  score: number | null;
}

export interface StatsDateItem {
  date: string;
  count: number;
}

export interface StatsGroupDateItem {
  date: string;
  group: string;
  count: number;
}

export interface SourceFreshness {
  source: string;
  last_item_at: string | null;
  hours_ago: number | null;
  status: 'ok' | 'stale' | 'dead';
}

export interface PipelineRun {
  id: string;
  started_at: string;
  duration_seconds: number | null;
  status: 'success' | 'empty' | 'error';
  sources: string[];
  items_extracted: number;
  items_after_dedup: number;
  items_seen_filtered: number;
  items_classified: number;
  items_validated: number;
  items_stored: number;
  error_message: string | null;
  correlation_id: string | null;
}

export interface AuditSourceRow {
  source: string;
  count: number;
  last_item_at: string | null;
}

export interface AuditDailyRow {
  date: string;
  source: string;
  count: number;
}

export interface AuditReport {
  total_items: number;
  date_range: { oldest: string; newest: string } | Record<string, never>;
  sources: AuditSourceRow[];
  daily_breakdown: AuditDailyRow[];
  duplicates: { duplicate_groups: number; extra_items: number };
}

export interface Briefing {
  date: string;
  total_items: number | null;
  items_extracted: number | null;
  items_after_dedup: number | null;
  items_filtered: number | null;
  trending_count: number | null;
  duration_seconds: number | null;
  sources_used: { sources: string[] } | null;
  generated_at: string;
  items: NewsItem[];
}

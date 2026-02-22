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

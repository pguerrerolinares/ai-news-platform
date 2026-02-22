import { Component, OnInit, inject, signal, computed } from '@angular/core';
import { DatePipe, UpperCasePipe } from '@angular/common';
import { NewsService } from '../services/news.service';
import { NewsItem, Briefing } from '../models/news-item';
import { NewsItemCard } from '../components/news-item-card';

@Component({
  selector: 'app-dashboard',
  imports: [DatePipe, UpperCasePipe, NewsItemCard],
  template: `
    <div class="editorial">
      <!-- Header -->
      <header class="ed-header">
        <div class="ed-header-top">
          <span class="mono text-muted vol-label">Vol. I &bull; {{ todayFormatted() }}</span>
        </div>
        <h1 class="ed-title">AI News<br/>Aggregator</h1>
        <div class="ed-header-meta">
          <span class="mono text-muted"><span class="status-dot"></span> Online</span>
          <span class="mono text-muted">{{ items().length }} noticias</span>
        </div>
      </header>

      <!-- Stats Module -->
      @if (briefing(); as b) {
        <section class="ed-stats">
          <div class="stat-module">
            <div class="stat-item">
              <span class="stat-value accent">{{ b.total_items ?? '-' }}</span>
              <span class="stat-label">Extraídas</span>
              <div class="stat-bar"><div class="stat-bar-fill accent-bg" [style.width.%]="100"></div></div>
            </div>
            <div class="stat-item">
              <span class="stat-value">{{ b.items_after_dedup ?? '-' }}</span>
              <span class="stat-label">Dedup</span>
              <div class="stat-bar"><div class="stat-bar-fill" [style.width.%]="barPercent(b.items_after_dedup, b.total_items)"></div></div>
            </div>
            <div class="stat-item">
              <span class="stat-value">{{ b.items_filtered ?? '-' }}</span>
              <span class="stat-label">Filtradas</span>
              <div class="stat-bar"><div class="stat-bar-fill" [style.width.%]="barPercent(b.items_filtered, b.total_items)"></div></div>
            </div>
            <div class="stat-item">
              <span class="stat-value forest">{{ b.trending_count ?? '-' }}</span>
              <span class="stat-label">Trending</span>
              <div class="stat-bar"><div class="stat-bar-fill forest-bg" [style.width.%]="barPercent(b.trending_count, b.items_filtered)"></div></div>
            </div>
            @if (b.duration_seconds) {
              <div class="stat-item span-2">
                <span class="stat-value">{{ b.duration_seconds }}s</span>
                <span class="stat-label">Duración del ciclo</span>
                <div class="stat-bar"><div class="stat-bar-fill" [style.width.%]="90"></div></div>
              </div>
            }
          </div>
        </section>
      }

      <!-- Topic Filters -->
      @if (topicCounts().length > 0) {
        <div class="ed-filters">
          <span class="mono filter-label">Filters:</span>
          @for (tc of topicCounts(); track tc.topic) {
            <button
              class="filter-chip"
              [class.active]="selectedTopic() === tc.topic"
              (click)="toggleTopic(tc.topic)"
            >{{ tc.topic }}/{{ tc.count }}</button>
          }
          @if (selectedTopic()) {
            <button class="filter-clear" (click)="selectedTopic.set(null)">limpiar</button>
          }
        </div>
      }

      <!-- Hero / Featured Analysis -->
      @if (heroItem(); as hero) {
        <section class="ed-section">
          <article class="ed-card hero-card">
            <div class="card-header" [attr.data-source]="hero.source">
              <span class="heading-xs">Featured Analysis</span>
              <span class="mono">SRC: {{ hero.source | uppercase }}</span>
            </div>
            <div class="card-body">
              <h2 class="hero-title">
                @if (hero.url) {
                  <a [href]="hero.url" target="_blank" rel="noopener">{{ hero.title }}</a>
                } @else {
                  {{ hero.title }}
                }
              </h2>
              @if (hero.summary) {
                <p class="hero-summary">{{ hero.summary }}</p>
              }
            </div>
            <div class="card-meta-grid">
              <div class="meta-cell border-right">
                <span class="mono text-muted meta-label">Score</span>
                <span class="mono meta-value">{{ hero.score ?? '-' }} pts</span>
              </div>
              <div class="meta-cell">
                <span class="mono text-muted meta-label">Byline</span>
                <span class="mono meta-value truncate">{{ hero.author ?? 'unknown' }}</span>
              </div>
            </div>
          </article>
        </section>
      }

      <!-- The Dispatch — News Grid -->
      @if (regularItems().length > 0) {
        <section class="ed-section">
          <div class="section-header">
            <h3 class="section-title">The Dispatch</h3>
            <div class="section-line"></div>
          </div>
          <div class="news-grid">
            @for (item of regularItems(); track item.id; let i = $index) {
              <app-news-item-card [item]="item" [class.span-2]="i % 5 === 4" />
            }
          </div>
        </section>
      }

      <!-- Loading / Error / Empty -->
      @if (loading()) {
        <div class="ed-loading">
          <span class="mono">Cargando noticias...</span>
        </div>
      }
      @if (error()) {
        <div class="ed-error">
          <span class="mono">{{ error() }}</span>
        </div>
      }
      @if (!loading() && !error() && items().length === 0) {
        <div class="ed-empty">
          <span class="mono">No hay noticias disponibles hoy. Ejecuta el pipeline primero.</span>
        </div>
      }
    </div>
  `,
  styles: [`
    :host { display: block; }

    /* === Typography helpers === */
    .heading-xs {
      font-family: var(--font-heading);
      font-weight: 700;
      font-size: 10px;
      text-transform: uppercase;
      letter-spacing: 0.12em;
    }
    .mono {
      font-family: var(--font-mono);
      font-weight: 500;
    }
    .text-muted { opacity: 0.6; }
    .truncate { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    .accent { color: var(--ed-terracotta); }
    .accent-bg { background: var(--ed-terracotta); }
    .forest { color: var(--ed-forest); }
    .forest-bg { background: var(--ed-forest); }

    /* === Layout === */
    .editorial {
      max-width: 900px;
      margin: 0 auto;
      padding-bottom: 48px;
    }

    /* === Header === */
    .ed-header {
      padding: 20px 0;
      border-bottom: 1px solid var(--text-primary);
      display: flex;
      flex-direction: column;
      gap: 12px;
    }
    .ed-header-top {
      display: flex;
      justify-content: space-between;
      align-items: center;
    }
    .vol-label { font-size: 10px; letter-spacing: 0.15em; text-transform: uppercase; }
    .ed-title {
      font-family: var(--font-heading);
      font-weight: 700;
      font-size: clamp(2rem, 5vw, 3rem);
      line-height: 0.95;
      letter-spacing: -0.03em;
      text-transform: uppercase;
      margin: 0;
      color: var(--text-primary);
    }
    .ed-header-meta {
      display: flex;
      justify-content: space-between;
      font-size: 9px;
      text-transform: uppercase;
    }

    .status-dot {
      display: inline-block;
      width: 6px;
      height: 6px;
      border-radius: 50%;
      background: var(--ed-status-color);
      margin-right: 4px;
      vertical-align: middle;
      animation: pulse-dot 2s ease-in-out infinite;
    }

    /* === Stats Module === */
    .ed-stats { padding: 16px 0; }
    .stat-module {
      background: var(--text-primary);
      color: var(--bg-base);
      padding: 20px;
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 20px 16px;
      border-radius: 2px;
      box-shadow: var(--ed-stat-shadow);
    }
    .stat-item { display: flex; flex-direction: column; }
    .stat-item.span-2 { grid-column: span 2; }
    .stat-value {
      font-family: var(--font-mono);
      font-size: 1.25rem;
      font-weight: 500;
    }
    .stat-label {
      font-size: 8px;
      text-transform: uppercase;
      letter-spacing: 0.12em;
      font-weight: 700;
      opacity: 0.7;
    }
    .stat-bar {
      width: 100%;
      height: 3px;
      background: rgba(255, 255, 255, 0.15);
      margin-top: 6px;
    }
    .stat-bar-fill {
      height: 100%;
      background: rgba(255, 255, 255, 0.7);
      transition: width 0.6s ease;
    }

    /* === Filters === */
    .ed-filters {
      display: flex;
      align-items: center;
      gap: 8px;
      padding: 12px 0;
      overflow-x: auto;
      scrollbar-width: none;
    }
    .ed-filters::-webkit-scrollbar { display: none; }
    .filter-label {
      font-size: 10px;
      font-weight: 700;
      text-transform: uppercase;
      margin-right: 4px;
      white-space: nowrap;
    }
    .filter-chip {
      font-family: var(--font-mono);
      font-size: 12px;
      padding: 4px 12px;
      border: 1px solid var(--text-primary);
      background: transparent;
      color: var(--text-primary);
      cursor: pointer;
      white-space: nowrap;
      transition: background 0.15s ease, color 0.15s ease;
    }
    .filter-chip:hover, .filter-chip.active {
      background: var(--text-primary);
      color: var(--bg-base);
    }
    .filter-clear {
      font-family: var(--font-mono);
      font-size: 11px;
      color: var(--ed-terracotta);
      background: none;
      border: none;
      cursor: pointer;
      text-decoration: underline;
      white-space: nowrap;
    }

    /* === Sections === */
    .ed-section { margin-bottom: 32px; }
    .section-header {
      display: flex;
      align-items: center;
      gap: 12px;
      margin-bottom: 16px;
    }
    .section-title {
      font-family: var(--font-heading);
      font-weight: 700;
      font-size: 1.125rem;
      text-transform: uppercase;
      margin: 0;
      white-space: nowrap;
      color: var(--text-primary);
    }
    .section-line {
      flex: 1;
      height: 1px;
      background: var(--text-primary);
      opacity: 0.2;
    }

    /* === Hero Card (inline, not using news-item-card) === */
    .ed-card {
      border: 1px solid var(--text-primary);
      background: var(--bg-surface);
      transition: transform 0.15s ease;
    }
    .ed-card:active { transform: scale(0.99); }

    .card-header {
      padding: 8px 12px;
      border-bottom: 1px solid var(--border);
      display: flex;
      justify-content: space-between;
      align-items: center;
      font-size: 10px;
      background: var(--bg-elevated);
    }
    .card-header[data-source="hackernews"] { background: var(--source-hackernews); color: white; }
    .card-header[data-source="arxiv"] { background: var(--source-arxiv); color: white; }
    .card-header[data-source="github"] { background: var(--source-github); color: white; }
    .card-header[data-source="reddit"] { background: var(--source-reddit); color: white; }
    .card-header[data-source="rss"] { background: var(--source-rss); color: #1A1A1A; }
    .card-header[data-source="huggingface"] { background: var(--source-huggingface); color: #1A1A1A; }

    .card-body { padding: 16px; }

    .card-meta-grid {
      display: grid;
      grid-template-columns: 1fr 1fr;
      border-top: 1px solid var(--border);
    }
    .meta-cell { padding: 10px 12px; display: flex; flex-direction: column; }
    .meta-cell.border-right { border-right: 1px solid var(--border); }
    .meta-label { font-size: 9px; text-transform: uppercase; }
    .meta-value { font-size: 0.9rem; }

    .hero-card { margin-bottom: 24px; }
    .hero-title {
      font-family: var(--font-heading);
      font-weight: 700;
      font-size: clamp(1.25rem, 3vw, 1.75rem);
      line-height: 1.15;
      margin: 0 0 12px;
      color: var(--text-primary);
    }
    .hero-title a {
      color: var(--text-primary);
      text-decoration: none;
    }
    .hero-title a:hover { text-decoration: underline; }
    .hero-summary {
      font-size: 0.9rem;
      line-height: 1.6;
      color: var(--text-secondary);
      margin: 0;
    }

    /* === News Grid === */
    .news-grid {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 16px;
    }
    .span-2 { grid-column: span 2; }

    /* === Loading / Error / Empty === */
    .ed-loading, .ed-error, .ed-empty {
      padding: 48px;
      text-align: center;
      font-size: var(--text-base);
      border: 1px solid var(--border);
    }
    .ed-error { color: var(--error); }
    .ed-empty { color: var(--text-muted); }

    /* === Mobile === */
    @media (max-width: 640px) {
      .news-grid { grid-template-columns: 1fr; }
      .span-2 { grid-column: span 1; }
      .stat-module { grid-template-columns: repeat(2, 1fr); }
      .stat-item.span-2 { grid-column: span 2; }
      .ed-title { font-size: 2rem; }
    }
  `],
})
export class DashboardPage implements OnInit {
  private newsService = inject(NewsService);

  items = signal<NewsItem[]>([]);
  briefing = signal<Briefing | null>(null);
  loading = signal(true);
  error = signal<string | null>(null);
  selectedTopic = signal<string | null>(null);

  todayFormatted = computed(() => {
    const d = new Date();
    return d.toLocaleDateString('es-ES', { month: 'short', year: 'numeric' }).toUpperCase();
  });

  topicCounts = computed(() => {
    const counts = new Map<string, number>();
    for (const item of this.items()) {
      const topic = item.topic || 'sin tema';
      counts.set(topic, (counts.get(topic) || 0) + 1);
    }
    return Array.from(counts.entries())
      .map(([topic, count]) => ({ topic, count }))
      .sort((a, b) => b.count - a.count);
  });

  filteredItems = computed(() => {
    const topic = this.selectedTopic();
    if (!topic) return this.items();
    return this.items().filter(item => (item.topic || 'sin tema') === topic);
  });

  heroItem = computed(() => {
    const items = this.filteredItems();
    if (items.length === 0) return null;
    const trending = items.filter(i => i.trending);
    if (trending.length === 0) return items[0];
    return trending.reduce((best, item) =>
      (item.score ?? 0) > (best.score ?? 0) ? item : best, trending[0]);
  });

  regularItems = computed(() => {
    const hero = this.heroItem();
    if (!hero) return this.filteredItems();
    return this.filteredItems().filter(i => i.id !== hero.id);
  });

  barPercent(value: number | null | undefined, total: number | null | undefined): number {
    if (!value || !total || total === 0) return 0;
    return Math.min(100, Math.round((value / total) * 100));
  }

  toggleTopic(topic: string) {
    this.selectedTopic.set(this.selectedTopic() === topic ? null : topic);
  }

  private loadTodayItems() {
    this.newsService.getTodayItems().subscribe({
      next: (res) => {
        this.items.set(res.items);
        this.loading.set(false);
      },
      error: () => {
        this.error.set('Error al cargar noticias. Verifica que el API esté disponible.');
        this.loading.set(false);
      },
    });
  }

  ngOnInit() {
    const today = new Date().toISOString().slice(0, 10);

    this.newsService.getBriefing(today).subscribe({
      next: (briefing) => {
        this.briefing.set(briefing);
        if (briefing.items && briefing.items.length > 0) {
          this.items.set(briefing.items);
          this.loading.set(false);
        } else {
          this.loadTodayItems();
        }
      },
      error: () => this.loadTodayItems(),
    });
  }
}

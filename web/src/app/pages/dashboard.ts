import { Component, OnInit, inject, signal, computed } from '@angular/core';
import { CommonModule, DatePipe } from '@angular/common';
import { NewsService } from '../services/news.service';
import { NewsItem } from '../models/news-item';
import { Briefing } from '../models/news-item';

@Component({
  selector: 'app-dashboard',
  imports: [CommonModule, DatePipe],
  template: `
    <div class="dashboard">
      @if (loading()) {
        <div class="loading">Cargando noticias de hoy...</div>
      }

      @if (error()) {
        <div class="error">{{ error() }}</div>
      }

      @if (!loading() && !error()) {
        <!-- Stats bar -->
        @if (briefing()) {
          <div class="stats-bar">
            <div class="stat">
              <span class="stat-value">{{ briefing()!.total_items ?? '-' }}</span>
              <span class="stat-label">Extraidas</span>
            </div>
            <div class="stat">
              <span class="stat-value">{{ briefing()!.items_after_dedup ?? '-' }}</span>
              <span class="stat-label">Dedup</span>
            </div>
            <div class="stat">
              <span class="stat-value">{{ briefing()!.items_filtered ?? '-' }}</span>
              <span class="stat-label">Filtradas</span>
            </div>
            <div class="stat">
              <span class="stat-value">{{ briefing()!.trending_count ?? '-' }}</span>
              <span class="stat-label">Trending</span>
            </div>
            @if (briefing()!.duration_seconds) {
              <div class="stat">
                <span class="stat-value">{{ briefing()!.duration_seconds }}s</span>
                <span class="stat-label">Duracion</span>
              </div>
            }
          </div>
        }

        <!-- Topic distribution -->
        @if (topicCounts().length > 0) {
          <div class="topic-summary">
            <h3>Distribucion por tema</h3>
            <div class="topic-chips">
              @for (tc of topicCounts(); track tc.topic) {
                <span class="topic-chip">
                  {{ tc.topic }} <strong>{{ tc.count }}</strong>
                </span>
              }
            </div>
          </div>
        }

        @if (items().length === 0) {
          <div class="empty">No hay noticias disponibles hoy. Ejecuta el pipeline primero.</div>
        }

        @if (items().length > 0) {
          <div class="count-label">{{ items().length }} noticias hoy</div>
        }

        <!-- News list -->
        <div class="news-list">
          @for (item of items(); track item.id) {
            <article class="news-item">
              <div class="item-header">
                <span class="source-badge" [attr.data-source]="item.source">{{ item.source }}</span>
                @if (item.score) {
                  <span class="score">{{ item.score }} pts</span>
                }
                @if (item.topic) {
                  <span class="topic-badge">{{ item.topic }}</span>
                }
                @if (item.trending) {
                  <span class="trending">trending</span>
                }
              </div>
              <h2>
                @if (item.url) {
                  <a [href]="item.url" target="_blank" rel="noopener">{{ item.title }}</a>
                } @else {
                  {{ item.title }}
                }
              </h2>
              @if (item.summary) {
                <p class="summary">{{ item.summary }}</p>
              }
              <div class="item-meta">
                @if (item.author) {
                  <span>{{ item.author }}</span>
                }
                @if (item.published_at) {
                  <span>{{ item.published_at | date:'short' }}</span>
                }
              </div>
            </article>
          }
        </div>
      }
    </div>
  `,
  styles: [`
    :host { display: block; }
    .loading, .error, .empty {
      padding: 24px;
      text-align: center;
      border-radius: 8px;
      margin: 20px 0;
    }
    .loading { background: #f1f5f9; color: #475569; }
    .error { background: #fef2f2; color: #dc2626; }
    .empty { background: #f8fafc; color: #64748b; }

    .stats-bar {
      display: flex;
      gap: 16px;
      padding: 16px;
      background: #f8fafc;
      border: 1px solid #e2e8f0;
      border-radius: 8px;
      margin-bottom: 16px;
      flex-wrap: wrap;
    }
    .stat {
      display: flex;
      flex-direction: column;
      align-items: center;
      min-width: 60px;
    }
    .stat-value {
      font-size: 1.3rem;
      font-weight: 700;
      color: #1e293b;
    }
    .stat-label {
      font-size: 0.75rem;
      color: #64748b;
      text-transform: uppercase;
      letter-spacing: 0.5px;
    }

    .topic-summary {
      margin-bottom: 16px;
    }
    .topic-summary h3 {
      margin: 0 0 8px;
      font-size: 0.9rem;
      color: #475569;
      font-weight: 600;
    }
    .topic-chips {
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
    }
    .topic-chip {
      font-size: 0.78rem;
      padding: 3px 10px;
      border-radius: 12px;
      background: #dbeafe;
      color: #1e40af;
    }
    .topic-chip strong {
      margin-left: 4px;
    }

    .count-label {
      color: #64748b;
      margin-bottom: 12px;
      font-size: 0.9rem;
    }

    .news-list { display: flex; flex-direction: column; gap: 12px; }
    .news-item {
      border: 1px solid #e2e8f0;
      border-radius: 8px;
      padding: 16px;
      transition: box-shadow 0.15s;
    }
    .news-item:hover { box-shadow: 0 2px 8px rgba(0,0,0,0.08); }
    .item-header {
      display: flex;
      gap: 8px;
      align-items: center;
      margin-bottom: 8px;
      flex-wrap: wrap;
    }
    .source-badge {
      font-size: 0.75rem;
      padding: 2px 8px;
      border-radius: 4px;
      font-weight: 600;
      background: #e2e8f0;
      color: #475569;
      text-transform: uppercase;
    }
    .source-badge[data-source="hackernews"] { background: #ff6600; color: white; }
    .source-badge[data-source="arxiv"] { background: #b31b1b; color: white; }
    .source-badge[data-source="reddit"] { background: #ff4500; color: white; }
    .source-badge[data-source="rss"] { background: #f59e0b; color: white; }
    .score { font-size: 0.8rem; color: #64748b; font-weight: 500; }
    .topic-badge {
      font-size: 0.7rem;
      padding: 2px 6px;
      border-radius: 3px;
      background: #dbeafe;
      color: #1e40af;
    }
    .trending {
      font-size: 0.7rem;
      padding: 2px 6px;
      border-radius: 3px;
      background: #fef3c7;
      color: #b45309;
      font-weight: 600;
    }
    h2 {
      margin: 0 0 8px;
      font-size: 1.05rem;
      line-height: 1.4;
    }
    h2 a { color: #1e293b; text-decoration: none; }
    h2 a:hover { color: #2563eb; text-decoration: underline; }
    .summary { margin: 0 0 8px; color: #475569; font-size: 0.9rem; line-height: 1.5; }
    .item-meta {
      display: flex;
      gap: 12px;
      color: #94a3b8;
      font-size: 0.8rem;
    }
  `],
})
export class DashboardPage implements OnInit {
  private newsService = inject(NewsService);

  items = signal<NewsItem[]>([]);
  briefing = signal<Briefing | null>(null);
  loading = signal(true);
  error = signal<string | null>(null);

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

  ngOnInit() {
    const today = new Date().toISOString().slice(0, 10);

    this.newsService.getBriefing(today).subscribe({
      next: (briefing) => {
        this.briefing.set(briefing);
        this.items.set(briefing.items || []);
        this.loading.set(false);
      },
      error: () => {
        // Fallback to today items if briefing not available
        this.newsService.getTodayItems().subscribe({
          next: (items) => {
            this.items.set(items);
            this.loading.set(false);
          },
          error: (err) => {
            this.error.set('Error al cargar noticias. Verifica que el API este disponible.');
            this.loading.set(false);
            console.error('Failed to load news:', err);
          },
        });
      },
    });
  }
}

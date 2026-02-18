import { Component, OnInit, inject, signal, computed } from '@angular/core';
import { CommonModule } from '@angular/common';
import { NewsService } from '../services/news.service';
import { NewsItem } from '../models/news-item';
import { Briefing } from '../models/news-item';
import { NewsItemCard } from '../components/news-item-card';

@Component({
  selector: 'app-dashboard',
  imports: [CommonModule, NewsItemCard],
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
                <button
                  class="topic-chip"
                  [class.active]="selectedTopic() === tc.topic"
                  (click)="toggleTopic(tc.topic)"
                >
                  {{ tc.topic }} <strong>{{ tc.count }}</strong>
                </button>
              }
              @if (selectedTopic()) {
                <button class="clear-filter" (click)="toggleTopic(selectedTopic()!)">limpiar filtro</button>
              }
            </div>
          </div>
        }

        @if (items().length === 0) {
          <div class="empty">No hay noticias disponibles hoy. Ejecuta el pipeline primero.</div>
        }

        @if (filteredItems().length > 0) {
          <div class="count-label">{{ filteredItems().length }} noticias hoy</div>
        }

        <!-- News list -->
        <div class="news-list">
          @for (item of filteredItems(); track item.id) {
            <app-news-item-card [item]="item" />
          }
        </div>
      }
    </div>
  `,
  styles: [`
    :host { display: block; }
    .loading, .error, .empty {
      padding: 28px;
      text-align: center;
      border-radius: 14px;
      margin: 24px 0;
      font-size: 0.9375rem;
    }
    .loading { background: #f5f5f7; color: #6e6e73; }
    .error { background: #fff2f2; color: #d70015; }
    .empty { background: #f5f5f7; color: #86868b; }

    .stats-bar {
      display: flex;
      gap: 0;
      padding: 0;
      background: #ffffff;
      border-radius: 14px;
      margin-bottom: 20px;
      box-shadow: 0 1px 2px rgba(0, 0, 0, 0.04), 0 1px 4px rgba(0, 0, 0, 0.06);
      overflow: hidden;
    }
    .stat {
      display: flex;
      flex-direction: column;
      align-items: center;
      flex: 1;
      padding: 16px 12px;
      border-right: 1px solid #f5f5f7;
    }
    .stat:last-child { border-right: none; }
    .stat-value {
      font-size: 1.5rem;
      font-weight: 700;
      color: #1d1d1f;
      letter-spacing: -0.02em;
      font-variant-numeric: tabular-nums;
    }
    .stat-label {
      font-size: 0.6875rem;
      color: #86868b;
      text-transform: uppercase;
      letter-spacing: 0.06em;
      margin-top: 2px;
      font-weight: 500;
    }

    .topic-summary {
      margin-bottom: 20px;
    }
    .topic-summary h3 {
      margin: 0 0 10px;
      font-size: 0.8125rem;
      color: #86868b;
      font-weight: 500;
      text-transform: uppercase;
      letter-spacing: 0.06em;
    }
    .topic-chips {
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
      align-items: center;
    }
    .topic-chip {
      font-size: 0.8125rem;
      padding: 5px 14px;
      border-radius: 980px;
      background: #f5f5f7;
      color: #1d1d1f;
      border: none;
      cursor: pointer;
      transition: all 0.2s;
      font-weight: 400;
    }
    .topic-chip:hover { background: #e8e8ed; }
    .topic-chip.active {
      background: #1d1d1f;
      color: #f5f5f7;
    }
    .topic-chip strong {
      margin-left: 4px;
      font-weight: 600;
      color: #86868b;
    }
    .topic-chip.active strong { color: rgba(255, 255, 255, 0.64); }
    .clear-filter {
      background: none;
      border: none;
      color: #0071e3;
      font-size: 0.8125rem;
      cursor: pointer;
      margin-left: 8px;
      font-weight: 500;
    }
    .clear-filter:hover { text-decoration: underline; }

    .count-label {
      color: #86868b;
      margin-bottom: 14px;
      font-size: 0.875rem;
    }

    .news-list { display: flex; flex-direction: column; gap: 10px; }

    @media (max-width: 640px) {
      .stat { padding: 12px 8px; }
      .stat-value { font-size: 1.2rem; }
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

  toggleTopic(topic: string) {
    this.selectedTopic.set(this.selectedTopic() === topic ? null : topic);
  }

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

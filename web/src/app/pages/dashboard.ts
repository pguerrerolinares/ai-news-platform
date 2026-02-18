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
      align-items: center;
    }
    .topic-chip {
      font-size: 0.78rem;
      padding: 3px 10px;
      border-radius: 12px;
      background: #dbeafe;
      color: #1e40af;
      border: none;
      cursor: pointer;
      transition: all 0.15s;
    }
    .topic-chip:hover { background: #bfdbfe; }
    .topic-chip.active { background: #2563eb; color: white; }
    .topic-chip strong { margin-left: 4px; }
    .clear-filter {
      background: none;
      border: none;
      color: #2563eb;
      font-size: 0.85rem;
      cursor: pointer;
      margin-left: 8px;
      text-decoration: underline;
    }

    .count-label {
      color: #64748b;
      margin-bottom: 12px;
      font-size: 0.9rem;
    }

    .news-list { display: flex; flex-direction: column; gap: 12px; }
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

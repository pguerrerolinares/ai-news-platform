import { Component, inject, signal, computed, effect } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { NewsService } from '../services/news.service';
import { NewsItem } from '../models/news-item';
import { Briefing } from '../models/news-item';
import { NewsItemCard } from '../components/news-item-card';

@Component({
  selector: 'app-archive',
  imports: [CommonModule, FormsModule, NewsItemCard],
  template: `
    <div class="archive">
      <div class="controls">
        <label for="archive-date">Fecha</label>
        <input
          id="archive-date"
          type="date"
          [(ngModel)]="selectedDate"
          (ngModelChange)="onDateChange()"
          [max]="todayStr"
        />
        <select [ngModel]="selectedTopic()" (ngModelChange)="selectedTopic.set($event)" class="topic-select">
          <option value="">Todos los temas</option>
          @for (tc of topicCounts(); track tc.topic) {
            <option [value]="tc.topic">{{ tc.topic }} ({{ tc.count }})</option>
          }
        </select>
      </div>

      @if (loading()) {
        <div class="loading">Cargando noticias...</div>
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

        @if (!loading() && items().length === 0 && !error()) {
          <div class="empty">No hay noticias para esta fecha.</div>
        }

        @if (filteredItems().length > 0) {
          <div class="count-label">{{ filteredItems().length }} noticias del {{ selectedDate }}</div>
        }

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

    .controls {
      display: flex;
      align-items: center;
      gap: 12px;
      margin-bottom: 24px;
    }
    .controls label {
      font-size: 0.8125rem;
      font-weight: 500;
      color: #86868b;
    }
    .controls input[type="date"] {
      padding: 8px 14px;
      border: 1px solid #d2d2d7;
      border-radius: 8px;
      font-size: 0.875rem;
      outline: none;
      color: #1d1d1f;
      transition: border-color 0.2s, box-shadow 0.2s;
    }
    .controls input[type="date"]:focus {
      border-color: #0071e3;
      box-shadow: 0 0 0 4px rgba(0, 113, 227, 0.12);
    }

    .topic-select {
      padding: 8px 14px;
      border: 1px solid #d2d2d7;
      border-radius: 8px;
      font-size: 0.875rem;
      outline: none;
      color: #1d1d1f;
      transition: border-color 0.2s, box-shadow 0.2s;
    }
    .topic-select:focus {
      border-color: #0071e3;
      box-shadow: 0 0 0 4px rgba(0, 113, 227, 0.12);
    }

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

    .topic-summary { margin-bottom: 20px; }
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
    }
    .topic-chip {
      font-size: 0.8125rem;
      padding: 5px 14px;
      border-radius: 980px;
      background: #f5f5f7;
      color: #1d1d1f;
    }
    .topic-chip strong { margin-left: 4px; color: #86868b; }

    .count-label {
      color: #86868b;
      margin-bottom: 14px;
      font-size: 0.875rem;
    }

    .news-list { display: flex; flex-direction: column; gap: 10px; }

    @media (max-width: 640px) {
      .controls { flex-wrap: wrap; }
      .stat { padding: 12px 8px; }
      .stat-value { font-size: 1.2rem; }
    }
  `],
})
export class ArchivePage {
  private newsService = inject(NewsService);

  todayStr = new Date().toISOString().slice(0, 10);
  selectedDate = this.todayStr;
  selectedTopic = signal('');

  items = signal<NewsItem[]>([]);
  briefing = signal<Briefing | null>(null);
  loading = signal(false);
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

  filteredItems = computed(() => {
    const topic = this.selectedTopic();
    if (!topic) return this.items();
    return this.items().filter(item => (item.topic || 'sin tema') === topic);
  });

  onDateChange() {
    if (!this.selectedDate) return;
    this.selectedTopic.set('');
    this.loadBriefing(this.selectedDate);
  }

  private loadBriefing(date: string) {
    this.loading.set(true);
    this.error.set(null);
    this.briefing.set(null);
    this.items.set([]);

    this.newsService.getBriefing(date).subscribe({
      next: (briefing) => {
        this.briefing.set(briefing);
        this.items.set(briefing.items || []);
        this.loading.set(false);
      },
      error: (err) => {
        if (err.status === 404) {
          this.error.set('No hay briefing para esta fecha.');
        } else {
          this.error.set('Error al cargar el archivo. Intenta de nuevo.');
        }
        this.loading.set(false);
        console.error('Failed to load archive:', err);
      },
    });
  }
}

import { Component, inject, signal, computed } from '@angular/core';
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
        <select [(ngModel)]="selectedTopic" (ngModelChange)="0" class="topic-select">
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
      margin-bottom: 20px;
    }
    .controls label {
      font-size: 0.9rem;
      font-weight: 600;
      color: #475569;
    }
    .controls input[type="date"] {
      padding: 8px 12px;
      border: 1px solid #e2e8f0;
      border-radius: 6px;
      font-size: 0.9rem;
      outline: none;
    }
    .controls input[type="date"]:focus {
      border-color: #2563eb;
      box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.1);
    }

    .topic-select {
      padding: 8px 12px;
      border: 1px solid #e2e8f0;
      border-radius: 6px;
      font-size: 0.9rem;
      outline: none;
    }
    .topic-select:focus {
      border-color: #2563eb;
      box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.1);
    }

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

    .topic-summary { margin-bottom: 16px; }
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
    .topic-chip strong { margin-left: 4px; }

    .count-label {
      color: #64748b;
      margin-bottom: 12px;
      font-size: 0.9rem;
    }

    .news-list { display: flex; flex-direction: column; gap: 12px; }
  `],
})
export class ArchivePage {
  private newsService = inject(NewsService);

  todayStr = new Date().toISOString().slice(0, 10);
  selectedDate = this.todayStr;
  selectedTopic = '';

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
    const topic = this.selectedTopic;
    if (!topic) return this.items();
    return this.items().filter(item => (item.topic || 'sin tema') === topic);
  });

  onDateChange() {
    if (!this.selectedDate) return;
    this.selectedTopic = '';
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

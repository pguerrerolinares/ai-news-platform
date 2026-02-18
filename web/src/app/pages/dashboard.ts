import { Component, OnInit, inject, signal, computed } from '@angular/core';
import { CommonModule } from '@angular/common';
import { MatCardModule } from '@angular/material/card';
import { MatChipsModule, MatChipListboxChange } from '@angular/material/chips';
import { MatProgressBarModule } from '@angular/material/progress-bar';
import { MatButtonModule } from '@angular/material/button';
import { NewsService } from '../services/news.service';
import { NewsItem } from '../models/news-item';
import { Briefing } from '../models/news-item';
import { NewsItemCard } from '../components/news-item-card';

@Component({
  selector: 'app-dashboard',
  imports: [CommonModule, NewsItemCard, MatCardModule, MatChipsModule, MatProgressBarModule, MatButtonModule],
  template: `
    <div class="dashboard">
      @if (loading()) {
        <mat-progress-bar mode="indeterminate" class="loading-bar"></mat-progress-bar>
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
            <div class="topic-chips-row">
              <mat-chip-listbox
                [value]="selectedTopic()"
                (change)="onChipChange($event)"
                class="topic-chips"
              >
                @for (tc of topicCounts(); track tc.topic) {
                  <mat-chip-option class="topic-chip" [value]="tc.topic">
                    {{ tc.topic }} <strong>{{ tc.count }}</strong>
                  </mat-chip-option>
                }
              </mat-chip-listbox>
              @if (selectedTopic()) {
                <button mat-button class="clear-filter" (click)="clearFilter()">limpiar filtro</button>
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
          @for (item of filteredItems(); track item.id; let i = $index) {
            <app-news-item-card [item]="item" class="fade-in" [style.animation-delay]="i * 50 + 'ms'" />
          }
        </div>
      }
    </div>
  `,
  styles: [`
    :host { display: block; }

    .loading-bar {
      margin-bottom: 24px;
    }

    .error, .empty {
      padding: 28px;
      text-align: center;
      border-radius: 12px;
      margin: 24px 0;
      font-size: 0.9375rem;
    }
    .error {
      background: var(--error-subtle);
      color: #f87171;
      border: 1px solid rgba(239,68,68,0.15);
    }
    .empty {
      background: var(--bg-surface);
      color: var(--text-tertiary);
      border: 1px solid var(--border);
    }

    .topic-summary {
      margin-bottom: 20px;
    }
    .topic-summary h3 {
      margin: 0 0 10px;
      font-size: 0.8125rem;
      color: var(--text-tertiary);
      font-weight: 500;
      text-transform: uppercase;
      letter-spacing: 0.06em;
    }
    .topic-chips-row {
      display: flex;
      align-items: center;
      gap: 8px;
      flex-wrap: wrap;
    }
    .topic-chips {
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
    }
    .topic-chip {
      --mdc-chip-elevated-container-color: var(--bg-surface);
      --mdc-chip-label-text-color: var(--text-secondary);
      --mdc-chip-outline-color: var(--border);
      --mdc-chip-label-text-font: var(--font-body);
      --mdc-chip-label-text-size: 0.8125rem;
      border: 1px solid var(--border);
      border-radius: 980px;
    }
    .topic-chip.mat-mdc-chip-selected {
      --mdc-chip-elevated-selected-container-color: #fff;
      --mdc-chip-selected-label-text-color: #09090b;
      border-color: transparent;
    }
    :host-context(html:not(.dark)) .topic-chip.mat-mdc-chip-selected {
      --mdc-chip-elevated-selected-container-color: #09090b;
      --mdc-chip-selected-label-text-color: #fff;
    }
    .topic-chip strong {
      margin-left: 4px;
      font-weight: 600;
      color: var(--text-tertiary);
    }
    .topic-chip.mat-mdc-chip-selected strong { color: inherit; opacity: 0.6; }
    .clear-filter {
      color: var(--accent);
      font-size: 0.8125rem;
      font-weight: 500;
      --mdc-text-button-label-text-color: var(--accent);
    }

    .count-label {
      color: var(--text-tertiary);
      margin-bottom: 14px;
      font-size: 0.875rem;
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

  onChipChange(event: MatChipListboxChange) {
    this.selectedTopic.set(event.value || null);
  }

  clearFilter() {
    this.selectedTopic.set(null);
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

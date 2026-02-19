import { Component, OnInit, inject, signal, computed } from '@angular/core';
import { CommonModule } from '@angular/common';
import { MatCardModule } from '@angular/material/card';
import { MatChipsModule, MatChipListboxChange } from '@angular/material/chips';
import { MatProgressBarModule } from '@angular/material/progress-bar';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { NewsService } from '../services/news.service';
import { NewsItem } from '../models/news-item';
import { Briefing } from '../models/news-item';
import { NewsItemCard } from '../components/news-item-card';

@Component({
  selector: 'app-dashboard',
  imports: [CommonModule, NewsItemCard, MatCardModule, MatChipsModule, MatProgressBarModule, MatButtonModule, MatIconModule],
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
              <mat-icon class="stat-icon">cloud_download</mat-icon>
              <span class="stat-value">{{ briefing()!.total_items ?? '-' }}</span>
              <span class="stat-label">Extraídas</span>
            </div>
            <div class="stat">
              <mat-icon class="stat-icon">filter_list</mat-icon>
              <span class="stat-value">{{ briefing()!.items_after_dedup ?? '-' }}</span>
              <span class="stat-label">Dedup</span>
            </div>
            <div class="stat">
              <mat-icon class="stat-icon">done_all</mat-icon>
              <span class="stat-value">{{ briefing()!.items_filtered ?? '-' }}</span>
              <span class="stat-label">Filtradas</span>
            </div>
            <div class="stat">
              <mat-icon class="stat-icon">trending_up</mat-icon>
              <span class="stat-value">{{ briefing()!.trending_count ?? '-' }}</span>
              <span class="stat-label">Trending</span>
            </div>
            @if (briefing()!.duration_seconds) {
              <div class="stat">
                <mat-icon class="stat-icon">timer</mat-icon>
                <span class="stat-value">{{ briefing()!.duration_seconds }}s</span>
                <span class="stat-label">Duración</span>
              </div>
            }
          </div>
        }

        <!-- Topic distribution -->
        @if (topicCounts().length > 0) {
          <div class="topic-summary">
            <h3>Distribución por tema</h3>
            <div class="topic-chips-row">
              <mat-chip-listbox
                [value]="selectedTopic()"
                (change)="onChipChange($event)"
                class="topic-chips"
              >
                @for (tc of topicCounts(); track tc.topic) {
                  <mat-chip-option class="topic-chip" [value]="tc.topic" [attr.data-topic]="tc.topic">
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

        <!-- Hero card -->
        @if (heroItem(); as hero) {
          <app-news-item-card [item]="hero" [hero]="true" class="fade-in hero-entry" />
        }

        <!-- News list -->
        <div class="news-list">
          @for (item of regularItems(); track item.id; let i = $index) {
            <app-news-item-card [item]="item" class="fade-in" [style.animation-delay]="i * 50 + 'ms'" />
          }
        </div>
      }
    </div>
  `,
  styles: [`
    :host { display: block; }

    .loading-bar { margin-bottom: 24px; }

    .error, .empty {
      padding: 32px;
      text-align: center;
      border-radius: 14px;
      margin: 24px 0;
      font-size: var(--text-base);
    }
    .error {
      background: var(--error-subtle);
      color: #f87171;
      border: 1px solid rgba(239, 68, 68, 0.15);
    }
    .empty {
      background: var(--bg-elevated);
      color: var(--text-muted);
      border: 1px solid var(--border);
    }

    .topic-summary { margin-bottom: 24px; }
    .topic-summary h3 {
      margin: 0 0 12px;
      font-size: var(--text-xs);
      color: var(--text-muted);
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: var(--tracking-wider);
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
      --mdc-chip-elevated-container-color: var(--bg-elevated);
      --mdc-chip-label-text-color: var(--text-secondary);
      --mdc-chip-outline-color: var(--border);
      --mdc-chip-label-text-font: var(--font-body);
      --mdc-chip-label-text-size: var(--text-sm);
      border: 1px solid var(--border);
      border-radius: 980px;
      transition: border-color 0.15s ease, background 0.15s ease;
    }

    .topic-chip.mat-mdc-chip-selected {
      --mdc-chip-elevated-selected-container-color: var(--accent);
      --mdc-chip-selected-label-text-color: #fff;
      border-color: transparent;
    }

    :host-context(html:not(.dark)) .topic-chip.mat-mdc-chip-selected {
      --mdc-chip-elevated-selected-container-color: var(--accent);
      --mdc-chip-selected-label-text-color: #fff;
    }

    .topic-chip strong {
      margin-left: 4px;
      font-weight: 600;
      color: var(--text-muted);
    }
    .topic-chip.mat-mdc-chip-selected strong { color: inherit; opacity: 0.7; }

    /* Topic color tints */
    .topic-chip[data-topic="modelos"] { border-color: color-mix(in srgb, var(--topic-modelos) 30%, transparent); color: var(--topic-modelos); }
    .topic-chip[data-topic="herramientas"] { border-color: color-mix(in srgb, var(--topic-herramientas) 30%, transparent); color: var(--topic-herramientas); }
    .topic-chip[data-topic="papers"] { border-color: color-mix(in srgb, var(--topic-papers) 30%, transparent); color: var(--topic-papers); }
    .topic-chip[data-topic="open_source"] { border-color: color-mix(in srgb, var(--topic-open_source) 30%, transparent); color: var(--topic-open_source); }
    .topic-chip[data-topic="productos"] { border-color: color-mix(in srgb, var(--topic-productos) 30%, transparent); color: var(--topic-productos); }
    .topic-chip[data-topic="agentes"] { border-color: color-mix(in srgb, var(--topic-agentes) 30%, transparent); color: var(--topic-agentes); }
    .topic-chip[data-topic="regulacion"] { border-color: color-mix(in srgb, var(--topic-regulacion) 30%, transparent); color: var(--topic-regulacion); }

    .clear-filter {
      color: var(--accent);
      font-size: var(--text-sm);
      font-weight: 500;
      --mdc-text-button-label-text-color: var(--accent);
    }

    .count-label {
      color: var(--text-muted);
      margin-bottom: 16px;
      font-size: 0.875rem;
      font-weight: 500;
    }

    .hero-entry { margin-bottom: 14px; }

    .news-list {
      display: flex;
      flex-direction: column;
      gap: 14px;
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

  heroItem = computed(() => {
    const items = this.filteredItems();
    if (items.length === 0) return null;
    const trending = items.filter(i => i.trending);
    if (trending.length === 0) return null;
    return trending.reduce((best, item) =>
      (item.score ?? 0) > (best.score ?? 0) ? item : best, trending[0]);
  });

  regularItems = computed(() => {
    const hero = this.heroItem();
    if (!hero) return this.filteredItems();
    return this.filteredItems().filter(i => i.id !== hero.id);
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

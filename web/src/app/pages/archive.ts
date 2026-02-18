import { Component, inject, signal, computed } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { MatCardModule } from '@angular/material/card';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';
import { MatChipsModule } from '@angular/material/chips';
import { MatProgressBarModule } from '@angular/material/progress-bar';
import { NewsService } from '../services/news.service';
import { NewsItem } from '../models/news-item';
import { Briefing } from '../models/news-item';
import { NewsItemCard } from '../components/news-item-card';

@Component({
  selector: 'app-archive',
  imports: [CommonModule, FormsModule, NewsItemCard, MatCardModule, MatFormFieldModule, MatInputModule, MatSelectModule, MatChipsModule, MatProgressBarModule],
  template: `
    <div class="archive">
      <div class="controls">
        <mat-form-field appearance="outline" class="control-field">
          <mat-label>Fecha</mat-label>
          <input
            matInput
            id="archive-date"
            type="date"
            [(ngModel)]="selectedDate"
            (ngModelChange)="onDateChange()"
            [max]="todayStr"
          />
        </mat-form-field>
        <mat-form-field appearance="outline" class="control-field">
          <mat-label>Tema</mat-label>
          <mat-select [ngModel]="selectedTopic()" (ngModelChange)="selectedTopic.set($event)">
            <mat-option value="">Todos los temas</mat-option>
            @for (tc of topicCounts(); track tc.topic) {
              <mat-option [value]="tc.topic">{{ tc.topic }} ({{ tc.count }})</mat-option>
            }
          </mat-select>
        </mat-form-field>
      </div>

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
          @for (item of filteredItems(); track item.id; let i = $index) {
            <app-news-item-card [item]="item" class="fade-in" [style.animation-delay]="i * 50 + 'ms'" />
          }
        </div>
      }
    </div>
  `,
  styles: [`
    :host { display: block; }

    .controls {
      display: flex;
      align-items: flex-start;
      gap: 12px;
      margin-bottom: 8px;
    }
    .control-field {
      min-width: 180px;
    }

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

    .topic-summary { margin-bottom: 20px; }
    .topic-summary h3 {
      margin: 0 0 10px;
      font-size: 0.8125rem;
      color: var(--text-tertiary);
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
      background: var(--bg-surface);
      border: 1px solid var(--border);
      color: var(--text-secondary);
    }
    .topic-chip strong { margin-left: 4px; color: var(--text-tertiary); }

    .count-label {
      color: var(--text-tertiary);
      margin-bottom: 14px;
      font-size: 0.875rem;
    }

    .news-list { display: flex; flex-direction: column; gap: 12px; }

    @media (max-width: 640px) {
      .controls { flex-wrap: wrap; }
      .control-field { width: 100%; min-width: 0; }
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

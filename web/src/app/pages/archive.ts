import { Component, inject, signal, computed, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { MatCardModule } from '@angular/material/card';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';
import { MatDatepickerModule } from '@angular/material/datepicker';
import { MatNativeDateModule } from '@angular/material/core';
import { MatChipsModule } from '@angular/material/chips';
import { MatProgressBarModule } from '@angular/material/progress-bar';
import { NewsService } from '../services/news.service';
import { NewsItem } from '../models/news-item';
import { Briefing } from '../models/news-item';
import { NewsItemCard } from '../components/news-item-card';

@Component({
  selector: 'app-archive',
  imports: [CommonModule, FormsModule, NewsItemCard, MatCardModule, MatFormFieldModule, MatInputModule, MatSelectModule, MatDatepickerModule, MatNativeDateModule, MatChipsModule, MatProgressBarModule],
  template: `
    <div class="archive">
      <div class="controls">
        <mat-form-field appearance="outline" class="control-field">
          <mat-label>Fecha</mat-label>
          <input
            matInput
            [matDatepicker]="pickerDate"
            [(ngModel)]="selectedDate"
            (ngModelChange)="onDateChange()"
            [max]="today"
          />
          <mat-datepicker-toggle matIconSuffix [for]="pickerDate"></mat-datepicker-toggle>
          <mat-datepicker #pickerDate></mat-datepicker>
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
              <span class="stat-label">Extraídas</span>
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
                <span class="stat-label">Duración</span>
              </div>
            }
          </div>
        }

        <!-- Topic distribution -->
        @if (topicCounts().length > 0) {
          <div class="topic-summary">
            <h3>Distribución por tema</h3>
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
          <div class="count-label">{{ filteredItems().length }} noticias del {{ selectedDate | date:'yyyy-MM-dd' }}</div>
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
    .control-field { min-width: 180px; }

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

    .topic-chips {
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
    }

    .topic-chip {
      font-size: var(--text-sm);
      padding: 5px 14px;
      border-radius: 980px;
      background: var(--bg-elevated);
      border: 1px solid var(--border);
      color: var(--text-secondary);
    }
    .topic-chip strong { margin-left: 4px; color: var(--text-muted); }

    .count-label {
      color: var(--text-muted);
      margin-bottom: 16px;
      font-size: 0.875rem;
      font-weight: 500;
    }

    .news-list {
      display: flex;
      flex-direction: column;
      gap: 14px;
    }

    @media (max-width: 640px) {
      .controls { flex-wrap: wrap; }
      .control-field { width: 100%; min-width: 0; }
    }
  `],
})
export class ArchivePage implements OnInit {
  private newsService = inject(NewsService);

  todayStr = new Date().toISOString().slice(0, 10);
  today = new Date();
  selectedDate: Date = new Date();
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

  ngOnInit() {
    this.loadBriefing(this.todayStr);
  }

  onDateChange() {
    if (!this.selectedDate) return;
    this.selectedTopic.set('');
    this.loadBriefing(this.selectedDate.toISOString().slice(0, 10));
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

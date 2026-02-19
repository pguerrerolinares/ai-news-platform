import { Component, inject, signal, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';
import { MatButtonModule } from '@angular/material/button';
import { MatProgressBarModule } from '@angular/material/progress-bar';
import { NewsService } from '../services/news.service';
import { NewsItem } from '../models/news-item';
import { NewsItemCard } from '../components/news-item-card';

@Component({
  selector: 'app-search',
  imports: [CommonModule, FormsModule, NewsItemCard, MatFormFieldModule, MatInputModule, MatSelectModule, MatButtonModule, MatProgressBarModule],
  template: `
    <div class="search-page">
      <form class="search-form" (ngSubmit)="onSearch()">
        <div class="search-row">
          <mat-form-field appearance="outline" class="search-field">
            <mat-label>Buscar noticias</mat-label>
            <input
              matInput
              type="text"
              [(ngModel)]="query"
              name="query"
              placeholder="Buscar noticias..."
              class="search-input"
            />
          </mat-form-field>
          <button
            mat-flat-button
            type="submit"
            class="search-btn submit-btn"
            [disabled]="loading() || !query.trim()"
          >
            Buscar
          </button>
        </div>

        <div class="filters">
          <mat-form-field appearance="outline" class="filter-field">
            <mat-label>Tema</mat-label>
            <mat-select [(ngModel)]="selectedTopic" name="topic">
              <mat-option value="">Todos</mat-option>
              @for (topic of topics(); track topic) {
                <mat-option [value]="topic">{{ topic }}</mat-option>
              }
            </mat-select>
          </mat-form-field>
          <mat-form-field appearance="outline" class="filter-field">
            <mat-label>Desde</mat-label>
            <input matInput id="date-from" type="date" [(ngModel)]="dateFrom" name="dateFrom" />
          </mat-form-field>
          <mat-form-field appearance="outline" class="filter-field">
            <mat-label>Hasta</mat-label>
            <input matInput id="date-to" type="date" [(ngModel)]="dateTo" name="dateTo" />
          </mat-form-field>
        </div>
      </form>

      @if (!searched() && !loading()) {
        <div class="search-empty-state">
          <div class="search-empty-icon">🔍</div>
          <p class="search-empty-title">Busca entre las noticias archivadas</p>
          <p class="search-empty-hint">Prueba con: LLM, agentes, open source, GPT-4, Mistral...</p>
        </div>
      }

      @if (loading()) {
        <mat-progress-bar mode="indeterminate" class="loading-bar"></mat-progress-bar>
      }

      @if (error()) {
        <div class="error">{{ error() }}</div>
      }

      @if (searched() && !loading() && !error() && results().length === 0) {
        <div class="empty">No se encontraron resultados para "{{ lastQuery() }}"</div>
      }

      @if (results().length > 0) {
        <div class="count-label">{{ results().length }} resultados para "{{ lastQuery() }}"</div>
      }

      <div class="news-list">
        @for (item of results(); track item.id; let i = $index) {
          <app-news-item-card [item]="item" class="fade-in" [style.animation-delay]="i * 50 + 'ms'" />
        }
      </div>
    </div>
  `,
  styles: [`
    :host { display: block; }

    .search-form { margin-bottom: 8px; }

    .search-row {
      display: flex;
      gap: 10px;
      align-items: flex-start;
    }

    .search-field { flex: 1; }

    .search-btn {
      height: 56px;
      padding: 0 28px;
      font-size: var(--text-sm);
      font-weight: 600;
      letter-spacing: var(--tracking-normal);
      font-family: var(--font-body);
      border-radius: 10px;
    }

    .filters {
      display: flex;
      gap: 14px;
      flex-wrap: wrap;
    }
    .filter-field { min-width: 140px; }

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

    .search-empty-state {
      display: flex;
      flex-direction: column;
      align-items: center;
      padding: 64px 24px;
      text-align: center;
      animation: fade-in 0.4s ease-out both;
    }

    .search-empty-icon {
      font-size: 2.5rem;
      margin-bottom: 16px;
      opacity: 0.5;
    }

    .search-empty-title {
      margin: 0 0 8px;
      font-size: var(--text-base);
      font-weight: 500;
      color: var(--text-secondary);
    }

    .search-empty-hint {
      margin: 0;
      font-size: var(--text-sm);
      color: var(--text-muted);
      font-family: var(--font-mono);
    }

    @media (max-width: 640px) {
      .search-row { flex-direction: column; }
      .search-field { width: 100%; }
      .search-btn { width: 100%; height: 48px; }
      .filters { flex-direction: column; }
      .filter-field { width: 100%; min-width: 0; }
    }
  `],
})
export class SearchPage implements OnInit {
  private newsService = inject(NewsService);

  query = '';
  selectedTopic = '';
  dateFrom = '';
  dateTo = '';

  results = signal<NewsItem[]>([]);
  loading = signal(false);
  error = signal<string | null>(null);
  searched = signal(false);
  lastQuery = signal('');

  topics = signal<string[]>([]);

  ngOnInit() {
    this.newsService.getTopics().subscribe({
      next: (topics) => this.topics.set(topics),
      error: () => {},
    });
  }

  onSearch() {
    const q = this.query.trim();
    if (!q) return;

    this.loading.set(true);
    this.error.set(null);
    this.searched.set(true);
    this.lastQuery.set(q);
    this.results.set([]);

    this.newsService
      .searchItems({
        q,
        topic: this.selectedTopic || undefined,
        date_from: this.dateFrom || undefined,
        date_to: this.dateTo || undefined,
        limit: 50,
      })
      .subscribe({
        next: (items) => {
          this.results.set(items);
          this.loading.set(false);
        },
        error: (err) => {
          this.error.set('Error en la busqueda. Intenta de nuevo.');
          this.loading.set(false);
          console.error('Search failed:', err);
        },
      });
  }
}

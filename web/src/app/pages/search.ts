import { Component, inject, signal, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { NewsService } from '../services/news.service';
import { NewsItem } from '../models/news-item';
import { NewsItemCard } from '../components/news-item-card';

@Component({
  selector: 'app-search',
  imports: [CommonModule, FormsModule, NewsItemCard],
  template: `
    <div class="search-page">
      <form class="search-form" (ngSubmit)="onSearch()">
        <div class="search-row">
          <input
            type="text"
            [(ngModel)]="query"
            name="query"
            placeholder="Buscar noticias..."
            class="search-input"
          />
          <button type="submit" [disabled]="loading() || !query.trim()" class="search-btn">
            Buscar
          </button>
        </div>

        <div class="filters">
          <div class="filter-group">
            <label for="topic-select">Tema</label>
            <select id="topic-select" [(ngModel)]="selectedTopic" name="topic">
              <option value="">Todos</option>
              @for (topic of topics(); track topic) {
                <option [value]="topic">{{ topic }}</option>
              }
            </select>
          </div>
          <div class="filter-group">
            <label for="date-from">Desde</label>
            <input id="date-from" type="date" [(ngModel)]="dateFrom" name="dateFrom" />
          </div>
          <div class="filter-group">
            <label for="date-to">Hasta</label>
            <input id="date-to" type="date" [(ngModel)]="dateTo" name="dateTo" />
          </div>
        </div>
      </form>

      @if (loading()) {
        <div class="loading">Buscando...</div>
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
        @for (item of results(); track item.id) {
          <app-news-item-card [item]="item" />
        }
      </div>
    </div>
  `,
  styles: [`
    :host { display: block; }

    .search-form {
      margin-bottom: 24px;
    }
    .search-row {
      display: flex;
      gap: 10px;
      margin-bottom: 14px;
    }
    .search-input {
      flex: 1;
      padding: 12px 16px;
      border: 1px solid #d2d2d7;
      border-radius: 10px;
      font-size: 0.9375rem;
      outline: none;
      color: #1d1d1f;
      transition: border-color 0.2s, box-shadow 0.2s;
    }
    .search-input:focus {
      border-color: #0071e3;
      box-shadow: 0 0 0 4px rgba(0, 113, 227, 0.12);
    }
    .search-btn {
      padding: 12px 24px;
      background: #0071e3;
      color: white;
      border: none;
      border-radius: 980px;
      font-size: 0.875rem;
      font-weight: 500;
      cursor: pointer;
      white-space: nowrap;
      transition: background 0.2s;
      letter-spacing: -0.01em;
    }
    .search-btn:hover:not(:disabled) { background: #0077ED; }
    .search-btn:disabled { opacity: 0.42; cursor: default; }

    .filters {
      display: flex;
      gap: 14px;
      flex-wrap: wrap;
    }
    .filter-group {
      display: flex;
      flex-direction: column;
      gap: 4px;
    }
    .filter-group label {
      font-size: 0.6875rem;
      font-weight: 500;
      color: #86868b;
      text-transform: uppercase;
      letter-spacing: 0.06em;
    }
    .filter-group select,
    .filter-group input[type="date"] {
      padding: 8px 12px;
      border: 1px solid #d2d2d7;
      border-radius: 8px;
      font-size: 0.875rem;
      outline: none;
      color: #1d1d1f;
      transition: border-color 0.2s, box-shadow 0.2s;
    }
    .filter-group select:focus,
    .filter-group input[type="date"]:focus {
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

    .count-label {
      color: #86868b;
      margin-bottom: 14px;
      font-size: 0.875rem;
    }

    .news-list { display: flex; flex-direction: column; gap: 10px; }

    @media (max-width: 640px) {
      .search-row { flex-direction: column; }
      .filters { flex-direction: column; }
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

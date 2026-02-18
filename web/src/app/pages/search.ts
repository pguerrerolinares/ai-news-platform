import { Component, inject, signal } from '@angular/core';
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
              @for (topic of topics; track topic) {
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
      margin-bottom: 20px;
    }
    .search-row {
      display: flex;
      gap: 8px;
      margin-bottom: 12px;
    }
    .search-input {
      flex: 1;
      padding: 10px 14px;
      border: 1px solid #e2e8f0;
      border-radius: 6px;
      font-size: 0.95rem;
      outline: none;
    }
    .search-input:focus {
      border-color: #2563eb;
      box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.1);
    }
    .search-btn {
      padding: 10px 20px;
      background: #2563eb;
      color: white;
      border: none;
      border-radius: 6px;
      font-size: 0.9rem;
      font-weight: 600;
      cursor: pointer;
      white-space: nowrap;
    }
    .search-btn:hover:not(:disabled) { background: #1d4ed8; }
    .search-btn:disabled { opacity: 0.6; cursor: not-allowed; }

    .filters {
      display: flex;
      gap: 16px;
      flex-wrap: wrap;
    }
    .filter-group {
      display: flex;
      flex-direction: column;
      gap: 4px;
    }
    .filter-group label {
      font-size: 0.78rem;
      font-weight: 600;
      color: #64748b;
      text-transform: uppercase;
      letter-spacing: 0.5px;
    }
    .filter-group select,
    .filter-group input[type="date"] {
      padding: 7px 10px;
      border: 1px solid #e2e8f0;
      border-radius: 6px;
      font-size: 0.85rem;
      outline: none;
    }
    .filter-group select:focus,
    .filter-group input[type="date"]:focus {
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

    .count-label {
      color: #64748b;
      margin-bottom: 12px;
      font-size: 0.9rem;
    }

    .news-list { display: flex; flex-direction: column; gap: 12px; }

    @media (max-width: 640px) {
      .search-row { flex-direction: column; }
      .filters { flex-direction: column; }
    }
  `],
})
export class SearchPage {
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

  topics = [
    'modelos',
    'herramientas',
    'papers',
    'productos',
    'open_source',
    'agentes',
    'regulacion',
  ];

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

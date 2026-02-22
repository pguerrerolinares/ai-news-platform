import { Component, inject, signal, OnInit, ElementRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';
import { MatDatepickerModule } from '@angular/material/datepicker';
import { MatNativeDateModule } from '@angular/material/core';
import { MatButtonModule } from '@angular/material/button';
import { NewsService } from '../services/news.service';
import { NewsItem } from '../models/news-item';
import { NewsItemCard } from '../components/news-item-card';
import { animateCardStagger } from '../utils/gsap-animations';

@Component({
  selector: 'app-search',
  imports: [CommonModule, FormsModule, NewsItemCard, MatFormFieldModule, MatInputModule, MatSelectModule, MatDatepickerModule, MatNativeDateModule, MatButtonModule],
  template: `
    <div class="search-page">
      <!-- Section header -->
      <div class="section-header">
        <h1 class="section-title">BUSCAR</h1>
        <div class="section-line"></div>
      </div>

      <form class="search-form" (ngSubmit)="onSearch()">
        <div class="search-row">
          <mat-form-field appearance="outline" class="search-field" subscriptSizing="dynamic">
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
            BUSCAR
          </button>
        </div>

        <div class="filters">
          <mat-form-field appearance="outline" class="filter-field" subscriptSizing="dynamic">
            <mat-label>Tema</mat-label>
            <mat-select [(ngModel)]="selectedTopic" name="topic">
              <mat-option value="">Todos</mat-option>
              @for (topic of topics(); track topic) {
                <mat-option [value]="topic">{{ topic }}</mat-option>
              }
            </mat-select>
          </mat-form-field>
          <mat-form-field appearance="outline" class="filter-field" subscriptSizing="dynamic">
            <mat-label>Desde</mat-label>
            <input matInput [matDatepicker]="pickerFrom" [(ngModel)]="dateFrom" name="dateFrom" />
            <mat-datepicker-toggle matIconSuffix [for]="pickerFrom"></mat-datepicker-toggle>
            <mat-datepicker #pickerFrom></mat-datepicker>
          </mat-form-field>
          <mat-form-field appearance="outline" class="filter-field" subscriptSizing="dynamic">
            <mat-label>Hasta</mat-label>
            <input matInput [matDatepicker]="pickerTo" [(ngModel)]="dateTo" name="dateTo" />
            <mat-datepicker-toggle matIconSuffix [for]="pickerTo"></mat-datepicker-toggle>
            <mat-datepicker #pickerTo></mat-datepicker>
          </mat-form-field>
        </div>
      </form>

      @if (!searched() && !loading()) {
        <div class="search-empty-state">
          <div class="empty-icon mono">?</div>
          <p class="empty-title mono">BUSCA ENTRE LAS NOTICIAS ARCHIVADAS</p>
          <div class="search-suggestions">
            @for (term of quickTerms; track term) {
              <button type="button" class="quick-chip" (click)="quickSearch(term)">{{ term }}</button>
            }
          </div>
        </div>
      }

      @if (loading()) {
        <div class="ed-loading"><span class="mono">Buscando...</span></div>
      }

      @if (error()) {
        <div class="ed-error"><span class="mono">{{ error() }}</span></div>
      }

      @if (searched() && !loading() && !error() && results().length === 0) {
        <div class="ed-empty"><span class="mono">No se encontraron resultados para "{{ lastQuery() }}"</span></div>
      }

      @if (results().length > 0) {
        <div class="count-label mono">{{ results().length }} RESULTADOS PARA "{{ lastQuery() | uppercase }}"</div>
      }

      <div class="news-list">
        @for (item of results(); track item.id; let i = $index) {
          <app-news-item-card [item]="item" />
        }
      </div>
    </div>
  `,
  styles: [`
    :host { display: block; }

    .section-header { margin-bottom: 20px; }
    .section-title { font-size: 1.5rem; letter-spacing: -0.02em; }

    .search-form { margin-bottom: 8px; }

    .search-row {
      display: flex;
      gap: 10px;
      align-items: center;
    }
    .search-field { flex: 1; }
    .search-btn {
      height: 56px;
      padding: 0 28px;
      font-family: var(--font-mono);
      font-size: 11px;
      font-weight: 600;
      letter-spacing: 0.08em;
    }

    .filters {
      display: flex;
      gap: 14px;
      flex-wrap: wrap;
    }
    .filter-field { min-width: 140px; }

    .search-empty-state {
      display: flex;
      flex-direction: column;
      align-items: center;
      padding: 64px 24px;
      text-align: center;
      animation: fade-in 0.4s ease-out both;
    }
    .empty-icon {
      font-size: 48px;
      color: var(--accent);
      opacity: 0.4;
      margin-bottom: 16px;
      font-weight: 700;
    }
    .empty-title {
      margin: 0 0 20px;
      font-size: 11px;
      letter-spacing: 0.1em;
      color: var(--text-muted);
    }

    .search-suggestions {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      justify-content: center;
    }
    .quick-chip {
      cursor: pointer;
      background: transparent;
      color: var(--text-secondary);
      border: 1px solid var(--text-primary);
      padding: 6px 16px;
      font-family: var(--font-mono);
      font-size: 11px;
      font-weight: 500;
      transition: background 0.15s ease, color 0.15s ease;
    }
    .quick-chip:hover {
      background: var(--text-primary);
      color: var(--bg-base);
    }

    @media (max-width: 640px) {
      .search-form {
        display: flex;
        flex-direction: column;
        gap: 4px;
      }
      .search-row { display: contents; }
      .search-field { width: 100%; order: 1; }
      .filters { order: 2; flex-direction: column; }
      .filter-field { width: 100%; min-width: 0; }
      .search-btn { order: 3; width: 100%; height: 48px; }
    }
  `],
})
export class SearchPage implements OnInit {
  private newsService = inject(NewsService);
  private el = inject(ElementRef);

  query = '';
  selectedTopic = '';
  dateFrom: Date | null = null;
  dateTo: Date | null = null;

  results = signal<NewsItem[]>([]);
  loading = signal(false);
  error = signal<string | null>(null);
  searched = signal(false);
  lastQuery = signal('');

  topics = signal<string[]>([]);
  quickTerms = ['LLM', 'agentes', 'open source', 'GPT-4', 'Mistral', 'RAG'];

  quickSearch(term: string) {
    this.query = term;
    this.onSearch();
  }

  ngOnInit() {
    this.newsService.getTopics().subscribe({
      next: (topics) => this.topics.set(topics),
      error: () => { /* topics load is non-critical */ },
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
        date_from: this.dateFrom ? this.dateFrom.toISOString().slice(0, 10) : undefined,
        date_to: this.dateTo ? this.dateTo.toISOString().slice(0, 10) : undefined,
        limit: 50,
      })
      .subscribe({
        next: (res) => {
          this.results.set(res.items);
          this.loading.set(false);
          this.animateResults();
        },
        error: (err) => {
          this.error.set('Error en la búsqueda. Intenta de nuevo.');
          this.loading.set(false);
        },
      });
  }

  private animateResults() {
    requestAnimationFrame(() => {
      animateCardStagger(this.el.nativeElement, '.news-list app-news-item-card');
    });
  }
}

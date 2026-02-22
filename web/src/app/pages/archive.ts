import { Component, inject, signal, computed, OnInit, ElementRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';
import { MatDatepickerModule } from '@angular/material/datepicker';
import { MatNativeDateModule } from '@angular/material/core';
import { NewsService } from '../services/news.service';
import { NewsItem, Briefing } from '../models/news-item';
import { NewsItemCard } from '../components/news-item-card';

@Component({
  selector: 'app-archive',
  imports: [CommonModule, FormsModule, NewsItemCard, MatFormFieldModule, MatInputModule, MatSelectModule, MatDatepickerModule, MatNativeDateModule],
  template: `
    <div class="archive">
      <!-- Section header -->
      <div class="section-header">
        <h1 class="section-title">ARCHIVO</h1>
        <div class="section-line"></div>
      </div>

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
        <div class="ed-loading"><span class="mono">Cargando archivo...</span></div>
      }

      @if (error()) {
        <div class="ed-error"><span class="mono">{{ error() }}</span></div>
      }

      @if (!loading() && !error()) {
        <!-- Stats Module -->
        @if (briefing(); as b) {
          <div class="stat-module">
            <div class="stat-item">
              <span class="stat-value accent">{{ b.total_items ?? '-' }}</span>
              <span class="stat-label">Extraídas</span>
            </div>
            <div class="stat-item">
              <span class="stat-value">{{ b.items_after_dedup ?? '-' }}</span>
              <span class="stat-label">Dedup</span>
            </div>
            <div class="stat-item">
              <span class="stat-value">{{ b.items_filtered ?? '-' }}</span>
              <span class="stat-label">Filtradas</span>
            </div>
            <div class="stat-item">
              <span class="stat-value forest">{{ b.trending_count ?? '-' }}</span>
              <span class="stat-label">Trending</span>
            </div>
          </div>
        }

        <!-- Topic chips -->
        @if (topicCounts().length > 0) {
          <div class="topic-row">
            @for (tc of topicCounts(); track tc.topic) {
              <span class="topic-chip" [attr.data-topic]="tc.topic">
                {{ tc.topic }}/{{ tc.count }}
              </span>
            }
          </div>
        }

        @if (items().length === 0) {
          <div class="ed-empty"><span class="mono">No hay noticias para esta fecha.</span></div>
        }

        @if (filteredItems().length > 0) {
          <div class="count-label mono">{{ filteredItems().length }} NOTICIAS DEL {{ selectedDate | date:'yyyy-MM-dd' }}</div>
        }

        <div class="news-list">
          @for (item of filteredItems(); track item.id; let i = $index) {
            <app-news-item-card [item]="item" />
          }
        </div>
      }
    </div>
  `,
  styles: [`
    :host { display: block; }

    .section-header {
      display: flex;
      align-items: center;
      gap: 12px;
      margin-bottom: 20px;
    }
    .section-title {
      font-family: var(--font-heading);
      font-weight: 700;
      font-size: 1.5rem;
      text-transform: uppercase;
      letter-spacing: -0.02em;
      margin: 0;
      white-space: nowrap;
      color: var(--text-primary);
    }
    .section-line {
      flex: 1;
      height: 1px;
      background: var(--text-primary);
      opacity: 0.2;
    }

    .controls {
      display: flex;
      align-items: flex-start;
      gap: 12px;
      margin-bottom: 8px;
    }
    .control-field { min-width: 180px; }

    .stat-module {
      background: var(--text-primary);
      color: var(--bg-base);
      padding: 16px 20px;
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      gap: 16px;
      border-radius: 2px;
      box-shadow: var(--ed-stat-shadow);
      margin-bottom: 16px;
    }
    .stat-item { display: flex; flex-direction: column; align-items: center; }
    .stat-value {
      font-family: var(--font-mono);
      font-size: 1.25rem;
      font-weight: 500;
    }
    .stat-label {
      font-size: 8px;
      text-transform: uppercase;
      letter-spacing: 0.12em;
      font-weight: 700;
      opacity: 0.7;
      font-family: var(--font-mono);
    }
    .accent { color: var(--ed-terracotta); }
    .forest { color: var(--ed-forest); }

    .topic-row {
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
      margin-bottom: 16px;
    }
    .topic-chip {
      font-family: var(--font-mono);
      font-size: 11px;
      padding: 4px 10px;
      border: 1px solid var(--border);
      color: var(--text-secondary);
      font-weight: 500;
    }
    .topic-chip[data-topic="modelos"] { border-color: var(--topic-modelos); color: var(--topic-modelos); }
    .topic-chip[data-topic="herramientas"] { border-color: var(--topic-herramientas); color: var(--topic-herramientas); }
    .topic-chip[data-topic="papers"] { border-color: var(--topic-papers); color: var(--topic-papers); }
    .topic-chip[data-topic="open_source"] { border-color: var(--topic-open_source); color: var(--topic-open_source); }
    .topic-chip[data-topic="productos"] { border-color: var(--topic-productos); color: var(--topic-productos); }
    .topic-chip[data-topic="agentes"] { border-color: var(--topic-agentes); color: var(--topic-agentes); }
    .topic-chip[data-topic="regulacion"] { border-color: var(--topic-regulacion); color: var(--topic-regulacion); }

    .count-label {
      color: var(--text-muted);
      margin-bottom: 16px;
      font-size: 10px;
      letter-spacing: 0.06em;
    }
    .mono { font-family: var(--font-mono); }

    .ed-loading, .ed-error, .ed-empty {
      padding: 48px;
      text-align: center;
      border: 1px solid var(--border);
      font-size: var(--text-base);
    }
    .ed-error { color: var(--error); }
    .ed-empty { color: var(--text-muted); }

    .news-list {
      display: flex;
      flex-direction: column;
      gap: 14px;
    }

    @media (max-width: 640px) {
      .controls { flex-wrap: wrap; }
      .control-field { width: 100%; min-width: 0; }
      .stat-module { grid-template-columns: repeat(2, 1fr); }
    }
  `],
})
export class ArchivePage implements OnInit {
  private newsService = inject(NewsService);
  private el = inject(ElementRef);

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
    this.loadBriefing(this.today.toISOString().slice(0, 10));
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
        this.animateEntrance();
      },
      error: (err) => {
        if (err.status === 404) {
          this.error.set('No hay briefing para esta fecha.');
        } else {
          this.error.set('Error al cargar el archivo. Intenta de nuevo.');
        }
        this.loading.set(false);
      },
    });
  }

  private animateEntrance() {
    requestAnimationFrame(async () => {
      const { gsap } = await import('gsap');
      const root = this.el.nativeElement;

      // Stagger news cards
      const cards = root.querySelectorAll('.news-list app-news-item-card');
      if (cards.length) {
        gsap.from(cards, {
          y: 20, opacity: 0, duration: 0.4, stagger: 0.06, ease: 'power2.out',
        });
      }

      // Stat counter animation
      root.querySelectorAll('.stat-value').forEach((statEl: Element) => {
        const text = statEl.textContent?.trim() ?? '';
        const match = text.match(/^([\d.]+)(.*)/);
        if (!match) return;
        const num = parseFloat(match[1]);
        if (isNaN(num)) return;
        const suffix = match[2];
        const isFloat = match[1].includes('.');
        const obj = { val: 0 };
        gsap.to(obj, {
          val: num, duration: 1.2, ease: 'power2.out',
          onUpdate: () => {
            const display = isFloat ? obj.val.toFixed(1) : Math.round(obj.val).toString();
            (statEl as HTMLElement).textContent = display + suffix;
          },
        });
      });
    });
  }
}

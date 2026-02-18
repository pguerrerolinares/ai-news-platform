import { Component, DestroyRef, OnInit, inject, signal, computed } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { CommonModule } from '@angular/common';
import { HighchartsChartComponent } from 'highcharts-angular';
import * as Highcharts from 'highcharts';
import { switchMap, of } from 'rxjs';
import { NewsService } from '../services/news.service';
import { Briefing, NewsItem } from '../models/news-item';

@Component({
  selector: 'app-analytics',
  imports: [CommonModule, HighchartsChartComponent],
  template: `
    <div class="analytics">
      @if (loading()) {
        <div class="loading">Cargando analytics...</div>
      }

      @if (error()) {
        <div class="error">{{ error() }}</div>
      }

      @if (!loading() && !error()) {
        <div class="chart-grid">
          <div class="chart-card">
            <h3>Items por dia (ultimos 14 dias)</h3>
            <highcharts-chart
              [options]="itemsPerDayOptions()"
              style="width: 100%; display: block;"
            />
          </div>

          <div class="chart-card">
            <h3>Distribucion por tema</h3>
            <highcharts-chart
              [options]="topicOptions()"
              style="width: 100%; display: block;"
            />
          </div>

          <div class="chart-card">
            <h3>Fuentes</h3>
            <highcharts-chart
              [options]="sourcesOptions()"
              style="width: 100%; display: block;"
            />
          </div>
        </div>
      }
    </div>
  `,
  styles: [`
    :host { display: block; }
    .loading, .error {
      padding: 28px;
      text-align: center;
      border-radius: 14px;
      margin: 24px 0;
      font-size: 0.9375rem;
    }
    .loading { background: #f5f5f7; color: #6e6e73; }
    .error { background: #fff2f2; color: #d70015; }
    .chart-grid {
      display: flex;
      flex-direction: column;
      gap: 16px;
    }
    .chart-card {
      border-radius: 14px;
      padding: 20px 22px;
      background: #ffffff;
      box-shadow: 0 1px 2px rgba(0, 0, 0, 0.04), 0 1px 4px rgba(0, 0, 0, 0.06);
    }
    .chart-card h3 {
      margin: 0 0 14px;
      font-size: 0.8125rem;
      color: #86868b;
      font-weight: 500;
      text-transform: uppercase;
      letter-spacing: 0.06em;
    }
  `],
})
export class AnalyticsPage implements OnInit {
  private newsService = inject(NewsService);
  private destroyRef = inject(DestroyRef);

  Highcharts = Highcharts;
  briefings = signal<Briefing[]>([]);
  todayItems = signal<NewsItem[]>([]);
  loading = signal(true);
  error = signal<string | null>(null);

  itemsPerDayOptions = computed<Highcharts.Options>(() => {
    const data = this.briefings()
      .map(b => ({ date: b.date, count: b.total_items ?? 0 }))
      .sort((a, b) => a.date.localeCompare(b.date));
    return {
      chart: { type: 'line', height: 280 },
      title: { text: undefined },
      xAxis: { categories: data.map(d => d.date), labels: { rotation: -45, style: { fontSize: '11px' } } },
      yAxis: { title: { text: 'Items' }, min: 0 },
      series: [{ type: 'line', name: 'Items', data: data.map(d => d.count), color: '#2563eb' }],
      credits: { enabled: false },
      legend: { enabled: false },
    };
  });

  topicOptions = computed<Highcharts.Options>(() => {
    const counts = new Map<string, number>();
    for (const item of this.todayItems()) {
      const topic = item.topic || 'sin tema';
      counts.set(topic, (counts.get(topic) || 0) + 1);
    }
    const data = Array.from(counts.entries()).map(([name, y]) => ({ name, y }));
    return {
      chart: { type: 'pie', height: 280 },
      title: { text: undefined },
      series: [{ type: 'pie', name: 'Items', data, innerSize: '50%' }],
      credits: { enabled: false },
      plotOptions: { pie: { dataLabels: { format: '{point.name}: {point.y}' } } },
    };
  });

  sourcesOptions = computed<Highcharts.Options>(() => {
    const counts = new Map<string, number>();
    for (const item of this.todayItems()) {
      counts.set(item.source, (counts.get(item.source) || 0) + 1);
    }
    const sourceColors: Record<string, string> = {
      hackernews: '#ff6600', arxiv: '#b31b1b', reddit: '#ff4500',
      rss: '#f59e0b', github: '#333333', huggingface: '#ffcc00',
    };
    const categories = Array.from(counts.keys());
    const data = categories.map(s => ({ y: counts.get(s) || 0, color: sourceColors[s] || '#94a3b8' }));
    return {
      chart: { type: 'bar', height: 280 },
      title: { text: undefined },
      xAxis: { categories, labels: { style: { fontSize: '12px' } } },
      yAxis: { title: { text: 'Items' }, min: 0 },
      series: [{ type: 'bar', name: 'Items', data }],
      credits: { enabled: false },
      legend: { enabled: false },
    };
  });

  ngOnInit() {
    this.newsService.getBriefings().pipe(
      takeUntilDestroyed(this.destroyRef),
      switchMap((briefings) => {
        this.briefings.set(briefings.slice(0, 14));
        const today = new Date().toISOString().slice(0, 10);
        const todayBriefing = briefings.find(b => b.date === today);
        if (todayBriefing?.items) {
          this.todayItems.set(todayBriefing.items);
          return of(null);
        }
        return this.newsService.getTodayItems();
      }),
    ).subscribe({
      next: (items) => {
        if (items) { this.todayItems.set(items); }
        this.loading.set(false);
      },
      error: () => {
        this.error.set('Error al cargar analytics.');
        this.loading.set(false);
      },
    });
  }
}

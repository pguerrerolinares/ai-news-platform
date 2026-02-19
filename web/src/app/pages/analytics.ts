import { Component, DestroyRef, OnInit, inject, signal, computed } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { CommonModule } from '@angular/common';
import { MatCardModule } from '@angular/material/card';
import { MatProgressBarModule } from '@angular/material/progress-bar';
import { HighchartsChartComponent } from 'highcharts-angular';
import * as Highcharts from 'highcharts';
import { switchMap, of } from 'rxjs';
import { NewsService } from '../services/news.service';
import { Briefing, NewsItem } from '../models/news-item';

@Component({
  selector: 'app-analytics',
  imports: [CommonModule, HighchartsChartComponent, MatCardModule, MatProgressBarModule],
  template: `
    <div class="analytics">
      @if (loading()) {
        <mat-progress-bar mode="indeterminate" class="loading-bar"></mat-progress-bar>
      }

      @if (error()) {
        <div class="error">{{ error() }}</div>
      }

      @if (!loading() && !error()) {
        <div class="chart-grid">
          <mat-card class="chart-card full-width">
            <mat-card-content>
              <h3>Items por día (últimos 14 días)</h3>
              <highcharts-chart
                [options]="itemsPerDayOptions()"
                style="width: 100%; display: block;"
              />
            </mat-card-content>
          </mat-card>

          <mat-card class="chart-card">
            <mat-card-content>
              <h3>Distribución por tema</h3>
              <highcharts-chart
                [options]="topicOptions()"
                style="width: 100%; display: block;"
              />
            </mat-card-content>
          </mat-card>

          <mat-card class="chart-card">
            <mat-card-content>
              <h3>Fuentes</h3>
              <highcharts-chart
                [options]="sourcesOptions()"
                style="width: 100%; display: block;"
              />
            </mat-card-content>
          </mat-card>
        </div>
      }
    </div>
  `,
  styles: [`
    :host { display: block; }

    .loading-bar { margin-bottom: 24px; }

    .error {
      padding: 32px;
      text-align: center;
      border-radius: 14px;
      margin: 24px 0;
      font-size: var(--text-base);
      background: var(--error-subtle);
      color: #f87171;
      border: 1px solid rgba(239, 68, 68, 0.15);
    }

    .chart-grid {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 20px;
    }

    .full-width { grid-column: 1 / -1; }

    .chart-card mat-card-content { padding: 24px; }

    .chart-card h3 {
      margin: 0 0 16px;
      font-size: var(--text-xs);
      color: var(--text-muted);
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: var(--tracking-wider);
    }

    @media (max-width: 640px) {
      .chart-grid { grid-template-columns: 1fr; }
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

  private darkTheme: Partial<Highcharts.Options> = {
    chart: {
      backgroundColor: 'transparent',
      style: { fontFamily: "'Plus Jakarta Sans', sans-serif" },
    },
    xAxis: {
      labels: { style: { color: '#52525B' } },
      gridLineColor: 'rgba(255,255,255,0.04)',
      lineColor: 'rgba(255,255,255,0.06)',
      tickColor: 'rgba(255,255,255,0.06)',
    },
    yAxis: {
      labels: { style: { color: '#52525B' } },
      gridLineColor: 'rgba(255,255,255,0.04)',
      title: { style: { color: '#52525B' } },
    },
    legend: {
      itemStyle: { color: '#A1A1AA' },
      itemHoverStyle: { color: '#F4F4F5' },
    },
    tooltip: {
      backgroundColor: '#1C1C22',
      borderColor: 'rgba(255,255,255,0.1)',
      style: { color: '#F4F4F5' },
    },
  };

  itemsPerDayOptions = computed<Highcharts.Options>(() => {
    const data = this.briefings()
      .map(b => ({ date: b.date, count: b.total_items ?? 0 }))
      .sort((a, b) => a.date.localeCompare(b.date));
    return {
      ...this.darkTheme,
      chart: { ...this.darkTheme.chart, type: 'line', height: 280 },
      title: { text: undefined },
      xAxis: {
        ...this.darkTheme.xAxis as Highcharts.XAxisOptions,
        categories: data.map(d => d.date),
        labels: {
          rotation: -45,
          style: { fontSize: '11px', color: '#5a5a6e' },
        },
      },
      yAxis: {
        ...this.darkTheme.yAxis as Highcharts.YAxisOptions,
        title: { text: 'Items', style: { color: '#5a5a6e' } },
      },
      series: [{ type: 'line', name: 'Items', data: data.map(d => d.count), color: '#6366F1' }],
      credits: { enabled: false },
      legend: { enabled: false },
      tooltip: this.darkTheme.tooltip,
    };
  });

  topicOptions = computed<Highcharts.Options>(() => {
    const counts = new Map<string, number>();
    for (const item of this.todayItems()) {
      const topic = item.topic || 'sin tema';
      counts.set(topic, (counts.get(topic) || 0) + 1);
    }
    const indigoPalette = ['#6366F1', '#818CF8', '#A5B4FC', '#C7D2FE', '#A1A1AA', '#71717A', '#52525B'];
    const data = Array.from(counts.entries()).map(([name, y], i) => ({
      name,
      y,
      color: indigoPalette[i % indigoPalette.length],
    }));
    return {
      ...this.darkTheme,
      chart: { ...this.darkTheme.chart, type: 'pie', height: 280 },
      title: { text: undefined },
      series: [{ type: 'pie', name: 'Items', data, innerSize: '50%' }],
      credits: { enabled: false },
      plotOptions: {
        pie: {
          dataLabels: {
            format: '{point.name}: {point.y}',
            style: { color: '#a0a0b0', textOutline: 'none', fontSize: '11px' },
          },
          borderColor: '#141418',
        },
      },
      tooltip: this.darkTheme.tooltip,
    };
  });

  sourcesOptions = computed<Highcharts.Options>(() => {
    const counts = new Map<string, number>();
    for (const item of this.todayItems()) {
      counts.set(item.source, (counts.get(item.source) || 0) + 1);
    }
    const sourceColors: Record<string, string> = {
      hackernews: '#fb923c', arxiv: '#f87171', reddit: '#fb923c',
      rss: '#fbbf24', github: '#a0a0b0', huggingface: '#fbbf24',
    };
    const categories = Array.from(counts.keys());
    const data = categories.map(s => ({ y: counts.get(s) || 0, color: sourceColors[s] || '#71717a' }));
    return {
      ...this.darkTheme,
      chart: { ...this.darkTheme.chart, type: 'bar', height: 280 },
      title: { text: undefined },
      xAxis: {
        ...this.darkTheme.xAxis as Highcharts.XAxisOptions,
        categories,
        labels: { style: { fontSize: '12px', color: '#a0a0b0' } },
      },
      yAxis: {
        ...this.darkTheme.yAxis as Highcharts.YAxisOptions,
        title: { text: 'Items', style: { color: '#5a5a6e' } },
        min: 0,
      },
      series: [{ type: 'bar', name: 'Items', data }],
      credits: { enabled: false },
      legend: { enabled: false },
      tooltip: this.darkTheme.tooltip,
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

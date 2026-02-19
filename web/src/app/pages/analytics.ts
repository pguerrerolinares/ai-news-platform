import { Component, DestroyRef, OnInit, OnDestroy, inject, signal, computed } from '@angular/core';
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
      font-size: var(--text-sm);
      color: var(--text-secondary);
      font-weight: 600;
      letter-spacing: var(--tracking-normal);
      display: flex;
      align-items: center;
      gap: 8px;
    }
    .chart-card h3::before {
      content: '';
      display: inline-block;
      width: 8px;
      height: 8px;
      border-radius: 50%;
      background: var(--accent);
    }

    @media (max-width: 640px) {
      .chart-grid { grid-template-columns: 1fr; }
    }
  `],
})
export class AnalyticsPage implements OnInit, OnDestroy {
  private newsService = inject(NewsService);
  private destroyRef = inject(DestroyRef);

  Highcharts = Highcharts;
  briefings = signal<Briefing[]>([]);
  todayItems = signal<NewsItem[]>([]);
  loading = signal(true);
  error = signal<string | null>(null);

  isDark = signal(document.documentElement.classList.contains('dark'));
  private themeObserver?: MutationObserver;

  private chartTheme = computed<Partial<Highcharts.Options>>(() => {
    const dark = this.isDark();
    const labelColor = dark ? '#B4B4BE' : '#71717A';
    const gridColor = dark ? 'rgba(255,255,255,0.04)' : 'rgba(0,0,0,0.05)';
    const lineColor = dark ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.08)';
    return {
      chart: {
        backgroundColor: 'transparent',
        style: { fontFamily: "'Plus Jakarta Sans', sans-serif" },
      },
      xAxis: {
        labels: { style: { color: labelColor } },
        gridLineColor: gridColor,
        lineColor,
        tickColor: lineColor,
      },
      yAxis: {
        labels: { style: { color: labelColor } },
        gridLineColor: gridColor,
        title: { style: { color: labelColor } },
      },
      legend: {
        itemStyle: { color: dark ? '#B4B4BE' : '#52525B' },
        itemHoverStyle: { color: dark ? '#F4F4F5' : '#09090B' },
      },
      tooltip: {
        backgroundColor: dark ? '#1C1C22' : '#FFFFFF',
        borderColor: dark ? 'rgba(255,255,255,0.1)' : 'rgba(0,0,0,0.1)',
        borderRadius: 10,
        shadow: { color: 'rgba(0,0,0,0.15)', offsetX: 0, offsetY: 4, width: 12, opacity: 1 },
        style: { color: dark ? '#F4F4F5' : '#09090B', fontSize: '13px' },
        padding: 12,
      },
    };
  });

  itemsPerDayOptions = computed<Highcharts.Options>(() => {
    const theme = this.chartTheme();
    const data = this.briefings()
      .map(b => ({ date: b.date, count: b.total_items ?? 0 }))
      .sort((a, b) => a.date.localeCompare(b.date));
    const dark = this.isDark();
    return {
      ...theme,
      chart: { ...theme.chart, type: 'areaspline', height: 300 },
      title: { text: undefined },
      xAxis: {
        ...theme.xAxis as Highcharts.XAxisOptions,
        categories: data.map(d => d.date),
        labels: {
          rotation: -45,
          style: { fontSize: '11px', color: dark ? '#B4B4BE' : '#71717A' },
        },
      },
      yAxis: {
        ...theme.yAxis as Highcharts.YAxisOptions,
        title: { text: 'Items', style: { color: dark ? '#B4B4BE' : '#71717A' } },
      },
      plotOptions: {
        areaspline: {
          fillColor: {
            linearGradient: { x1: 0, y1: 0, x2: 0, y2: 1 },
            stops: [
              [0, dark ? 'rgba(99, 102, 241, 0.25)' : 'rgba(99, 102, 241, 0.15)'],
              [1, 'rgba(99, 102, 241, 0.02)'],
            ],
          } as unknown as string,
          marker: {
            enabled: true,
            radius: 4,
            fillColor: '#6366F1',
            lineWidth: 2,
            lineColor: dark ? '#141418' : '#FFFFFF',
          },
          lineWidth: 2.5,
        },
      },
      series: [{ type: 'areaspline' as const, name: 'Items', data: data.map(d => d.count), color: '#6366F1' }],
      credits: { enabled: false },
      legend: { enabled: false },
      tooltip: theme.tooltip,
    };
  });

  topicOptions = computed<Highcharts.Options>(() => {
    const theme = this.chartTheme();
    const counts = new Map<string, number>();
    for (const item of this.todayItems()) {
      const topic = item.topic || 'sin tema';
      counts.set(topic, (counts.get(topic) || 0) + 1);
    }
    const chartPalette = ['#6366F1', '#818CF8', '#A78BFA', '#6EE7B7', '#FBBF24', '#F472B6', '#94A3B8'];
    const dark = this.isDark();
    const data = Array.from(counts.entries()).map(([name, y], i) => ({
      name,
      y,
      color: chartPalette[i % chartPalette.length],
    }));
    return {
      ...theme,
      chart: { ...theme.chart, type: 'pie', height: 300 },
      title: { text: undefined },
      series: [{ type: 'pie', name: 'Items', data, innerSize: '55%' }],
      credits: { enabled: false },
      plotOptions: {
        pie: {
          dataLabels: {
            format: '{point.name}: {point.y}',
            style: { color: dark ? '#B4B4BE' : '#52525B', textOutline: 'none', fontSize: '12px', fontWeight: '500' },
            connectorColor: dark ? 'rgba(255,255,255,0.1)' : 'rgba(0,0,0,0.1)',
          },
          borderColor: dark ? '#141418' : '#FFFFFF',
          borderWidth: 2,
        },
      },
      tooltip: theme.tooltip,
    };
  });

  sourcesOptions = computed<Highcharts.Options>(() => {
    const theme = this.chartTheme();
    const counts = new Map<string, number>();
    for (const item of this.todayItems()) {
      counts.set(item.source, (counts.get(item.source) || 0) + 1);
    }
    const sourceColors: Record<string, string> = {
      hackernews: '#FF6600', arxiv: '#f87171', reddit: '#FF4500',
      rss: '#F59E0B', github: '#8B5CF6', huggingface: '#e6b800',
    };
    const categories = Array.from(counts.keys());
    const data = categories.map(s => ({ y: counts.get(s) || 0, color: sourceColors[s] || '#71717a' }));
    return {
      ...theme,
      chart: { ...theme.chart, type: 'bar', height: 300 },
      title: { text: undefined },
      xAxis: {
        ...theme.xAxis as Highcharts.XAxisOptions,
        categories,
        labels: { style: { fontSize: '12px', fontWeight: '500', color: this.isDark() ? '#B4B4BE' : '#52525B' } },
      },
      yAxis: {
        ...theme.yAxis as Highcharts.YAxisOptions,
        title: { text: 'Items', style: { color: this.isDark() ? '#B4B4BE' : '#71717A' } },
        min: 0,
      },
      series: [{ type: 'bar', name: 'Items', data }],
      credits: { enabled: false },
      legend: { enabled: false },
      tooltip: theme.tooltip,
    };
  });

  ngOnInit() {
    this.themeObserver = new MutationObserver(() => {
      this.isDark.set(document.documentElement.classList.contains('dark'));
    });
    this.themeObserver.observe(document.documentElement, { attributeFilter: ['class'] });

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

  ngOnDestroy() {
    this.themeObserver?.disconnect();
  }
}

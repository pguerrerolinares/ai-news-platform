import { Component, DestroyRef, OnInit, OnDestroy, inject, signal, computed } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { CommonModule } from '@angular/common';
import { HighchartsChartComponent } from 'highcharts-angular';
import * as Highcharts from 'highcharts';
import { switchMap, of, map } from 'rxjs';
import { NewsService } from '../services/news.service';
import { Briefing, NewsItem } from '../models/news-item';

@Component({
  selector: 'app-analytics',
  imports: [CommonModule, HighchartsChartComponent],
  template: `
    <div class="analytics">
      <!-- Section header -->
      <div class="section-header">
        <h1 class="section-title">ANALYTICS</h1>
        <div class="section-line"></div>
      </div>

      @if (loading()) {
        <div class="ed-loading"><span class="mono">Cargando analytics...</span></div>
      }

      @if (error()) {
        <div class="ed-error"><span class="mono">{{ error() }}</span></div>
      }

      @if (!loading() && !error()) {
        <div class="chart-grid">
          <div class="chart-card full-width">
            <h3 class="chart-heading"><span class="dot"></span> ITEMS POR DÍA (ÚLTIMOS 14 DÍAS)</h3>
            <highcharts-chart
              [options]="itemsPerDayOptions()"
              style="width: 100%; display: block;"
            />
          </div>

          <div class="chart-card">
            <h3 class="chart-heading"><span class="dot"></span> DISTRIBUCIÓN POR TEMA</h3>
            <highcharts-chart
              [options]="topicOptions()"
              style="width: 100%; display: block;"
            />
          </div>

          <div class="chart-card">
            <h3 class="chart-heading"><span class="dot"></span> FUENTES</h3>
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

    .section-header { margin-bottom: 20px; }
    .section-title { font-size: 1.5rem; letter-spacing: -0.02em; }

    .chart-grid {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 20px;
    }
    .full-width { grid-column: 1 / -1; }

    .chart-card {
      border: 1px solid var(--text-primary);
      background: var(--bg-surface);
      padding: 24px;
    }

    .chart-heading {
      margin: 0 0 16px;
      font-family: var(--font-mono);
      font-size: 10px;
      font-weight: 600;
      color: var(--text-secondary);
      letter-spacing: 0.08em;
      text-transform: uppercase;
      display: flex;
      align-items: center;
      gap: 8px;
    }
    .dot {
      display: inline-block;
      width: 6px;
      height: 6px;
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
    const labelColor = dark ? '#A0A0A0' : '#4A4A4A';
    const gridColor = dark ? 'rgba(255,255,255,0.04)' : 'rgba(0,0,0,0.05)';
    const lineColor = dark ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.08)';
    return {
      chart: {
        backgroundColor: 'transparent',
        style: { fontFamily: 'var(--font-body)' },
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
        itemStyle: { color: dark ? '#A0A0A0' : '#4A4A4A' },
        itemHoverStyle: { color: dark ? '#E0E0E0' : '#1A1A1A' },
      },
      tooltip: {
        backgroundColor: dark ? '#141414' : '#FFFFFF',
        borderColor: dark ? 'rgba(255,255,255,0.1)' : 'rgba(0,0,0,0.1)',
        borderRadius: 2,
        shadow: false,
        style: { color: dark ? '#E0E0E0' : '#1A1A1A', fontSize: '12px', fontFamily: 'var(--font-mono)' },
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
    const accentColor = dark ? '#4ADE80' : '#C05E4E';
    return {
      ...theme,
      chart: { ...theme.chart, type: 'areaspline', height: 300 },
      title: { text: undefined },
      xAxis: {
        ...theme.xAxis as Highcharts.XAxisOptions,
        categories: data.map(d => d.date),
        labels: {
          rotation: -45,
          style: { fontSize: '10px', color: dark ? '#A0A0A0' : '#4A4A4A', fontFamily: 'var(--font-mono)' },
        },
      },
      yAxis: {
        ...theme.yAxis as Highcharts.YAxisOptions,
        title: { text: 'Items', style: { color: dark ? '#A0A0A0' : '#4A4A4A' } },
      },
      plotOptions: {
        areaspline: {
          fillColor: {
            linearGradient: { x1: 0, y1: 0, x2: 0, y2: 1 },
            stops: [
              [0, dark ? 'rgba(74, 222, 128, 0.25)' : 'rgba(192, 94, 78, 0.15)'],
              [1, dark ? 'rgba(74, 222, 128, 0.02)' : 'rgba(192, 94, 78, 0.02)'],
            ],
          } as Highcharts.GradientColorObject,
          marker: {
            enabled: true,
            radius: 3,
            fillColor: accentColor,
            lineWidth: 0,
          },
          lineWidth: 2,
        },
      },
      series: [{ type: 'areaspline' as const, name: 'Items', data: data.map(d => d.count), color: accentColor }],
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
    const dark = this.isDark();
    const chartPalette = dark
      ? ['#4ADE80', '#EF6B5A', '#818CF8', '#34D399', '#FBBF24', '#FB7185', '#94A3B8']
      : ['#C05E4E', '#2D4739', '#6366F1', '#10B981', '#F59E0B', '#F43F5E', '#64748B'];
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
            style: { color: dark ? '#A0A0A0' : '#4A4A4A', textOutline: 'none', fontSize: '11px', fontWeight: '500', fontFamily: 'var(--font-mono)' },
            connectorColor: dark ? 'rgba(255,255,255,0.1)' : 'rgba(0,0,0,0.1)',
          },
          borderColor: dark ? '#111111' : '#FFFFFF',
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
      hackernews: '#FF6600', arxiv: '#B31B1B', reddit: '#FF4500',
      rss: '#E8A317', github: '#8B5CF6', huggingface: '#e6b800',
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
        labels: { style: { fontSize: '11px', fontWeight: '500', color: this.isDark() ? '#A0A0A0' : '#4A4A4A', fontFamily: 'var(--font-mono)' } },
      },
      yAxis: {
        ...theme.yAxis as Highcharts.YAxisOptions,
        title: { text: 'Items', style: { color: this.isDark() ? '#A0A0A0' : '#4A4A4A' } },
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
      switchMap((res) => {
        this.briefings.set(res.items.slice(0, 14));
        const today = new Date().toISOString().slice(0, 10);
        const todayBriefing = res.items.find(b => b.date === today);
        if (todayBriefing?.items) {
          this.todayItems.set(todayBriefing.items);
          return of(null);
        }
        return this.newsService.getTodayItems().pipe(
          map(todayRes => todayRes.items)
        );
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

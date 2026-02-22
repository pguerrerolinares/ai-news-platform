import { Component, Input, ElementRef, DestroyRef, inject, afterNextRender } from '@angular/core';
import { DatePipe, UpperCasePipe } from '@angular/common';
import { NewsItem } from '../models/news-item';
import { setupSpringHover } from '../utils/gsap-animations';

@Component({
  selector: 'app-news-item-card',
  imports: [DatePipe, UpperCasePipe],
  template: `
    <article class="ed-card" [class.hero]="hero" [attr.aria-label]="item.title">
      <div class="card-header" [attr.data-source]="item.source">
        <span class="source-label">{{ item.source | uppercase }}</span>
        @if (item.score) {
          <span class="score">{{ item.score }} PTS</span>
        }
        @if (item.trending) {
          <span class="trending" role="status" aria-label="trending">TRENDING</span>
        }
      </div>
      <div class="card-body">
        <h2>
          @if (item.url) {
            <a [href]="item.url" target="_blank" rel="noopener">{{ item.title }}</a>
          } @else {
            {{ item.title }}
          }
        </h2>
        @if (item.summary) {
          <p class="summary">{{ item.summary }}</p>
        }
      </div>
      <div class="card-footer">
        <div class="meta">
          @if (item.author) {
            <span class="author">{{ item.author }}</span>
          }
          @if (item.published_at) {
            <span class="date">{{ item.published_at | date:'short' }}</span>
          }
        </div>
        @if (item.topic) {
          <span class="topic-tag" [attr.data-topic]="item.topic">{{ item.topic }}</span>
        }
      </div>
    </article>
  `,
  styles: [`
    :host { display: block; }

    .ed-card {
      background: var(--bg-surface);
      border: 1px solid var(--text-primary);
      border-radius: 0;
      overflow: hidden;
      transition: border-color 0.15s ease, transform 0.15s ease;
    }
    .ed-card:hover {
      border-color: var(--accent);
    }

    /* Source-colored header bar */
    .card-header {
      display: flex;
      align-items: center;
      gap: 8px;
      padding: 6px 16px;
      background: var(--ed-terracotta);
      color: #fff;
      font-family: var(--font-mono);
      font-size: 10px;
      font-weight: 600;
      letter-spacing: 0.08em;
      text-transform: uppercase;
    }
    .card-header[data-source="hackernews"] { background: var(--source-hackernews); }
    .card-header[data-source="arxiv"] { background: var(--source-arxiv); }
    .card-header[data-source="reddit"] { background: var(--source-reddit); }
    .card-header[data-source="rss"] { background: var(--source-rss); color: #1A1A1A; }
    .card-header[data-source="github"] { background: var(--source-github); }
    .card-header[data-source="huggingface"] { background: var(--source-huggingface); color: #1A1A1A; }

    .source-label { flex: 1; }
    .score {
      font-variant-numeric: tabular-nums;
      opacity: 0.9;
    }
    .trending {
      padding: 1px 6px;
      border: 1px solid rgba(255,255,255,0.5);
      font-size: 9px;
      animation: pulse-dot 2s ease-in-out infinite;
    }

    /* Body */
    .card-body {
      padding: 16px;
    }
    h2 {
      margin: 0 0 8px;
      font-family: var(--font-heading);
      font-size: var(--text-lg);
      line-height: var(--leading-snug);
      letter-spacing: var(--tracking-tight);
      font-weight: 700;
      color: var(--text-primary);
    }
    h2 a {
      color: var(--text-primary);
      text-decoration: none;
    }
    h2 a:hover {
      text-decoration: underline;
    }
    .summary {
      margin: 0;
      color: var(--text-secondary);
      font-size: var(--text-base);
      line-height: var(--leading-relaxed);
      display: -webkit-box;
      -webkit-line-clamp: 3;
      -webkit-box-orient: vertical;
      overflow: hidden;
    }

    /* Footer */
    .card-footer {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 10px 16px;
      border-top: 1px solid var(--border);
      font-family: var(--font-mono);
      font-size: 10px;
      letter-spacing: 0.04em;
    }
    .meta {
      display: flex;
      gap: 12px;
      color: var(--text-muted);
    }
    .topic-tag {
      padding: 2px 8px;
      border: 1px solid var(--border);
      font-weight: 500;
      text-transform: uppercase;
      color: var(--text-secondary);
    }
    .topic-tag[data-topic="modelos"] { border-color: var(--topic-modelos); color: var(--topic-modelos); }
    .topic-tag[data-topic="herramientas"] { border-color: var(--topic-herramientas); color: var(--topic-herramientas); }
    .topic-tag[data-topic="papers"] { border-color: var(--topic-papers); color: var(--topic-papers); }
    .topic-tag[data-topic="open_source"] { border-color: var(--topic-open_source); color: var(--topic-open_source); }
    .topic-tag[data-topic="productos"] { border-color: var(--topic-productos); color: var(--topic-productos); }
    .topic-tag[data-topic="agentes"] { border-color: var(--topic-agentes); color: var(--topic-agentes); }
    .topic-tag[data-topic="regulacion"] { border-color: var(--topic-regulacion); color: var(--topic-regulacion); }

    /* Hero variant */
    .ed-card.hero .card-body { padding: 20px; }
    .ed-card.hero h2 {
      font-size: var(--text-xl);
    }
    .ed-card.hero .summary {
      -webkit-line-clamp: 5;
      font-size: var(--text-base);
      line-height: var(--leading-relaxed);
    }
  `],
})
export class NewsItemCard {
  @Input({ required: true }) item!: NewsItem;
  @Input() hero = false;

  private el = inject(ElementRef);
  private destroyRef = inject(DestroyRef);

  constructor() {
    afterNextRender(async () => {
      const card = this.el.nativeElement.querySelector('.ed-card') as HTMLElement | null;
      if (!card) return;

      const cleanup = await setupSpringHover(card);
      this.destroyRef.onDestroy(cleanup);
    });
  }
}

import { Component, Input } from '@angular/core';
import { CommonModule, DatePipe } from '@angular/common';
import { NewsItem } from '../models/news-item';

@Component({
  selector: 'app-news-item-card',
  imports: [CommonModule, DatePipe],
  template: `
    <article class="news-item">
      <div class="item-header">
        <span class="source-badge" [attr.data-source]="item.source">{{ item.source }}</span>
        @if (item.score) {
          <span class="score">{{ item.score }} pts</span>
        }
        @if (item.topic) {
          <span class="topic-badge">{{ item.topic }}</span>
        }
        @if (item.trending) {
          <span class="trending">trending</span>
        }
      </div>
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
      <div class="item-meta">
        @if (item.author) {
          <span>{{ item.author }}</span>
        }
        @if (item.published_at) {
          <span>{{ item.published_at | date:'short' }}</span>
        }
      </div>
    </article>
  `,
  styles: [`
    :host { display: block; }
    .news-item {
      border-radius: 14px;
      padding: 20px 22px;
      background: #ffffff;
      box-shadow: 0 1px 2px rgba(0, 0, 0, 0.04), 0 1px 4px rgba(0, 0, 0, 0.06);
      transition: box-shadow 0.25s ease, transform 0.25s ease;
    }
    .news-item:hover {
      box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06), 0 4px 16px rgba(0, 0, 0, 0.08);
      transform: translateY(-1px);
    }
    .item-header {
      display: flex;
      gap: 8px;
      align-items: center;
      margin-bottom: 10px;
      flex-wrap: wrap;
    }
    .source-badge {
      font-size: 0.6875rem;
      padding: 3px 8px;
      border-radius: 5px;
      font-weight: 600;
      background: #f5f5f7;
      color: #6e6e73;
      letter-spacing: 0.02em;
    }
    .source-badge[data-source="hackernews"] { background: #fff4ec; color: #c2410c; }
    .source-badge[data-source="arxiv"] { background: #fef2f2; color: #b91c1c; }
    .source-badge[data-source="reddit"] { background: #fff7ed; color: #c2410c; }
    .source-badge[data-source="rss"] { background: #fffbeb; color: #b45309; }
    .source-badge[data-source="github"] { background: #f5f5f7; color: #1d1d1f; }
    .source-badge[data-source="huggingface"] { background: #fffbeb; color: #a16207; }
    .score {
      font-size: 0.75rem;
      color: #86868b;
      font-weight: 500;
      font-variant-numeric: tabular-nums;
    }
    .topic-badge {
      font-size: 0.6875rem;
      padding: 3px 8px;
      border-radius: 5px;
      background: #f0f1ff;
      color: #4338ca;
      font-weight: 500;
    }
    .trending {
      font-size: 0.6875rem;
      padding: 3px 8px;
      border-radius: 5px;
      background: #fefce8;
      color: #a16207;
      font-weight: 600;
    }
    h2 {
      margin: 0 0 8px;
      font-size: 1.0625rem;
      line-height: 1.4;
      letter-spacing: -0.01em;
      font-weight: 600;
    }
    h2 a {
      color: #1d1d1f;
      text-decoration: none;
      transition: color 0.15s;
    }
    h2 a:hover { color: #0071e3; }
    .summary {
      margin: 0 0 10px;
      color: #6e6e73;
      font-size: 0.9375rem;
      line-height: 1.6;
    }
    .item-meta {
      display: flex;
      gap: 12px;
      color: #aeaeb2;
      font-size: 0.8125rem;
    }
  `],
})
export class NewsItemCard {
  @Input({ required: true }) item!: NewsItem;
}

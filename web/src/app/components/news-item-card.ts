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
      border: 1px solid #e2e8f0;
      border-radius: 8px;
      padding: 16px;
      transition: box-shadow 0.15s;
    }
    .news-item:hover { box-shadow: 0 2px 8px rgba(0,0,0,0.08); }
    .item-header {
      display: flex;
      gap: 8px;
      align-items: center;
      margin-bottom: 8px;
      flex-wrap: wrap;
    }
    .source-badge {
      font-size: 0.75rem;
      padding: 2px 8px;
      border-radius: 4px;
      font-weight: 600;
      background: #e2e8f0;
      color: #475569;
      text-transform: uppercase;
    }
    .source-badge[data-source="hackernews"] { background: #ff6600; color: white; }
    .source-badge[data-source="arxiv"] { background: #b31b1b; color: white; }
    .source-badge[data-source="reddit"] { background: #ff4500; color: white; }
    .source-badge[data-source="rss"] { background: #f59e0b; color: white; }
    .source-badge[data-source="github"] { background: #24292f; color: white; }
    .source-badge[data-source="huggingface"] { background: #ff9d00; color: white; }
    .score { font-size: 0.8rem; color: #64748b; font-weight: 500; }
    .topic-badge {
      font-size: 0.7rem;
      padding: 2px 6px;
      border-radius: 3px;
      background: #dbeafe;
      color: #1e40af;
    }
    .trending {
      font-size: 0.7rem;
      padding: 2px 6px;
      border-radius: 3px;
      background: #fef3c7;
      color: #b45309;
      font-weight: 600;
    }
    h2 {
      margin: 0 0 8px;
      font-size: 1.05rem;
      line-height: 1.4;
    }
    h2 a { color: #1e293b; text-decoration: none; }
    h2 a:hover { color: #2563eb; text-decoration: underline; }
    .summary { margin: 0 0 8px; color: #475569; font-size: 0.9rem; line-height: 1.5; }
    .item-meta {
      display: flex;
      gap: 12px;
      color: #94a3b8;
      font-size: 0.8rem;
    }
  `],
})
export class NewsItemCard {
  @Input({ required: true }) item!: NewsItem;
}

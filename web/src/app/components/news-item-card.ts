import { Component, Input } from '@angular/core';
import { CommonModule, DatePipe } from '@angular/common';
import { MatCardModule } from '@angular/material/card';
import { MatChipsModule } from '@angular/material/chips';
import { NewsItem } from '../models/news-item';

@Component({
  selector: 'app-news-item-card',
  imports: [CommonModule, DatePipe, MatCardModule, MatChipsModule],
  template: `
    <article>
      <mat-card class="news-item">
        <mat-card-content>
          <div class="item-header">
            <span class="source-badge" [attr.data-source]="item.source">{{ item.source }}</span>
            @if (item.score) {
              <span class="score">{{ item.score }} pts</span>
            }
            @if (item.topic) {
              <mat-chip class="topic-badge" disabled>{{ item.topic }}</mat-chip>
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
        </mat-card-content>
      </mat-card>
    </article>
  `,
  styles: [`
    :host { display: block; }
    article { display: block; }
    .news-item {
      transition: border-color 0.15s ease, background 0.15s ease, transform 0.15s ease;
    }
    .news-item:hover {
      border-color: var(--border-hover) !important;
      background: var(--bg-surface-hover);
      transform: translateY(-1px);
    }
    mat-card-content {
      padding: 20px;
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
      letter-spacing: 0.02em;
      background: rgba(255,255,255,0.08);
      color: var(--text-secondary);
    }
    .source-badge[data-source="hackernews"] { background: rgba(255,102,0,0.12); color: #fb923c; }
    .source-badge[data-source="arxiv"] { background: rgba(185,28,28,0.12); color: #f87171; }
    .source-badge[data-source="reddit"] { background: rgba(255,69,0,0.12); color: #fb923c; }
    .source-badge[data-source="rss"] { background: rgba(245,158,11,0.12); color: #fbbf24; }
    .source-badge[data-source="github"] { background: rgba(255,255,255,0.08); color: var(--text-secondary); }
    .source-badge[data-source="huggingface"] { background: rgba(255,204,0,0.12); color: #fbbf24; }
    .score {
      font-family: var(--font-mono);
      font-size: 0.75rem;
      color: var(--text-tertiary);
      font-weight: 400;
      font-variant-numeric: tabular-nums;
    }
    .topic-badge {
      --mdc-chip-elevated-container-color: var(--accent-subtle);
      --mdc-chip-label-text-color: #8b8bd8;
      --mdc-chip-container-height: 22px;
      --mdc-chip-label-text-size: 0.6875rem;
      font-weight: 500;
    }
    .trending {
      font-size: 0.6875rem;
      padding: 3px 8px;
      border-radius: 5px;
      background: rgba(250,204,21,0.1);
      color: #facc15;
      font-weight: 600;
    }
    h2 {
      margin: 0 0 8px;
      font-family: var(--font-heading);
      font-size: 1rem;
      line-height: 1.4;
      letter-spacing: -0.02em;
      font-weight: 600;
    }
    h2 a {
      color: var(--text-primary);
      text-decoration: none;
      transition: text-decoration 0.15s ease;
    }
    h2 a:hover { text-decoration: underline; }
    .summary {
      margin: 0 0 10px;
      color: var(--text-secondary);
      font-size: 0.875rem;
      line-height: 1.6;
    }
    .item-meta {
      display: flex;
      gap: 12px;
      font-family: var(--font-mono);
      color: var(--text-tertiary);
      font-size: 0.75rem;
    }
  `],
})
export class NewsItemCard {
  @Input({ required: true }) item!: NewsItem;
}

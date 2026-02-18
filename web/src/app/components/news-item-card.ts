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
      transition: border-color 0.2s ease, box-shadow 0.2s ease, transform 0.2s ease,
        background 0.2s ease;
    }
    .news-item:hover {
      border-color: var(--border-accent) !important;
      box-shadow: 0 4px 16px rgba(0, 0, 0, 0.12), 0 0 0 1px var(--border-accent);
      transform: translateY(-2px);
    }
    mat-card-content {
      padding: 24px;
    }
    .item-header {
      display: flex;
      gap: 8px;
      align-items: center;
      margin-bottom: 12px;
      flex-wrap: wrap;
    }
    .source-badge {
      font-size: var(--text-xs);
      padding: 3px 10px;
      border-radius: 6px;
      font-weight: 600;
      letter-spacing: var(--tracking-wide);
      background: rgba(255, 255, 255, 0.06);
      color: var(--text-secondary);
    }
    .source-badge[data-source="hackernews"] { background: rgba(255, 102, 0, 0.12); color: #fb923c; }
    .source-badge[data-source="arxiv"] { background: rgba(185, 28, 28, 0.12); color: #f87171; }
    .source-badge[data-source="reddit"] { background: rgba(255, 69, 0, 0.12); color: #fb923c; }
    .source-badge[data-source="rss"] { background: rgba(245, 158, 11, 0.12); color: #fbbf24; }
    .source-badge[data-source="github"] { background: rgba(255, 255, 255, 0.06); color: var(--text-secondary); }
    .source-badge[data-source="huggingface"] { background: rgba(255, 204, 0, 0.12); color: #fbbf24; }
    .score {
      font-family: var(--font-mono);
      font-size: 0.75rem;
      color: var(--text-muted);
      font-weight: 400;
      font-variant-numeric: tabular-nums;
    }
    .topic-badge {
      --mdc-chip-elevated-container-color: var(--accent-glow);
      --mdc-chip-label-text-color: var(--accent);
      --mdc-chip-container-height: 22px;
      --mdc-chip-label-text-size: var(--text-xs);
      font-weight: 500;
    }
    .trending {
      font-size: var(--text-xs);
      padding: 3px 10px;
      border-radius: 6px;
      background: rgba(250, 204, 21, 0.1);
      color: #facc15;
      font-weight: 600;
    }
    h2 {
      margin: 0 0 8px;
      font-family: var(--font-heading);
      font-size: var(--text-lg);
      line-height: var(--leading-snug);
      letter-spacing: var(--tracking-tight);
      font-weight: 700;
    }
    h2 a {
      color: var(--text-primary);
      text-decoration: none;
      background-image: linear-gradient(var(--text-primary), var(--text-primary));
      background-size: 0% 1px;
      background-position: left bottom;
      background-repeat: no-repeat;
      transition: background-size 0.25s ease;
    }
    h2 a:hover {
      background-size: 100% 1px;
    }
    .summary {
      margin: 0 0 14px;
      color: var(--text-secondary);
      font-size: var(--text-base);
      line-height: var(--leading-relaxed);
      display: -webkit-box;
      -webkit-line-clamp: 3;
      -webkit-box-orient: vertical;
      overflow: hidden;
    }
    .item-meta {
      display: flex;
      gap: 12px;
      font-family: var(--font-mono);
      color: var(--text-muted);
      font-size: 0.75rem;
      padding-top: 12px;
      border-top: 1px solid var(--border);
    }
  `],
})
export class NewsItemCard {
  @Input({ required: true }) item!: NewsItem;
}

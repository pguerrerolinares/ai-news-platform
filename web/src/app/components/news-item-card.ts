import { Component, Input } from '@angular/core';
import { CommonModule, DatePipe } from '@angular/common';
import { MatCardModule } from '@angular/material/card';
import { MatChipsModule } from '@angular/material/chips';
import { NewsItem } from '../models/news-item';

@Component({
  selector: 'app-news-item-card',
  imports: [CommonModule, DatePipe, MatCardModule, MatChipsModule],
  template: `
    <article [attr.aria-label]="item.title">
      <mat-card class="news-item" [class.hero]="hero">
        <mat-card-content>
          <div class="item-header">
            <span class="source-badge" [attr.data-source]="item.source">{{ item.source }}</span>
            @if (item.score) {
              <span class="score">{{ item.score }} pts</span>
            }
            @if (item.topic) {
              <mat-chip class="topic-badge" disabled [attr.data-topic]="item.topic">{{ item.topic }}</mat-chip>
            }
            @if (item.trending) {
              <span class="trending" role="status" aria-label="trending">trending</span>
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
    .source-badge[data-source="hackernews"] { background: color-mix(in srgb, var(--source-hackernews) 15%, transparent); color: var(--source-hackernews); }
    .source-badge[data-source="arxiv"] { background: color-mix(in srgb, var(--source-arxiv) 15%, transparent); color: var(--source-arxiv); }
    .source-badge[data-source="reddit"] { background: color-mix(in srgb, var(--source-reddit) 15%, transparent); color: var(--source-reddit); }
    .source-badge[data-source="rss"] { background: color-mix(in srgb, var(--source-rss) 15%, transparent); color: var(--source-rss); }
    .source-badge[data-source="github"] { background: color-mix(in srgb, var(--source-github) 15%, transparent); color: var(--source-github); }
    .source-badge[data-source="huggingface"] { background: color-mix(in srgb, var(--source-huggingface) 15%, transparent); color: var(--source-huggingface); }
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
    .topic-badge[data-topic="modelos"] { --mdc-chip-elevated-container-color: color-mix(in srgb, var(--topic-modelos) 12%, transparent); --mdc-chip-label-text-color: var(--topic-modelos); }
    .topic-badge[data-topic="herramientas"] { --mdc-chip-elevated-container-color: color-mix(in srgb, var(--topic-herramientas) 12%, transparent); --mdc-chip-label-text-color: var(--topic-herramientas); }
    .topic-badge[data-topic="papers"] { --mdc-chip-elevated-container-color: color-mix(in srgb, var(--topic-papers) 12%, transparent); --mdc-chip-label-text-color: var(--topic-papers); }
    .topic-badge[data-topic="open_source"] { --mdc-chip-elevated-container-color: color-mix(in srgb, var(--topic-open_source) 12%, transparent); --mdc-chip-label-text-color: var(--topic-open_source); }
    .topic-badge[data-topic="productos"] { --mdc-chip-elevated-container-color: color-mix(in srgb, var(--topic-productos) 12%, transparent); --mdc-chip-label-text-color: var(--topic-productos); }
    .topic-badge[data-topic="agentes"] { --mdc-chip-elevated-container-color: color-mix(in srgb, var(--topic-agentes) 12%, transparent); --mdc-chip-label-text-color: var(--topic-agentes); }
    .topic-badge[data-topic="regulacion"] { --mdc-chip-elevated-container-color: color-mix(in srgb, var(--topic-regulacion) 12%, transparent); --mdc-chip-label-text-color: var(--topic-regulacion); }
    .trending {
      font-size: var(--text-xs);
      padding: 3px 10px;
      border-radius: 6px;
      background: rgba(250, 204, 21, 0.1);
      color: #facc15;
      font-weight: 600;
    }

    /* Hero card variant */
    .news-item.hero {
      border-left: 4px solid var(--accent) !important;
      background: linear-gradient(135deg, var(--bg-elevated), color-mix(in srgb, var(--accent) 4%, var(--bg-elevated))) !important;
    }
    .news-item.hero mat-card-content { padding: 28px 28px 28px 24px; }
    .news-item.hero h2 { font-size: var(--text-xl); }
    .news-item.hero .summary {
      -webkit-line-clamp: 5;
      font-size: var(--text-base);
      line-height: var(--leading-relaxed);
    }
    .news-item.hero .trending {
      animation: hero-pulse 2s ease-in-out infinite;
    }
    @keyframes hero-pulse {
      0%, 100% { opacity: 1; }
      50% { opacity: 0.6; }
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
  @Input() hero = false;
}

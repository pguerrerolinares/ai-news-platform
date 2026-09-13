# Milestone 6 — Frontend Polish Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Eliminate frontend code duplication, add missing source badge colors, render markdown in chat, make topic chips interactive, expose topics via API, and widen the layout.

**Architecture:** Extract a shared `NewsItemCard` component used by dashboard, archive, and search. Add a `GET /api/topics` backend endpoint that drives topic dropdowns dynamically. Install `marked` + `dompurify` for safe markdown rendering in chat. All topic filtering is client-side (no new API calls needed).

**Tech Stack:** Angular 21 (standalone components, signals), FastAPI, marked, dompurify, Playwright (E2E)

---

### Task 1: Topics API Endpoint (Backend)

Create `GET /api/topics` that returns topics from Settings. This is the only backend change and unblocks the frontend tasks.

**Files:**
- Create: `src/api/routes/topics.py`
- Modify: `src/api/app.py:74-79`
- Create: `tests/unit/test_topics_api.py`

**Step 1: Write the failing test**

Create `tests/unit/test_topics_api.py`:

```python
"""Tests for GET /api/topics endpoint."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from src.api.app import app


@pytest.fixture()
async def api_client() -> AsyncClient:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac  # type: ignore[misc]


class TestTopicsEndpoint:
    """Verify GET /api/topics returns topic list from config."""

    async def test_returns_200(self, api_client: AsyncClient):
        resp = await api_client.get("/api/topics")
        assert resp.status_code == 200

    async def test_returns_topics_list(self, api_client: AsyncClient):
        resp = await api_client.get("/api/topics")
        data = resp.json()
        assert "topics" in data
        assert isinstance(data["topics"], list)
        assert len(data["topics"]) > 0

    async def test_contains_known_topics(self, api_client: AsyncClient):
        resp = await api_client.get("/api/topics")
        topics = resp.json()["topics"]
        assert "modelos" in topics
        assert "herramientas" in topics
        assert "papers" in topics

    async def test_no_auth_required(self, api_client: AsyncClient):
        """Topics endpoint should be accessible without JWT."""
        resp = await api_client.get("/api/topics")
        assert resp.status_code == 200
```

**Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/unit/test_topics_api.py -v`
Expected: FAIL (404 Not Found — route doesn't exist yet)

**Step 3: Create the route**

Create `src/api/routes/topics.py`:

```python
"""API route for available topics."""

from fastapi import APIRouter

from src.core.config import get_settings

router = APIRouter(prefix="/api/topics", tags=["topics"])


@router.get("")
async def get_topics() -> dict[str, list[str]]:
    """Return the list of configured topics. No auth required."""
    settings = get_settings()
    return {"topics": settings.topics_list}
```

**Step 4: Register the router in `src/api/app.py`**

Add import after line 21 (after the search_router import):

```python
from src.api.routes.topics import router as topics_router
```

Add after line 79 (after `app.include_router(chat_router)`):

```python
app.include_router(topics_router)
```

**Step 5: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/unit/test_topics_api.py -v`
Expected: 4 passed

**Step 6: Run full unit test suite**

Run: `.venv/bin/pytest tests/unit/ --timeout=30 -q`
Expected: 637+ passed

**Step 7: Commit**

```bash
git add src/api/routes/topics.py src/api/app.py tests/unit/test_topics_api.py
git commit -m "feat(m6): add GET /api/topics endpoint"
```

---

### Task 2: NewsItemCard Shared Component

Extract the duplicated news item card (template + CSS) into a standalone component. This is the biggest refactor — it touches 3 pages.

**Files:**
- Create: `web/src/app/components/news-item-card.ts`
- Modify: `web/src/app/pages/dashboard.ts`
- Modify: `web/src/app/pages/archive.ts`
- Modify: `web/src/app/pages/search.ts`

**Step 1: Create the shared component**

Create `web/src/app/components/news-item-card.ts`:

```typescript
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
```

**Step 2: Update `dashboard.ts`**

Replace the entire `@for (item of items()` block (lines 73-106) in the template with:

```html
        <div class="news-list">
          @for (item of filteredItems(); track item.id) {
            <app-news-item-card [item]="item" />
          }
        </div>
```

In the imports array, replace `CommonModule, DatePipe` with `CommonModule, NewsItemCard`.

Add import at top: `import { NewsItemCard } from '../components/news-item-card';`

Remove all card-related CSS from dashboard (`.news-list`, `.news-item`, `.item-header`, `.source-badge`, `.score`, `.topic-badge`, `.trending`, `h2`, `.summary`, `.item-meta` — lines 182-239). Keep `.loading`, `.error`, `.empty`, `.stats-bar`, `.stat`, `.topic-*`, `.count-label`.

Add a `selectedTopic` signal and `filteredItems` computed:

```typescript
  selectedTopic = signal<string | null>(null);

  filteredItems = computed(() => {
    const topic = this.selectedTopic();
    if (!topic) return this.items();
    return this.items().filter(item => item.topic === topic);
  });
```

Make topic chips clickable. Change the template from:

```html
                <span class="topic-chip">
                  {{ tc.topic }} <strong>{{ tc.count }}</strong>
                </span>
```

To:

```html
                <button
                  class="topic-chip"
                  [class.active]="selectedTopic() === tc.topic"
                  (click)="toggleTopic(tc.topic)"
                >
                  {{ tc.topic }} <strong>{{ tc.count }}</strong>
                </button>
```

Add method:

```typescript
  toggleTopic(topic: string) {
    this.selectedTopic.update(current => current === topic ? null : topic);
  }
```

Add CSS for active topic chip:

```css
    .topic-chip {
      font-size: 0.78rem;
      padding: 3px 10px;
      border-radius: 12px;
      background: #dbeafe;
      color: #1e40af;
      border: none;
      cursor: pointer;
      transition: all 0.15s;
    }
    .topic-chip:hover { background: #bfdbfe; }
    .topic-chip.active {
      background: #2563eb;
      color: white;
    }
    .topic-chip strong { margin-left: 4px; }
```

Update the count label to show filtered count:

```html
        @if (filteredItems().length > 0) {
          <div class="count-label">
            {{ filteredItems().length }} noticias hoy
            @if (selectedTopic()) {
              <button class="clear-filter" (click)="selectedTopic.set(null)">limpiar filtro</button>
            }
          </div>
        }
```

Add CSS:

```css
    .clear-filter {
      background: none;
      border: none;
      color: #2563eb;
      font-size: 0.85rem;
      cursor: pointer;
      margin-left: 8px;
      text-decoration: underline;
    }
```

**Step 3: Update `archive.ts`**

Same pattern: import `NewsItemCard`, replace the `@for` block with `<app-news-item-card>`, remove card CSS.

Add a topic dropdown in the controls section (after the date input):

```html
        <select [(ngModel)]="selectedTopic" (ngModelChange)="0" class="topic-select">
          <option value="">Todos los temas</option>
          @for (tc of topicCounts(); track tc.topic) {
            <option [value]="tc.topic">{{ tc.topic }} ({{ tc.count }})</option>
          }
        </select>
```

Add `selectedTopic = '';` property and a `filteredItems` computed:

```typescript
  selectedTopic = '';

  filteredItems = computed(() => {
    if (!this.selectedTopic) return this.items();
    return this.items().filter(item => item.topic === this.selectedTopic);
  });
```

Use `filteredItems()` in the template instead of `items()` for both the count label and the `@for` loop.

**Step 4: Update `search.ts`**

Import `NewsItemCard`, replace `@for` block with `<app-news-item-card>`, remove card CSS. The search page keeps its own form/filter CSS.

**Step 5: Build Angular to verify**

Run: `cd web && npx ng build`
Expected: Build succeeds

**Step 6: Run E2E tests**

Run: `.venv/bin/pytest tests/e2e/ -v --timeout=30`
Expected: All 34 pass (E2E tests use `.topic-badge` selector which now lives inside the card component — Playwright traverses shadow DOM by default in Angular, so selectors still work)

**Step 7: Commit**

```bash
git add web/src/app/components/news-item-card.ts web/src/app/pages/dashboard.ts web/src/app/pages/archive.ts web/src/app/pages/search.ts
git commit -m "refactor(m6): extract NewsItemCard component, add topic filters"
```

---

### Task 3: Markdown Rendering in Chat

Install `marked` + `dompurify` and render assistant messages as HTML.

**Files:**
- Modify: `web/package.json` (add dependencies)
- Modify: `web/src/app/pages/chat.ts`

**Step 1: Install dependencies**

Run from `web/` directory:

```bash
cd web && npm install marked dompurify && npm install -D @types/dompurify
```

This adds:
- `marked`: Markdown-to-HTML converter (lightweight, 0 deps)
- `dompurify`: Sanitizes HTML to prevent XSS
- `@types/dompurify`: TypeScript types

**Step 2: Update `chat.ts`**

Add imports at the top:

```typescript
import { marked } from 'marked';
import DOMPurify from 'dompurify';
```

Change the message content display from:

```html
            <div class="message-content">{{ msg.content }}</div>
```

To:

```html
            <div class="message-content" [innerHTML]="renderMarkdown(msg.content)"></div>
```

And for the streaming buffer, keep plain text (markdown renders mid-stream look broken):

```html
            <div class="message-content">{{ streamBuffer() }}<span class="cursor">|</span></div>
```

Add the render method to the class:

```typescript
  renderMarkdown(text: string): string {
    const html = marked.parse(text, { async: false }) as string;
    return DOMPurify.sanitize(html);
  }
```

Add CSS for rendered markdown elements inside `.message.assistant`:

```css
    .message.assistant .message-content :first-child { margin-top: 0; }
    .message.assistant .message-content :last-child { margin-bottom: 0; }
    .message.assistant .message-content p { margin: 0.5em 0; }
    .message.assistant .message-content ul,
    .message.assistant .message-content ol {
      margin: 0.5em 0;
      padding-left: 1.5em;
    }
    .message.assistant .message-content code {
      background: #e2e8f0;
      padding: 1px 4px;
      border-radius: 3px;
      font-size: 0.85em;
    }
    .message.assistant .message-content pre {
      background: #1e293b;
      color: #e2e8f0;
      padding: 12px;
      border-radius: 6px;
      overflow-x: auto;
      margin: 0.5em 0;
    }
    .message.assistant .message-content pre code {
      background: none;
      padding: 0;
      color: inherit;
    }
    .message.assistant .message-content strong { font-weight: 600; }
    .message.assistant .message-content a {
      color: #2563eb;
      text-decoration: underline;
    }
```

Remove `white-space: pre-wrap;` from `.message` CSS (line 151) since markdown now handles line breaks. Add it only to `.message.user`:

```css
    .message.user { white-space: pre-wrap; }
```

**Step 3: Build Angular to verify**

Run: `cd web && npx ng build`
Expected: Build succeeds

**Step 4: Run E2E tests**

Run: `.venv/bin/pytest tests/e2e/ -v --timeout=30`
Expected: All pass

**Step 5: Commit**

```bash
git add web/package.json web/package-lock.json web/src/app/pages/chat.ts
git commit -m "feat(m6): render markdown in chat with marked + dompurify"
```

---

### Task 4: Dynamic Topics from API

Replace hardcoded topic arrays in `chat.ts` and `search.ts` with data from `GET /api/topics`.

**Files:**
- Modify: `web/src/app/services/news.service.ts`
- Modify: `web/src/app/pages/chat.ts`
- Modify: `web/src/app/pages/search.ts`
- Modify: `tests/e2e/conftest.py` (add topics mock route)

**Step 1: Add `getTopics()` to `NewsService`**

In `web/src/app/services/news.service.ts`, add:

```typescript
  getTopics(): Observable<string[]> {
    return this.http.get<{ topics: string[] }>(`${this.baseUrl}/topics`).pipe(
      map(response => response.topics),
    );
  }
```

Add `map` to the rxjs import:

```typescript
import { Observable, map } from 'rxjs';
```

**Step 2: Update `search.ts`**

Replace the hardcoded `topics` array with a signal loaded from the API:

```typescript
  private newsService = inject(NewsService);
  topics = signal<string[]>([]);
```

Add `OnInit` implementation:

```typescript
export class SearchPage implements OnInit {
```

Add to imports: `import { OnInit } from '@angular/core';`

Add `ngOnInit`:

```typescript
  ngOnInit() {
    this.newsService.getTopics().subscribe({
      next: (topics) => this.topics.set(topics),
      error: () => {
        // Fallback to empty — the dropdown just won't have options
      },
    });
  }
```

Update the template to use `topics()` signal instead of `topics`:

```html
              @for (topic of topics(); track topic) {
```

**Step 3: Update `chat.ts`**

Same pattern. Replace `topics = [...]` with:

```typescript
  private newsService = inject(NewsService);
  topics = signal<string[]>([]);
```

Add `OnInit`, inject `NewsService`, load in `ngOnInit`:

```typescript
  ngOnInit() {
    this.newsService.getTopics().subscribe({
      next: (topics) => this.topics.set(topics),
    });
  }
```

Add import: `import { NewsService } from '../services/news.service';`

Update template to use `topics()` signal.

**Step 4: Add topics mock route to E2E conftest**

In `tests/e2e/conftest.py`, add a handler in `setup_mock_routes`:

```python
    def handle_topics(route):
        route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps({"topics": [
                "modelos", "herramientas", "papers", "productos",
                "open_source", "agentes", "regulacion",
            ]}),
        )
```

Register it after the chat route:

```python
    page.route("**/api/topics", handle_topics)
```

**Step 5: Build and test**

Run: `cd web && npx ng build`
Expected: Build succeeds

Run: `.venv/bin/pytest tests/e2e/ -v --timeout=30`
Expected: All pass

**Step 6: Commit**

```bash
git add web/src/app/services/news.service.ts web/src/app/pages/chat.ts web/src/app/pages/search.ts tests/e2e/conftest.py
git commit -m "feat(m6): load topics dynamically from GET /api/topics"
```

---

### Task 5: Layout Width + Polish

Widen the layout from 800px to 1024px.

**Files:**
- Modify: `web/src/app/app.ts:98`

**Step 1: Change layout width**

In `web/src/app/app.ts`, change line 98:

```css
    main.with-nav {
      max-width: 1024px;
```

**Step 2: Build and verify**

Run: `cd web && npx ng build`
Expected: Build succeeds

**Step 3: Run all E2E tests**

Run: `.venv/bin/pytest tests/e2e/ -v --timeout=30`
Expected: All pass

**Step 4: Commit**

```bash
git add web/src/app/app.ts
git commit -m "style(m6): widen layout from 800px to 1024px"
```

---

### Task 6: E2E Test for Topic Filter on Dashboard

Add a Playwright test that verifies the new clickable topic chips work.

**Files:**
- Modify: `tests/e2e/test_dashboard.py`

**Step 1: Add the topic filter test**

Add to `tests/e2e/test_dashboard.py`:

```python
def test_topic_chips_filter_items(authed_page: Page, base_url: str):
    authed_page.goto(base_url + "/dashboard")
    # All 3 items visible initially
    expect(authed_page.locator("app-news-item-card")).to_have_count(3)
    # Click on "modelos" topic chip
    authed_page.locator(".topic-chip", has_text="modelos").click()
    # Only modelos items visible (1 item)
    expect(authed_page.locator("app-news-item-card")).to_have_count(1)
    expect(authed_page.locator("text=New AI Model Released")).to_be_visible()
    # Click again to clear filter
    authed_page.locator(".topic-chip", has_text="modelos").click()
    expect(authed_page.locator("app-news-item-card")).to_have_count(3)
```

**Step 2: Run E2E tests**

Run: `.venv/bin/pytest tests/e2e/test_dashboard.py -v --timeout=30`
Expected: All pass (including new test)

**Step 3: Commit**

```bash
git add tests/e2e/test_dashboard.py
git commit -m "test(m6): add E2E test for dashboard topic chip filter"
```

---

### Task 7: Final Verification

**Step 1: Run ruff**

Run: `.venv/bin/ruff check src/ tests/`
Expected: All checks passed

Run: `.venv/bin/ruff format --check src/ tests/`
Expected: N files already formatted

**Step 2: Run all unit tests**

Run: `.venv/bin/pytest tests/unit/ --timeout=30 -q`
Expected: 637+ passed

**Step 3: Run all E2E tests**

Run: `.venv/bin/pytest tests/e2e/ --timeout=30 -q`
Expected: 35+ passed (34 existing + 1 new topic filter test)

**Step 4: Build Angular**

Run: `cd web && npx ng build`
Expected: Build succeeds

**Step 5: Report final counts**

Report: unit tests, E2E tests, lint status, Angular build status, total test count.

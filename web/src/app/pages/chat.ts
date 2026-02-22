import { Component, inject, signal, ElementRef, ViewChild, AfterViewChecked, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';
import { MatButtonModule } from '@angular/material/button';
import { marked } from 'marked';
import DOMPurify from 'dompurify';
import { AuthService } from '../services/auth.service';
import { NewsService } from '../services/news.service';

interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
  renderedHtml?: string;
  sources?: ChatSource[];
}

interface ChatSource {
  id: string;
  title: string;
  url: string | null;
  topic: string | null;
}

@Component({
  selector: 'app-chat',
  imports: [CommonModule, FormsModule, MatFormFieldModule, MatInputModule, MatSelectModule, MatButtonModule],
  template: `
    <div class="chat-page">
      <div class="chat-messages" #messagesContainer>
        @if (messages().length === 0) {
          <div class="empty-state">
            <h2 class="welcome-title">CHAT CON IA</h2>
            <p class="welcome-sub mono">Pregunta sobre noticias de IA y tecnología</p>
            <div class="suggestions">
              @for (s of suggestions; track s.text) {
                <button type="button" class="suggestion-chip" (click)="askQuestion(s.text)">
                  <span class="chip-label mono">{{ s.label }}</span>
                  <span>{{ s.text }}</span>
                </button>
              }
            </div>
          </div>
        }

        @for (msg of messages(); track $index) {
          <div class="message" [class.user]="msg.role === 'user'" [class.assistant]="msg.role === 'assistant'">
            @if (msg.role === 'assistant') {
              <div class="message-content rendered-markdown" [innerHTML]="msg.renderedHtml"></div>
            } @else {
              <div class="message-content">{{ msg.content }}</div>
            }
            @if (msg.sources && msg.sources.length > 0) {
              <div class="sources">
                <span class="sources-label mono">FUENTES:</span>
                @for (src of msg.sources; track src.id) {
                  @if (src.url) {
                    <a [href]="src.url" target="_blank" rel="noopener" class="source-link mono">{{ src.title }}</a>
                  } @else {
                    <span class="source-link no-url mono">{{ src.title }}</span>
                  }
                }
              </div>
            }
          </div>
        }

        @if (streaming()) {
          <div class="message assistant streaming">
            <div class="message-content">{{ streamBuffer() }}<span class="cursor">|</span></div>
          </div>
        }
      </div>

      <form class="chat-input-form" (ngSubmit)="onSend()">
        <div class="input-row">
          <mat-form-field appearance="outline" class="topic-field">
            <mat-label>Tema</mat-label>
            <mat-select class="topic-filter" [(ngModel)]="selectedTopic" name="topic">
              <mat-option value="">Todos los temas</mat-option>
              @for (t of topics(); track t) {
                <mat-option [value]="t">{{ t }}</mat-option>
              }
            </mat-select>
          </mat-form-field>
          <mat-form-field appearance="outline" class="chat-field">
            <mat-label>Pregunta</mat-label>
            <input
              matInput
              type="text"
              [(ngModel)]="question"
              name="question"
              placeholder="Pregunta sobre noticias de IA..."
              class="chat-input"
              [disabled]="streaming()"
            />
          </mat-form-field>
          <button
            mat-flat-button
            type="submit"
            class="send-btn submit-btn"
            [disabled]="streaming() || !question.trim()"
          >
            ENVIAR
          </button>
        </div>
      </form>
    </div>
  `,
  styles: [`
    :host { display: block; height: calc(100vh - 104px); }

    .chat-page {
      display: flex;
      flex-direction: column;
      height: 100%;
      max-width: 720px;
      margin: 0 auto;
    }

    .chat-messages {
      flex: 1;
      overflow-y: auto;
      padding: 24px 0;
      display: flex;
      flex-direction: column;
      gap: 16px;
    }

    .empty-state {
      text-align: center;
      padding: 80px 24px;
      animation: fade-in 0.5s ease-out both;
    }

    .welcome-title {
      font-family: var(--font-heading);
      font-size: var(--text-xl);
      margin: 0 0 8px;
      font-weight: 700;
      letter-spacing: -0.02em;
      color: var(--text-primary);
    }

    .welcome-sub {
      margin: 0 0 36px;
      font-size: 11px;
      color: var(--text-muted);
      letter-spacing: 0.08em;
      text-transform: uppercase;
    }
    .suggestions {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 10px;
      max-width: 500px;
      margin: 0 auto;
    }

    .suggestion-chip {
      cursor: pointer;
      background: var(--bg-surface);
      color: var(--text-secondary);
      border: 1px solid var(--text-primary);
      padding: 14px 16px;
      font-family: var(--font-body);
      font-size: var(--text-sm);
      text-align: left;
      width: 100%;
      line-height: var(--leading-relaxed);
      transition: background 0.15s ease, color 0.15s ease;
      display: flex;
      flex-direction: column;
      gap: 4px;
    }
    .chip-label {
      font-size: 9px;
      text-transform: uppercase;
      letter-spacing: 0.1em;
      color: var(--accent);
      font-weight: 600;
    }
    .suggestion-chip:hover {
      background: var(--text-primary);
      color: var(--bg-base);
    }
    .suggestion-chip:hover .chip-label {
      color: var(--bg-base);
      opacity: 0.7;
    }

    .message {
      padding: 14px 18px;
      max-width: 82%;
      line-height: var(--leading-relaxed);
      font-size: var(--text-base);
      animation: fade-in 0.3s ease-out both;
      border: 1px solid var(--border);
    }

    .message.user {
      align-self: flex-end;
      background: var(--accent);
      color: #fff;
      border-color: var(--accent);
    }
    :host-context(.dark) .message.user {
      color: #000;
    }

    .message.assistant {
      align-self: flex-start;
      background: var(--bg-elevated);
      color: var(--text-secondary);
    }

    .message-content { word-break: break-word; }

    .cursor {
      animation: blink 0.8s infinite;
      font-weight: bold;
      color: var(--accent);
    }

    .sources {
      margin-top: 12px;
      padding-top: 10px;
      border-top: 1px solid var(--border);
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
      align-items: center;
    }
    .sources-label {
      font-size: 9px;
      font-weight: 600;
      color: var(--text-muted);
      letter-spacing: 0.08em;
    }
    .source-link {
      font-size: 10px;
      padding: 3px 10px;
      background: var(--bg-hover);
      color: var(--text-secondary);
      border: 1px solid var(--border);
      text-decoration: none;
      transition: border-color 0.15s ease;
    }
    .source-link:hover { border-color: var(--accent); }
    .source-link.no-url { color: var(--text-muted); }

    .chat-input-form {
      padding: 16px 0;
      border-top: 1px solid var(--text-primary);
      background: var(--bg-base);
      position: sticky;
      bottom: 0;
    }

    .input-row {
      display: flex;
      gap: 8px;
      align-items: flex-start;
    }
    .topic-field { min-width: 140px; }
    .chat-field { flex: 1; }

    .send-btn {
      height: 56px;
      padding: 0 24px;
      font-family: var(--font-mono);
      font-size: 11px;
      font-weight: 600;
      letter-spacing: 0.08em;
    }

    @media (max-width: 640px) {
      :host { height: calc(100vh - 80px); }
      .suggestions { grid-template-columns: 1fr; }
      .input-row { flex-wrap: wrap; }
      .topic-field { min-width: 100%; }
      .chat-field { min-width: 0; flex: 1; }
      .send-btn { height: 48px; }
      .message { max-width: 92%; }
    }
  `],
})
export class ChatPage implements OnInit, AfterViewChecked {
  private auth = inject(AuthService);
  private newsService = inject(NewsService);

  @ViewChild('messagesContainer') private messagesContainer!: ElementRef;

  messages = signal<ChatMessage[]>([]);
  streaming = signal(false);
  streamBuffer = signal('');
  question = '';
  selectedTopic = '';

  topics = signal<string[]>([]);

  ngOnInit() {
    this.newsService.getTopics().subscribe({
      next: (topics) => this.topics.set(topics),
      error: () => { /* topics load is non-critical */ },
    });
  }

  suggestions = [
    { text: 'Que modelos de IA se lanzaron esta semana?', label: 'MODELOS' },
    { text: 'Cuales son las herramientas open source mas populares?', label: 'TOOLS' },
    { text: 'Que papers de LLMs se publicaron recientemente?', label: 'PAPERS' },
    { text: 'Que noticias hay sobre agentes de IA?', label: 'AGENTES' },
  ];

  renderMarkdown(text: string): string {
    const html = marked.parse(text, { async: false }) as string;
    return DOMPurify.sanitize(html);
  }

  ngAfterViewChecked() {
    if (this.streaming()) {
      this.scrollToBottom();
    }
  }

  askQuestion(q: string) {
    this.question = q;
    this.onSend();
  }

  async onSend(retryCount = 0): Promise<void> {
    const q = this.question.trim();
    if (!q || this.streaming()) return;

    this.messages.update(msgs => [...msgs, { role: 'user', content: q }]);
    this.question = '';
    this.streaming.set(true);
    this.streamBuffer.set('');

    const token = this.auth.getToken();
    const body = {
      question: q,
      topic: this.selectedTopic || null,
      limit: 5,
    };

    try {
      const response = await fetch('/api/chat', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
        },
        body: JSON.stringify(body),
      });

      if (!response.ok) {
        if (response.status === 401 && retryCount === 0) {
          const refreshed = await this.auth.refreshToken();
          if (refreshed) {
            this.question = q;
            this.messages.update(msgs => msgs.slice(0, -1));
            this.streaming.set(false);
            return this.onSend(1);
          }
        }
        throw new Error(`HTTP ${response.status}`);
      }

      if (!response.body) throw new Error('No response body');
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let fullText = '';
      let sources: ChatSource[] = [];
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const parts = buffer.split('\n');
        buffer = parts.pop()!;

        let currentEvent = '';

        for (const line of parts) {
          if (line.startsWith('event: ')) {
            currentEvent = line.slice(7);
            continue;
          }
          if (!line.startsWith('data: ')) continue;
          const data = line.slice(6);

          try {
            const parsed = JSON.parse(data);

            if (currentEvent === 'message') {
              if (parsed.type === 'token' && parsed.content) {
                fullText += parsed.content;
                this.streamBuffer.set(fullText);
              } else if (parsed.type === 'sources' && parsed.content) {
                sources = parsed.content;
              }
            } else if (currentEvent === 'error') {
              const errMsg = parsed.error?.message || 'Error desconocido';
              fullText += errMsg;
              this.streamBuffer.set(fullText);
            }
          } catch {
            // ignore parse errors on partial chunks
          }

          currentEvent = '';
        }
      }

      this.messages.update(msgs => [
        ...msgs,
        { role: 'assistant', content: fullText, renderedHtml: this.renderMarkdown(fullText), sources },
      ]);
    } catch {
      const errorMsg = 'Error al conectar con el servidor. Intenta de nuevo.';
      this.messages.update(msgs => [
        ...msgs,
        { role: 'assistant', content: errorMsg, renderedHtml: this.renderMarkdown(errorMsg) },
      ]);
    } finally {
      this.streaming.set(false);
      this.streamBuffer.set('');
    }
  }

  private scrollToBottom() {
    if (this.messagesContainer) {
      const el = this.messagesContainer.nativeElement;
      el.scrollTop = el.scrollHeight;
    }
  }
}

import { Component, inject, signal, ElementRef, ViewChild, AfterViewChecked, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
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
  imports: [CommonModule, FormsModule, MatFormFieldModule, MatInputModule, MatSelectModule, MatButtonModule, MatIconModule],
  template: `
    <div class="chat-page">
      <div class="chat-messages" #messagesContainer>
        @if (messages().length === 0) {
          <div class="empty-state">
            <div class="welcome-glow"></div>
            <mat-icon class="welcome-icon">auto_awesome</mat-icon>
            <h2 class="gradient-title">Chat con IA</h2>
            <p>Pregunta sobre noticias de IA y tecnologia</p>
            <div class="suggestions">
              <button type="button" class="suggestion-chip" (click)="askQuestion(suggestions[0])">
                <mat-icon class="chip-icon">auto_awesome</mat-icon>
                <span>{{ suggestions[0] }}</span>
              </button>
              <button type="button" class="suggestion-chip" (click)="askQuestion(suggestions[1])">
                <mat-icon class="chip-icon">code</mat-icon>
                <span>{{ suggestions[1] }}</span>
              </button>
              <button type="button" class="suggestion-chip" (click)="askQuestion(suggestions[2])">
                <mat-icon class="chip-icon">description</mat-icon>
                <span>{{ suggestions[2] }}</span>
              </button>
              <button type="button" class="suggestion-chip" (click)="askQuestion(suggestions[3])">
                <mat-icon class="chip-icon">smart_toy</mat-icon>
                <span>{{ suggestions[3] }}</span>
              </button>
            </div>
          </div>
        }

        @for (msg of messages(); track $index) {
          <div class="message" [class.user]="msg.role === 'user'" [class.assistant]="msg.role === 'assistant'">
            @if (msg.role === 'assistant') {
              <div class="message-content" [innerHTML]="msg.renderedHtml"></div>
            } @else {
              <div class="message-content">{{ msg.content }}</div>
            }
            @if (msg.sources && msg.sources.length > 0) {
              <div class="sources">
                <span class="sources-label">Fuentes:</span>
                @for (src of msg.sources; track src.id) {
                  @if (src.url) {
                    <a [href]="src.url" target="_blank" rel="noopener" class="source-link">{{ src.title }}</a>
                  } @else {
                    <span class="source-link no-url">{{ src.title }}</span>
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
            <mat-icon>send</mat-icon>
            Enviar
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
      position: relative;
    }

    .welcome-glow {
      position: absolute;
      top: 40px;
      left: 50%;
      transform: translateX(-50%);
      width: 300px;
      height: 200px;
      background: radial-gradient(ellipse at center, color-mix(in srgb, var(--accent) 8%, transparent), transparent 70%);
      pointer-events: none;
      z-index: 0;
    }

    .welcome-icon {
      font-size: 40px;
      width: 40px;
      height: 40px;
      color: var(--accent);
      margin-bottom: 16px;
      position: relative;
      z-index: 1;
      opacity: 0.8;
    }

    .gradient-title {
      font-family: var(--font-heading);
      font-size: var(--text-xl);
      margin: 0 0 8px;
      font-weight: 800;
      letter-spacing: var(--tracking-tight);
      background: linear-gradient(135deg, var(--accent), #A78BFA);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
      background-clip: text;
      position: relative;
      z-index: 1;
    }

    .empty-state p {
      margin: 0 0 36px;
      font-size: var(--text-base);
      color: var(--text-muted);
      position: relative;
      z-index: 1;
    }

    .suggestions {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 10px;
      max-width: 500px;
      margin: 0 auto;
      position: relative;
      z-index: 1;
    }

    .suggestion-chip {
      cursor: pointer;
      background: var(--bg-elevated);
      color: var(--text-secondary);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 14px 16px;
      font-family: var(--font-body);
      font-size: var(--text-sm);
      font-weight: 400;
      text-align: left;
      width: 100%;
      line-height: var(--leading-relaxed);
      transition: border-color 0.2s ease, background 0.2s ease, transform 0.15s ease, box-shadow 0.2s ease;
      white-space: normal;
      word-break: break-word;
      display: flex;
      align-items: flex-start;
      gap: 10px;
    }

    .chip-icon {
      font-size: 18px;
      width: 18px;
      height: 18px;
      color: var(--accent);
      opacity: 0.6;
      flex-shrink: 0;
      margin-top: 2px;
    }

    .suggestion-chip:hover {
      border-color: var(--accent);
      background: var(--accent-glow);
      color: var(--text-primary);
      transform: translateY(-1px);
      box-shadow: 0 4px 12px rgba(99, 102, 241, 0.1);
    }

    .suggestion-chip:hover .chip-icon {
      opacity: 1;
    }

    .message {
      padding: 14px 18px;
      border-radius: 18px;
      max-width: 82%;
      line-height: var(--leading-relaxed);
      font-size: var(--text-base);
      animation: fade-in 0.3s ease-out both;
    }

    .message.user {
      align-self: flex-end;
      background: var(--accent);
      color: #fff;
      border-bottom-right-radius: 6px;
      white-space: pre-wrap;
    }

    .message.assistant {
      align-self: flex-start;
      background: var(--bg-elevated);
      border: 1px solid var(--border);
      color: var(--text-secondary);
      border-bottom-left-radius: 6px;
    }

    .message-content { word-break: break-word; }
    .message.assistant .message-content :first-child { margin-top: 0; }
    .message.assistant .message-content :last-child { margin-bottom: 0; }
    .message.assistant .message-content p { margin: 0.5em 0; }

    .message.assistant .message-content ul,
    .message.assistant .message-content ol {
      margin: 0.5em 0;
      padding-left: 1.5em;
    }

    .message.assistant .message-content code {
      background: var(--bg-base);
      border: 1px solid var(--border);
      padding: 2px 6px;
      border-radius: 5px;
      font-family: var(--font-mono);
      font-size: 0.85em;
    }

    .message.assistant .message-content pre {
      background: var(--bg-base);
      border: 1px solid var(--border);
      color: var(--text-primary);
      padding: 16px 18px;
      border-radius: 12px;
      overflow-x: auto;
      margin: 0.5em 0;
    }

    .message.assistant .message-content pre code {
      background: none;
      border: none;
      padding: 0;
      color: inherit;
    }

    .message.assistant .message-content strong {
      font-weight: 600;
      color: var(--text-primary);
    }

    .message.assistant .message-content a {
      color: var(--accent);
      text-decoration: none;
    }

    .message.assistant .message-content a:hover {
      text-decoration: underline;
    }

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
      font-size: var(--text-xs);
      font-weight: 600;
      color: var(--text-muted);
      text-transform: uppercase;
      letter-spacing: var(--tracking-wide);
    }

    .source-link {
      font-size: var(--text-sm);
      padding: 3px 10px;
      background: var(--bg-hover);
      color: var(--text-secondary);
      border: 1px solid var(--border);
      border-radius: 6px;
      text-decoration: none;
      transition: border-color 0.15s ease;
    }

    .source-link:hover {
      border-color: var(--accent);
    }

    .source-link.no-url { color: var(--text-muted); }

    .chat-input-form {
      padding: 16px 0;
      border-top: 1px solid var(--border);
      background: color-mix(in srgb, var(--bg-base) 85%, transparent);
      backdrop-filter: blur(12px);
      -webkit-backdrop-filter: blur(12px);
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
      font-size: var(--text-sm);
      font-weight: 600;
      font-family: var(--font-body);
      border-radius: 10px;
      display: flex;
      align-items: center;
      gap: 6px;
    }
    .send-btn mat-icon {
      font-size: 18px;
      width: 18px;
      height: 18px;
    }

    @media (max-width: 640px) {
      :host { height: calc(100vh - 80px); }
      .suggestions { grid-template-columns: 1fr; }
      .welcome-glow { width: 200px; height: 150px; }
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
      error: () => {},
    });
  }

  suggestions = [
    'Que modelos de IA se lanzaron esta semana?',
    'Cuales son las herramientas open source mas populares?',
    'Que papers de LLMs se publicaron recientemente?',
    'Que noticias hay sobre agentes de IA?',
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

  async onSend() {
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
        throw new Error(`HTTP ${response.status}`);
      }

      const reader = response.body!.getReader();
      const decoder = new TextDecoder();
      let fullText = '';
      let sources: ChatSource[] = [];
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const parts = buffer.split('\n');
        buffer = parts.pop()!; // keep incomplete last line

        for (const line of parts) {
          if (!line.startsWith('data: ')) continue;
          const data = line.slice(6);

          if (data === '[DONE]') continue;

          try {
            const parsed = JSON.parse(data);
            if (parsed.token) {
              fullText += parsed.token;
              this.streamBuffer.set(fullText);
            }
            if (parsed.sources) {
              sources = parsed.sources;
            }
            if (parsed.error) {
              fullText += parsed.error;
              this.streamBuffer.set(fullText);
            }
          } catch {
            // ignore parse errors on partial chunks
          }
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

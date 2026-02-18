import { Component, inject, signal, ElementRef, ViewChild, AfterViewChecked, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
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
  imports: [CommonModule, FormsModule],
  template: `
    <div class="chat-page">
      <div class="chat-messages" #messagesContainer>
        @if (messages().length === 0) {
          <div class="empty-state">
            <h2>Chat con IA</h2>
            <p>Pregunta sobre noticias de IA y tecnologia</p>
            <div class="suggestions">
              @for (s of suggestions; track s) {
                <button class="suggestion-chip" (click)="askQuestion(s)">{{ s }}</button>
              }
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
          <select class="topic-filter" [(ngModel)]="selectedTopic" name="topic">
            <option value="">Todos los temas</option>
            @for (t of topics(); track t) {
              <option [value]="t">{{ t }}</option>
            }
          </select>
          <input
            type="text"
            [(ngModel)]="question"
            name="question"
            placeholder="Pregunta sobre noticias de IA..."
            class="chat-input"
            [disabled]="streaming()"
          />
          <button
            type="submit"
            class="send-btn"
            [disabled]="streaming() || !question.trim()"
          >
            Enviar
          </button>
        </div>
      </form>
    </div>
  `,
  styles: [`
    :host { display: block; height: calc(100vh - 92px); }

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
    }
    .empty-state h2 {
      font-size: 1.75rem;
      color: #1d1d1f;
      margin: 0 0 8px;
      font-weight: 700;
      letter-spacing: -0.02em;
    }
    .empty-state p {
      margin: 0 0 32px;
      font-size: 0.9375rem;
      color: #86868b;
    }
    .suggestions {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      justify-content: center;
    }
    .suggestion-chip {
      padding: 10px 18px;
      border: 1px solid #d2d2d7;
      border-radius: 980px;
      background: white;
      color: #1d1d1f;
      font-size: 0.8125rem;
      cursor: pointer;
      transition: all 0.2s;
    }
    .suggestion-chip:hover {
      border-color: #0071e3;
      color: #0071e3;
      background: #f5f5f7;
    }

    .message {
      padding: 14px 18px;
      border-radius: 18px;
      max-width: 82%;
      line-height: 1.6;
      font-size: 0.9375rem;
    }
    .message.user {
      align-self: flex-end;
      background: #0071e3;
      color: white;
      border-bottom-right-radius: 6px;
      white-space: pre-wrap;
    }
    .message.assistant {
      align-self: flex-start;
      background: #f5f5f7;
      color: #1d1d1f;
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
      background: #e8e8ed;
      padding: 2px 5px;
      border-radius: 4px;
      font-size: 0.85em;
    }
    .message.assistant .message-content pre {
      background: #1d1d1f;
      color: #f5f5f7;
      padding: 14px 16px;
      border-radius: 10px;
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
      color: #0071e3;
      text-decoration: none;
    }
    .message.assistant .message-content a:hover { text-decoration: underline; }

    .cursor {
      animation: blink 0.8s infinite;
      font-weight: bold;
      color: #86868b;
    }
    @keyframes blink {
      0%, 100% { opacity: 1; }
      50% { opacity: 0; }
    }

    .sources {
      margin-top: 12px;
      padding-top: 10px;
      border-top: 1px solid #e8e8ed;
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
      align-items: center;
    }
    .sources-label {
      font-size: 0.6875rem;
      font-weight: 600;
      color: #86868b;
      text-transform: uppercase;
      letter-spacing: 0.04em;
    }
    .source-link {
      font-size: 0.8125rem;
      padding: 3px 10px;
      background: #e8e8ed;
      color: #1d1d1f;
      border-radius: 6px;
      text-decoration: none;
      transition: background 0.15s;
    }
    .source-link:hover { background: #d2d2d7; }
    .source-link.no-url { color: #6e6e73; }

    .chat-input-form {
      padding: 14px 0;
      border-top: 1px solid #e8e8ed;
    }
    .input-row {
      display: flex;
      gap: 8px;
      align-items: center;
    }
    .topic-filter {
      padding: 10px 12px;
      border: 1px solid #d2d2d7;
      border-radius: 10px;
      font-size: 0.8125rem;
      outline: none;
      min-width: 120px;
      color: #1d1d1f;
      transition: border-color 0.2s, box-shadow 0.2s;
    }
    .topic-filter:focus {
      border-color: #0071e3;
      box-shadow: 0 0 0 4px rgba(0, 113, 227, 0.12);
    }
    .chat-input {
      flex: 1;
      padding: 10px 16px;
      border: 1px solid #d2d2d7;
      border-radius: 10px;
      font-size: 0.9375rem;
      outline: none;
      color: #1d1d1f;
      transition: border-color 0.2s, box-shadow 0.2s;
    }
    .chat-input:focus {
      border-color: #0071e3;
      box-shadow: 0 0 0 4px rgba(0, 113, 227, 0.12);
    }
    .send-btn {
      padding: 10px 20px;
      background: #0071e3;
      color: white;
      border: none;
      border-radius: 980px;
      font-size: 0.875rem;
      font-weight: 500;
      cursor: pointer;
      white-space: nowrap;
      transition: background 0.2s;
    }
    .send-btn:hover:not(:disabled) { background: #0077ED; }
    .send-btn:disabled { opacity: 0.42; cursor: default; }

    @media (max-width: 640px) {
      :host { height: calc(100vh - 76px); }
      .input-row { flex-wrap: wrap; }
      .topic-filter { min-width: 100%; }
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

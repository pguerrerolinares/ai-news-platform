import { Component, inject, signal, ElementRef, ViewChild, AfterViewChecked } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { marked } from 'marked';
import DOMPurify from 'dompurify';
import { AuthService } from '../services/auth.service';

interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
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
            <div class="message-content" [innerHTML]="renderMarkdown(msg.content)"></div>
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
            @for (t of topics; track t) {
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
      max-width: 800px;
      margin: 0 auto;
    }

    .chat-messages {
      flex: 1;
      overflow-y: auto;
      padding: 20px 0;
      display: flex;
      flex-direction: column;
      gap: 16px;
    }

    .empty-state {
      text-align: center;
      padding: 60px 20px;
      color: #64748b;
    }
    .empty-state h2 {
      font-size: 1.5rem;
      color: #1e293b;
      margin: 0 0 8px;
    }
    .empty-state p {
      margin: 0 0 24px;
      font-size: 0.95rem;
    }
    .suggestions {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      justify-content: center;
    }
    .suggestion-chip {
      padding: 8px 16px;
      border: 1px solid #e2e8f0;
      border-radius: 20px;
      background: white;
      color: #475569;
      font-size: 0.85rem;
      cursor: pointer;
      transition: all 0.15s;
    }
    .suggestion-chip:hover {
      border-color: #2563eb;
      color: #2563eb;
      background: #eff6ff;
    }

    .message {
      padding: 12px 16px;
      border-radius: 12px;
      max-width: 85%;
      line-height: 1.6;
      font-size: 0.95rem;
    }
    .message.user {
      align-self: flex-end;
      background: #2563eb;
      color: white;
      border-bottom-right-radius: 4px;
      white-space: pre-wrap;
    }
    .message.assistant {
      align-self: flex-start;
      background: #f1f5f9;
      color: #1e293b;
      border-bottom-left-radius: 4px;
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

    .cursor {
      animation: blink 0.8s infinite;
      font-weight: bold;
    }
    @keyframes blink {
      0%, 100% { opacity: 1; }
      50% { opacity: 0; }
    }

    .sources {
      margin-top: 10px;
      padding-top: 8px;
      border-top: 1px solid #e2e8f0;
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
      align-items: center;
    }
    .sources-label {
      font-size: 0.75rem;
      font-weight: 600;
      color: #64748b;
      text-transform: uppercase;
    }
    .source-link {
      font-size: 0.8rem;
      padding: 2px 8px;
      background: #dbeafe;
      color: #1e40af;
      border-radius: 4px;
      text-decoration: none;
    }
    .source-link:hover { background: #bfdbfe; }
    .source-link.no-url { color: #475569; background: #e2e8f0; }

    .chat-input-form {
      padding: 12px 0;
      border-top: 1px solid #e2e8f0;
    }
    .input-row {
      display: flex;
      gap: 8px;
    }
    .topic-filter {
      padding: 10px;
      border: 1px solid #e2e8f0;
      border-radius: 6px;
      font-size: 0.85rem;
      outline: none;
      min-width: 120px;
    }
    .chat-input {
      flex: 1;
      padding: 10px 14px;
      border: 1px solid #e2e8f0;
      border-radius: 6px;
      font-size: 0.95rem;
      outline: none;
    }
    .chat-input:focus {
      border-color: #2563eb;
      box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.1);
    }
    .send-btn {
      padding: 10px 20px;
      background: #2563eb;
      color: white;
      border: none;
      border-radius: 6px;
      font-size: 0.9rem;
      font-weight: 600;
      cursor: pointer;
      white-space: nowrap;
    }
    .send-btn:hover:not(:disabled) { background: #1d4ed8; }
    .send-btn:disabled { opacity: 0.6; cursor: not-allowed; }

    @media (max-width: 640px) {
      :host { height: calc(100vh - 80px); }
      .input-row { flex-wrap: wrap; }
      .topic-filter { min-width: 100%; }
      .message { max-width: 95%; }
    }
  `],
})
export class ChatPage implements AfterViewChecked {
  private auth = inject(AuthService);

  @ViewChild('messagesContainer') private messagesContainer!: ElementRef;

  messages = signal<ChatMessage[]>([]);
  streaming = signal(false);
  streamBuffer = signal('');
  question = '';
  selectedTopic = '';

  topics = ['modelos', 'herramientas', 'papers', 'productos', 'open_source', 'agentes', 'regulacion'];

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
        { role: 'assistant', content: fullText, sources },
      ]);
    } catch {
      this.messages.update(msgs => [
        ...msgs,
        { role: 'assistant', content: 'Error al conectar con el servidor. Intenta de nuevo.' },
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

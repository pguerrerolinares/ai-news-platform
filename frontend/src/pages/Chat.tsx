import { useState, useRef, useEffect } from 'react'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { IconSend } from '@tabler/icons-react'

interface Message {
  role: 'user' | 'assistant'
  content: string
}

const MOCK_RESPONSES: Record<string, string> = {
  default:
    'Basandome en las noticias de hoy, puedo decirte que el mundo de la IA sigue en constante movimiento. Hay avances importantes en modelos open-source, nuevas herramientas de desarrollo, y cambios regulatorios tanto en Europa como en Asia. Quieres que profundice en algun tema en particular?',
  llm: 'Hoy hay varias noticias sobre LLMs: DeepSeek R2 supera a GPT-4o en razonamiento matematico, Anthropic lanza Claude 3.5 Haiku con 200K tokens de contexto, y Phi-4 de Microsoft logra estado del arte en matematicas con solo 14B parametros. El trend principal es que los modelos mas pequeños estan cerrando la brecha con los grandes.',
  trending:
    'Las noticias con mas traccion hoy son: Mixtral 8x22B open-source (2,341 puntos), Llama 3.2 multimodal (2,891 puntos), DeepSeek R2 (1,847 puntos), y Gemini 2.0 Ultra (1,243 puntos). El tema dominante es el avance de modelos open-source que compiten con los cerrados.',
  herramientas:
    'En herramientas destacan: LangGraph 0.3 con soporte multi-modal, Ollama 0.7 con cuantizacion de 2 bits, Hugging Face Inference Endpoints con cuantizacion dinamica, y DSPy alcanzando 10K estrellas. La tendencia es hacer modelos mas accesibles y faciles de desplegar.',
}

const SUGGESTIONS = [
  'Que noticias hay de LLMs?',
  'Resume el trending de hoy',
  'Que herramientas nuevas hay?',
]

function getMockResponse(input: string): string {
  const q = input.toLowerCase()
  if (q.includes('llm') || q.includes('modelo')) return MOCK_RESPONSES.llm
  if (q.includes('trending') || q.includes('movimiento')) return MOCK_RESPONSES.trending
  if (q.includes('herramienta') || q.includes('tool')) return MOCK_RESPONSES.herramientas
  return MOCK_RESPONSES.default
}

export default function Chat() {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [isTyping, setIsTyping] = useState(false)
  const scrollRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [messages, isTyping])

  function send(text: string) {
    if (!text.trim()) return
    const userMsg: Message = { role: 'user', content: text.trim() }
    setMessages(prev => [...prev, userMsg])
    setInput('')
    setIsTyping(true)

    setTimeout(() => {
      const assistantMsg: Message = {
        role: 'assistant',
        content: getMockResponse(text),
      }
      setMessages(prev => [...prev, assistantMsg])
      setIsTyping(false)
    }, 500)
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      send(input)
    }
  }

  return (
    <div className="flex h-[calc(100vh-5rem)] flex-col">
      {/* Messages */}
      <ScrollArea className="flex-1" ref={scrollRef}>
        <div className="mx-auto max-w-3xl space-y-4 p-4">
          {messages.length === 0 && !isTyping && (
            <div className="flex flex-col items-center gap-6 pt-24 text-center">
              <div>
                <h2 className="text-2xl font-bold tracking-tight">Chat IA</h2>
                <p className="text-sm text-muted-foreground">
                  Pregunta sobre las noticias de IA de hoy
                </p>
              </div>
              <div className="flex flex-wrap justify-center gap-2">
                {SUGGESTIONS.map(s => (
                  <Button
                    key={s}
                    variant="outline"
                    size="sm"
                    onClick={() => send(s)}
                  >
                    {s}
                  </Button>
                ))}
              </div>
            </div>
          )}

          {messages.map((msg, i) => (
            <div
              key={i}
              className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
            >
              <div
                className={`max-w-[80%] rounded-2xl px-4 py-2.5 text-sm leading-relaxed ${
                  msg.role === 'user'
                    ? 'bg-primary text-primary-foreground'
                    : 'bg-muted'
                }`}
              >
                {msg.content}
              </div>
            </div>
          ))}

          {isTyping && (
            <div className="flex justify-start">
              <div className="rounded-2xl bg-muted px-4 py-2.5 text-sm text-muted-foreground">
                Escribiendo...
              </div>
            </div>
          )}
        </div>
      </ScrollArea>

      {/* Input bar */}
      <div className="border-t bg-background p-4">
        <div className="mx-auto flex max-w-3xl items-end gap-2">
          <Textarea
            placeholder="Escribe tu pregunta..."
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            rows={1}
            className="min-h-10 max-h-32 resize-none"
          />
          <Button
            size="icon"
            onClick={() => send(input)}
            disabled={!input.trim() || isTyping}
          >
            <IconSend className="size-4" />
            <span className="sr-only">Enviar</span>
          </Button>
        </div>
      </div>
    </div>
  )
}

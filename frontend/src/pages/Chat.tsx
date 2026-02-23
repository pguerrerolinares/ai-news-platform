import { useState, useRef, useEffect, useCallback } from 'react'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { IconSend } from '@tabler/icons-react'
import { motion, AnimatePresence } from 'motion/react'
import { useReducedMotion } from '@/hooks/use-reduced-motion'

interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
}

let nextId = 0
function msgId() {
  return `msg-${++nextId}`
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

const chipContainer = {
  hidden: {},
  show: { transition: { staggerChildren: 0.08 } },
}

const chipItem = {
  hidden: { opacity: 0, y: 10 },
  show: { opacity: 1, y: 0, transition: { duration: 0.2, ease: 'easeOut' as const } },
}

export default function Chat() {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [isTyping, setIsTyping] = useState(false)
  const bottomRef = useRef<HTMLDivElement>(null)
  const reduced = useReducedMotion()

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, isTyping])

  const send = useCallback((text: string) => {
    if (!text.trim()) return
    const userMsg: Message = { id: msgId(), role: 'user', content: text.trim() }
    setMessages(prev => [...prev, userMsg])
    setInput('')
    setIsTyping(true)

    setTimeout(() => {
      const assistantMsg: Message = {
        id: msgId(),
        role: 'assistant',
        content: getMockResponse(text),
      }
      setMessages(prev => [...prev, assistantMsg])
      setIsTyping(false)
    }, 500)
  }, [])

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      send(input)
    }
  }

  return (
    <div className="flex h-[calc(100vh-5rem)] flex-col">
      {/* Messages */}
      <ScrollArea className="flex-1">
        <div className="mx-auto max-w-3xl space-y-4 p-4">
          <AnimatePresence>
            {messages.length === 0 && !isTyping && (
              <motion.div
                key="empty"
                initial={reduced ? false : { opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={reduced ? undefined : { opacity: 0 }}
                className="flex flex-col items-center gap-6 pt-24 text-center"
              >
                <div>
                  <h2 className="text-2xl font-bold tracking-tight">Chat IA</h2>
                  <p className="text-sm text-muted-foreground">
                    Pregunta sobre las noticias de IA de hoy
                  </p>
                </div>
                <motion.div
                  className="flex flex-wrap justify-center gap-2"
                  variants={chipContainer}
                  initial="hidden"
                  animate="show"
                >
                  {SUGGESTIONS.map(s => (
                    <motion.div key={s} variants={chipItem}>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => send(s)}
                      >
                        {s}
                      </Button>
                    </motion.div>
                  ))}
                </motion.div>
              </motion.div>
            )}
          </AnimatePresence>

          {messages.map(msg => (
            <motion.div
              key={msg.id}
              initial={reduced ? false : {
                opacity: 0,
                x: msg.role === 'user' ? 20 : -20,
              }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ duration: 0.2, ease: 'easeOut' as const }}
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
            </motion.div>
          ))}

          <AnimatePresence>
            {isTyping && (
              <motion.div
                key="typing"
                initial={reduced ? false : { opacity: 0, x: -20 }}
                animate={{ opacity: 1, x: 0 }}
                exit={reduced ? undefined : { opacity: 0 }}
                className="flex justify-start"
              >
                <div className="flex items-center gap-1.5 rounded-2xl bg-muted px-4 py-3">
                  {[0, 1, 2].map(i => (
                    <motion.span
                      key={i}
                      className="size-1.5 rounded-full bg-muted-foreground"
                      animate={reduced ? undefined : { scale: [1, 1.4, 1] }}
                      transition={{ duration: 0.6, repeat: Infinity, delay: i * 0.15 }}
                    />
                  ))}
                </div>
              </motion.div>
            )}
          </AnimatePresence>

          <div ref={bottomRef} />
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
            aria-label="Escribe tu pregunta"
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

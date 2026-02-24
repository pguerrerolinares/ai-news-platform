import { useState, useRef, useEffect, useCallback } from 'react'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { IconSend } from '@tabler/icons-react'
import { motion, AnimatePresence } from 'motion/react'
import { useReducedMotion } from '@/hooks/use-reduced-motion'
import { apiStream } from '@/lib/api'

interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
}

let nextId = 0
function msgId() {
  return `msg-${++nextId}`
}

const SUGGESTIONS = [
  'Que noticias hay de LLMs?',
  'Resume el trending de hoy',
  'Que herramientas nuevas hay?',
]

const chipContainer = {
  hidden: {},
  show: { transition: { staggerChildren: 0.08 } },
}

const chipItem = {
  hidden: { opacity: 0, y: 10 },
  show: { opacity: 1, y: 0, transition: { duration: 0.2, ease: 'easeOut' } },
} as const

async function parseSSE(
  response: Response,
  onToken: (text: string) => void,
  onError: (message: string) => void,
  onDone: () => void,
) {
  const reader = response.body?.getReader()
  if (!reader) { onError('No response body'); return }

  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break

    buffer += decoder.decode(value, { stream: true })
    const lines = buffer.split('\n')
    buffer = lines.pop() ?? ''

    let currentEvent = ''
    for (const line of lines) {
      if (line.startsWith('event: ')) {
        currentEvent = line.slice(7).trim()
      } else if (line.startsWith('data: ')) {
        const data = line.slice(6)
        try {
          const parsed = JSON.parse(data)
          if (currentEvent === 'message') {
            if (parsed.type === 'token' && parsed.content) {
              onToken(parsed.content)
            }
          } else if (currentEvent === 'error') {
            onError(parsed.error?.message ?? 'Error del servidor')
          } else if (currentEvent === 'done') {
            onDone()
          }
        } catch {
          // ignore malformed JSON
        }
        currentEvent = ''
      }
    }
  }
  onDone()
}

export default function Chat() {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [isStreaming, setIsStreaming] = useState(false)
  const bottomRef = useRef<HTMLDivElement>(null)
  const reduced = useReducedMotion()

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, isStreaming])

  const send = useCallback(async (text: string) => {
    if (!text.trim() || isStreaming) return
    const userMsg: Message = { id: msgId(), role: 'user', content: text.trim() }
    const assistantId = msgId()
    setMessages(prev => [...prev, userMsg])
    setInput('')
    setIsStreaming(true)

    // Add empty assistant message that will be filled by streaming
    setMessages(prev => [...prev, { id: assistantId, role: 'assistant', content: '' }])

    try {
      const response = await apiStream('/api/chat', { question: text.trim() })
      await parseSSE(
        response,
        (token) => {
          setMessages(prev =>
            prev.map(m => m.id === assistantId ? { ...m, content: m.content + token } : m)
          )
        },
        (errorMsg) => {
          setMessages(prev =>
            prev.map(m => m.id === assistantId ? { ...m, content: `Error: ${errorMsg}` } : m)
          )
        },
        () => {
          setIsStreaming(false)
        },
      )
    } catch (err) {
      setMessages(prev =>
        prev.map(m => m.id === assistantId
          ? { ...m, content: `Error: ${err instanceof Error ? err.message : 'No se pudo conectar'}` }
          : m
        )
      )
      setIsStreaming(false)
    }
  }, [isStreaming])

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      send(input)
    }
  }

  return (
    <div className="flex h-[calc(100vh-5rem)] flex-col">
      <ScrollArea className="flex-1">
        <div className="mx-auto max-w-3xl space-y-4 p-4">
          <AnimatePresence>
            {messages.length === 0 && !isStreaming && (
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
              transition={{ duration: 0.2, ease: 'easeOut' }}
              className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
            >
              <div
                className={`max-w-[80%] rounded-2xl px-4 py-2.5 text-sm leading-relaxed ${
                  msg.role === 'user'
                    ? 'bg-primary text-primary-foreground'
                    : 'bg-muted'
                }`}
              >
                {msg.content || (isStreaming ? '...' : '')}
              </div>
            </motion.div>
          ))}

          <div ref={bottomRef} />
        </div>
      </ScrollArea>

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
            disabled={!input.trim() || isStreaming}
          >
            <IconSend className="size-4" />
            <span className="sr-only">Enviar</span>
          </Button>
        </div>
      </div>
    </div>
  )
}

import { useEffect, useRef, useState, useCallback } from 'react'
import { useStore, type Message } from '../store'
import { streamChat } from '../lib/api'
import MessageBubble from './MessageBubble'
import ModelSelector from './ModelSelector'
import { Send, Square, Wrench, PanelLeft, Brain, Zap } from 'lucide-react'
import { cn } from '../lib/utils'

export default function ChatView() {
  const {
    getActiveSession, addMessage, updateMessage,
    updateSessionTitle, settings, setSidebarOpen, sidebarOpen,
  } = useStore()

  const session = getActiveSession()
  const [input, setInput] = useState('')
  const [isStreaming, setIsStreaming] = useState(false)
  const [thinkingStep, setThinkingStep] = useState<string | null>(null)
  const [thinking, setThinking] = useState(false)
  const [lastUsage, setLastUsage] = useState<{ tokens: number; cost: number } | null>(null)
  const abortRef = useRef<AbortController | null>(null)
  const bottomRef = useRef<HTMLDivElement>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  // Keep a ref to the latest session so callbacks always see fresh state
  const sessionRef = useRef(session)
  sessionRef.current = session

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [session?.messages.length, session?.messages[session?.messages.length - 1]?.content])

  useEffect(() => {
    const ta = textareaRef.current
    if (!ta) return
    ta.style.height = 'auto'
    ta.style.height = Math.min(ta.scrollHeight, 200) + 'px'
  }, [input])

  const send = useCallback(async () => {
    if (!input.trim() || !session || isStreaming) return

    const userMsg: Message = {
      id: crypto.randomUUID(),
      role: 'user',
      content: input.trim(),
      timestamp: Date.now(),
    }

    addMessage(session.id, userMsg)
    setInput('')
    setThinkingStep(null)

    if (session.messages.length === 0) {
      updateSessionTitle(session.id, input.trim().slice(0, 40))
    }

    const assistantId = crypto.randomUUID()
    addMessage(session.id, {
      id: assistantId,
      role: 'assistant',
      content: '',
      timestamp: Date.now(),
      isStreaming: true,
      toolCalls: [],
      toolResults: [],
      thinkingSteps: [],
    })

    setIsStreaming(true)
    abortRef.current = new AbortController()

    const history = [
      ...session.messages.map((m) => ({ role: m.role, content: m.content })),
      { role: 'user', content: userMsg.content },
    ]

    let accContent = ''

    await streamChat(
      {
        model: session.model,
        messages: history,
        temperature: settings.temperature,
        max_tokens: settings.maxTokens,
        use_tools: settings.useTools,
        stream: true,
        session_id: session.id,
        thinking,
      },
      {
        onToken: (token) => {
          accContent += token
          updateMessage(session.id, assistantId, { content: accContent })
        },
        onToolCall: (name, args) => {
          setThinkingStep('Using tool: ' + name)
          const cur = sessionRef.current?.messages.find((m) => m.id === assistantId)
          updateMessage(session.id, assistantId, {
            toolCalls: [...(cur?.toolCalls ?? []), { name, args }],
          })
        },
        onToolResult: (name, result) => {
          setThinkingStep(null)
          const cur = sessionRef.current?.messages.find((m) => m.id === assistantId)
          updateMessage(session.id, assistantId, {
            toolResults: [...(cur?.toolResults ?? []), { name, result }],
          })
        },
        onThinking: (step) => {
          setThinkingStep(step)
          const cur = sessionRef.current?.messages.find((m) => m.id === assistantId)
          updateMessage(session.id, assistantId, {
            thinkingSteps: [...(cur?.thinkingSteps ?? []), step],
          })
        },
        onDone: () => {
          setThinkingStep(null)
          updateMessage(session.id, assistantId, { isStreaming: false })
          setIsStreaming(false)
        },
        onError: (err) => {
          setThinkingStep(null)
          updateMessage(session.id, assistantId, {
            content: accContent ? accContent + '\n\n---\n**Error:** ' + err : '**Error:** ' + err,
            isStreaming: false,
          })
          setIsStreaming(false)
        },
        onUsage: (tokens, cost) => {
          setLastUsage({ tokens, cost })
        },
        onExport: (content, filename) => {
          const blob = new Blob([content], { type: 'text/markdown' })
          const url = URL.createObjectURL(blob)
          const a = document.createElement('a')
          a.href = url; a.download = filename; a.click()
          URL.revokeObjectURL(url)
        },
        onFailover: (from, to) => {
          console.warn('[OpenClaw] failover:', from, '->', to)
        },
        signal: abortRef.current.signal,
      }
    )
  }, [input, session, isStreaming, addMessage, updateMessage, updateSessionTitle, settings])

  const stop = () => {
    abortRef.current?.abort()
    setThinkingStep(null)
    setIsStreaming(false)
    if (session) {
      const last = session.messages[session.messages.length - 1]
      if (last?.isStreaming) updateMessage(session.id, last.id, { isStreaming: false })
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send() }
  }

  if (!session) {
    return (
      <div className="flex-1 flex items-center justify-center text-muted-foreground">
        <p className="text-sm">Select or create a chat to get started</p>
      </div>
    )
  }

  return (
    <div className="flex flex-col h-full">
      {/* Topbar */}
      <div className="flex items-center gap-2 px-4 py-2.5 border-b border-border drag-region">
        {!sidebarOpen && (
          <button onClick={() => setSidebarOpen(true)} className="no-drag p-1.5 rounded-lg hover:bg-secondary transition-colors">
            <PanelLeft size={15} className="text-muted-foreground" />
          </button>
        )}
        <div className="flex-1 no-drag">
          <ModelSelector sessionId={session.id} currentModel={session.model} />
        </div>
        <div className="flex items-center gap-1 no-drag">
          {settings.useTools && (
            <span className="flex items-center gap-1 text-xs text-muted-foreground bg-secondary px-2 py-1 rounded-full">
              <Wrench size={10} /> Tools on
            </span>
          )}
          <button
            onClick={() => setThinking(!thinking)}
            title="Extended thinking mode"
            className={cn(
              'flex items-center gap-1 text-xs px-2 py-1 rounded-full transition-colors',
              thinking ? 'bg-primary/20 text-primary' : 'bg-secondary text-muted-foreground hover:text-foreground'
            )}
          >
            <Brain size={10} /> {thinking ? 'Thinking on' : 'Think'}
          </button>
          {lastUsage && (
            <span className="flex items-center gap-1 text-xs text-muted-foreground/60 px-1" title={`$${lastUsage.cost.toFixed(5)}`}>
              <Zap size={9} /> {lastUsage.tokens.toLocaleString()}t
            </span>
          )}
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto">
        {session.messages.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full gap-4 text-center px-4">
            <div className="w-16 h-16 rounded-2xl bg-primary/10 flex items-center justify-center">
              <span className="text-3xl">🦀</span>
            </div>
            <div>
              <h2 className="text-lg font-semibold text-foreground">ClosedClaw</h2>
              <p className="text-sm text-muted-foreground mt-1">Your local AI agent. Ask anything, use tools, research the web.</p>
            </div>
            <div className="grid grid-cols-2 gap-2 max-w-md w-full mt-2">
              {SUGGESTIONS.map((s) => (
                <button key={s} onClick={() => setInput(s)}
                  className="text-left text-xs px-3 py-2.5 rounded-lg border border-border hover:border-primary/50 hover:bg-primary/5 text-muted-foreground hover:text-foreground transition-all">
                  {s}
                </button>
              ))}
            </div>
          </div>
        ) : (
          <div className="max-w-3xl mx-auto px-4 py-6 space-y-1">
            {session.messages.map((msg) => (
              <MessageBubble key={msg.id} message={msg} />
            ))}
            {/* Live thinking indicator */}
            {isStreaming && thinkingStep && (
              <div className="flex items-center gap-2 px-3 py-2 text-xs text-muted-foreground">
                <span className="flex gap-0.5">
                  <span className="w-1 h-1 rounded-full bg-primary animate-bounce" style={{ animationDelay: '0ms' }} />
                  <span className="w-1 h-1 rounded-full bg-primary animate-bounce" style={{ animationDelay: '150ms' }} />
                  <span className="w-1 h-1 rounded-full bg-primary animate-bounce" style={{ animationDelay: '300ms' }} />
                </span>
                {thinkingStep}
              </div>
            )}
            {isStreaming && !thinkingStep && (
              <div className="flex items-center gap-2 px-3 py-2 text-xs text-muted-foreground">
                <span className="flex gap-0.5">
                  <span className="w-1 h-1 rounded-full bg-primary animate-bounce" style={{ animationDelay: '0ms' }} />
                  <span className="w-1 h-1 rounded-full bg-primary animate-bounce" style={{ animationDelay: '150ms' }} />
                  <span className="w-1 h-1 rounded-full bg-primary animate-bounce" style={{ animationDelay: '300ms' }} />
                </span>
                Thinking…
              </div>
            )}
            <div ref={bottomRef} />
          </div>
        )}
      </div>

      {/* Input */}
      <div className="border-t border-border p-4">
        <div className="max-w-3xl mx-auto">
          <div className={cn(
            'flex items-end gap-2 rounded-xl border bg-card px-3 py-2 transition-colors',
            isStreaming ? 'border-primary/30' : 'border-border focus-within:border-primary/50'
          )}>
            <textarea ref={textareaRef} value={input} onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Message OpenClaw… (/ for commands, Shift+Enter for newline)"
              rows={1} disabled={isStreaming}
              className="flex-1 bg-transparent text-sm text-foreground placeholder:text-muted-foreground resize-none outline-none py-1 max-h-48"
            />
            <button onClick={isStreaming ? stop : send}
              disabled={!isStreaming && !input.trim()}
              className={cn('shrink-0 p-2 rounded-lg transition-colors',
                isStreaming ? 'bg-destructive/20 hover:bg-destructive/30 text-destructive'
                  : input.trim() ? 'bg-primary hover:bg-primary/90 text-primary-foreground'
                  : 'bg-secondary text-muted-foreground cursor-not-allowed'
              )}>
              {isStreaming ? <Square size={15} /> : <Send size={15} />}
            </button>
          </div>
          <p className="text-xs text-muted-foreground text-center mt-2">
            ClosedClaw can make mistakes. Verify important information.
          </p>
        </div>
      </div>
    </div>
  )
}

const SUGGESTIONS = [
  'List files on my Desktop',
  'Search the web for latest AI news',
  'Open WhatsApp',
  '/status — show session info',
]

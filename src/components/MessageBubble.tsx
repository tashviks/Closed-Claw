import { useState } from 'react'
import ReactMarkdown from 'react-markdown'
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter'
import { oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism'
import { type Message } from '../store'
import { cn, formatTime } from '../lib/utils'
import { ChevronDown, ChevronRight, Copy, Check, Wrench, Globe } from 'lucide-react'

interface Props {
  message: Message
}

export default function MessageBubble({ message }: Props) {
  const [copied, setCopied] = useState(false)
  const [toolsExpanded, setToolsExpanded] = useState(false)

  const copy = async () => {
    await navigator.clipboard.writeText(message.content)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  const isUser = message.role === 'user'
  const hasTools = (message.toolCalls?.length ?? 0) > 0

  return (
    <div className={cn('group flex gap-3 py-3', isUser ? 'flex-row-reverse' : 'flex-row')}>
      {/* Avatar */}
      <div className={cn(
        'shrink-0 w-7 h-7 rounded-lg flex items-center justify-center text-xs font-medium mt-0.5',
        isUser ? 'bg-primary/20 text-primary' : 'bg-secondary text-foreground'
      )}>
        {isUser ? 'U' : '🦀'}
      </div>

      <div className={cn('flex flex-col gap-1 max-w-[85%]', isUser ? 'items-end' : 'items-start')}>
        {/* Tool calls indicator */}
        {hasTools && (
          <button
            onClick={() => setToolsExpanded(!toolsExpanded)}
            className="flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground bg-secondary/50 px-2.5 py-1.5 rounded-lg border border-border transition-colors"
          >
            <Wrench size={11} />
            <span>{message.toolCalls!.length} tool{message.toolCalls!.length > 1 ? 's' : ''} used</span>
            {toolsExpanded ? <ChevronDown size={11} /> : <ChevronRight size={11} />}
          </button>
        )}

        {/* Tool details */}
        {toolsExpanded && hasTools && (
          <div className="w-full space-y-2">
            {message.toolCalls!.map((tc, i) => {
              const result = message.toolResults?.find((r) => r.name === tc.name)
              return (
                <div key={i} className="rounded-lg border border-border bg-card overflow-hidden text-xs">
                  <div className="flex items-center gap-2 px-3 py-2 bg-secondary/30 border-b border-border">
                    {tc.name === 'web_search' || tc.name === 'fetch_url'
                      ? <Globe size={11} className="text-primary" />
                      : <Wrench size={11} className="text-primary" />
                    }
                    <span className="font-mono font-medium text-foreground">{tc.name}</span>
                  </div>
                  <div className="px-3 py-2 space-y-2">
                    <div>
                      <p className="text-muted-foreground mb-1">Input</p>
                      <pre className="text-foreground overflow-x-auto">
                        {JSON.stringify(tc.args, null, 2)}
                      </pre>
                    </div>
                    {result && (
                      <div>
                        <p className="text-muted-foreground mb-1">Output</p>
                        <pre className="text-foreground overflow-x-auto max-h-40">
                          {typeof result.result === 'string'
                            ? result.result
                            : JSON.stringify(result.result, null, 2)}
                        </pre>
                      </div>
                    )}
                  </div>
                </div>
              )
            })}
          </div>
        )}

        {/* Message content */}
        {message.content && (
          <div className={cn(
            'relative rounded-xl px-4 py-3 text-sm',
            isUser
              ? 'bg-primary text-primary-foreground'
              : 'bg-card border border-border text-foreground'
          )}>
            {isUser ? (
              <p className="whitespace-pre-wrap">{message.content}</p>
            ) : (
              <div className="prose prose-invert prose-sm max-w-none">
                <ReactMarkdown
                  components={{
                    code({ node, className, children, ...props }) {
                      const match = /language-(\w+)/.exec(className || '')
                      const isBlock = !!(props as { inline?: boolean }).inline === false && match
                      return isBlock ? (
                        <SyntaxHighlighter
                          style={oneDark as Record<string, React.CSSProperties>}
                          language={match[1]}
                          PreTag="div"
                          className="!rounded-lg !text-xs !my-2"
                        >
                          {String(children).replace(/\n$/, '')}
                        </SyntaxHighlighter>
                      ) : (
                        <code className="bg-secondary px-1 py-0.5 rounded text-xs font-mono" {...props}>
                          {children}
                        </code>
                      )
                    },
                  }}
                >
                  {message.content}
                </ReactMarkdown>
                {message.isStreaming && (
                  <span className="inline-block w-1.5 h-4 bg-primary ml-0.5 cursor-blink" />
                )}
              </div>
            )}

            {/* Copy button */}
            {!isUser && !message.isStreaming && (
              <button
                onClick={copy}
                className="absolute top-2 right-2 opacity-0 group-hover:opacity-100 p-1 rounded hover:bg-secondary transition-all"
              >
                {copied ? <Check size={12} className="text-green-400" /> : <Copy size={12} className="text-muted-foreground" />}
              </button>
            )}
          </div>
        )}

        <span className="text-xs text-muted-foreground px-1">
          {formatTime(message.timestamp)}
        </span>
      </div>
    </div>
  )
}

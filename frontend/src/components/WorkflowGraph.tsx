'use client'

import { useEffect, useRef } from 'react'
import { ExternalLink } from 'lucide-react'
import type {
  ServerMessage,
  LogMessage,
  SourceFoundMessage,
  AwaitingInputMessage,
  StatusUpdateMessage,
  CompleteMessage,
} from '@/lib/websocket'

interface WorkflowGraphProps {
  messages: ServerMessage[]
  onSendChoice?: (choice: string) => void
}

export function WorkflowGraph({ messages, onSendChoice }: WorkflowGraphProps) {
  const messagesEndRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const getLogIcon = (icon: string) => {
    switch (icon) {
      case 'search':
        return '🔍'
      case 'read':
        return '📄'
      case 'compare':
        return '⚖️'
      default:
        return '•'
    }
  }

  const formatTime = (timestamp?: string) => {
    if (!timestamp) return ''
    try {
      const date = new Date(timestamp)
      return date.toLocaleTimeString('en-US', {
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
      })
    } catch {
      return ''
    }
  }

  return (
    <div className="flex-1 flex flex-col bg-zinc-900/50 border-l border-zinc-800">
      <div className="flex-1 overflow-y-auto p-6 space-y-4">
        {messages.length === 0 && (
          <div className="flex items-center justify-center h-full text-zinc-500">
            <div className="text-center">
              <p className="text-sm">No activity yet</p>
              <p className="text-xs text-zinc-600 mt-1">Start a research mission to begin</p>
            </div>
          </div>
        )}

        {messages.map((message, index) => {
          switch (message.type) {
            case 'STATUS_UPDATE': {
              const msg = message as StatusUpdateMessage
              return (
                <div
                  key={index}
                  className="border-l-2 border-blue-500/50 pl-4 py-2 bg-blue-500/5 rounded-r-lg"
                >
                  <div className="text-xs uppercase tracking-widest text-blue-400 font-semibold">
                    {msg.phase}
                  </div>
                  <div className="text-sm text-zinc-300 mt-1">{msg.description}</div>
                  {msg.timestamp && (
                    <div className="text-xs text-zinc-600 mt-1">{formatTime(msg.timestamp)}</div>
                  )}
                </div>
              )
            }

            case 'LOG': {
              const msg = message as LogMessage
              return (
                <div key={index} className="flex gap-3 py-2">
                  <span className="text-lg flex-shrink-0">{getLogIcon(msg.icon)}</span>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm text-zinc-300">{msg.message}</p>
                    {msg.timestamp && (
                      <p className="text-xs text-zinc-600 mt-1">{formatTime(msg.timestamp)}</p>
                    )}
                  </div>
                </div>
              )
            }

            case 'SOURCE_FOUND': {
              const msg = message as SourceFoundMessage
              return (
                <div key={index} className="py-2">
                  <div className="inline-flex gap-2 items-start p-3 bg-amber-500/10 border border-amber-500/30 rounded-lg max-w-md">
                    <div className="text-lg flex-shrink-0">📎</div>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium text-amber-300">{msg.title}</p>
                      <a
                        href={msg.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-xs text-amber-200 hover:text-amber-100 flex items-center gap-1 mt-1 truncate"
                      >
                        <span className="truncate">{msg.url}</span>
                        <ExternalLink className="w-3 h-3 flex-shrink-0" />
                      </a>
                      <p className="text-xs text-amber-400/70 mt-1">
                        Type: {msg.source_type.toUpperCase()}
                      </p>
                      {msg.timestamp && (
                        <p className="text-xs text-zinc-600 mt-1">{formatTime(msg.timestamp)}</p>
                      )}
                    </div>
                  </div>
                </div>
              )
            }

            case 'AWAITING_INPUT': {
              const msg = message as AwaitingInputMessage
              return (
                <div key={index} className="py-2">
                  <div className="p-4 bg-purple-500/10 border border-purple-500/30 rounded-lg">
                    <p className="text-sm font-medium text-purple-300 mb-3">{msg.question}</p>
                    <div className="flex flex-col gap-2">
                      {msg.options.map((option, optIndex) => (
                        <button
                          key={optIndex}
                          onClick={() => onSendChoice?.(option)}
                          className="px-3 py-2 text-sm bg-purple-600 hover:bg-purple-500 text-white rounded-lg transition-colors text-left"
                        >
                          {option}
                        </button>
                      ))}
                    </div>
                    {msg.timestamp && (
                      <p className="text-xs text-zinc-600 mt-2">{formatTime(msg.timestamp)}</p>
                    )}
                  </div>
                </div>
              )
            }

            case 'COMPLETE': {
              const msg = message as CompleteMessage
              return (
                <div key={index} className="py-2">
                  <div className="p-4 bg-green-500/10 border border-green-500/30 rounded-lg">
                    <div className="flex items-center gap-2 mb-3">
                      <span className="text-lg">✅</span>
                      <p className="text-sm font-semibold text-green-400">Research Complete</p>
                    </div>
                    <p className="text-sm text-green-300/80 mb-3">{msg.narrative}</p>
                    {Object.keys(msg.data).length > 0 && (
                      <div className="bg-zinc-900 rounded p-2 text-xs text-zinc-300 space-y-1 font-mono">
                        {Object.entries(msg.data).map(([key, value]) => (
                          <div key={key}>
                            <span className="text-zinc-500">{key}:</span>{' '}
                            <span className="text-green-400">{String(value)}</span>
                          </div>
                        ))}
                      </div>
                    )}
                    {msg.timestamp && (
                      <p className="text-xs text-zinc-600 mt-2">{formatTime(msg.timestamp)}</p>
                    )}
                  </div>
                </div>
              )
            }

            default:
              return null
          }
        })}

        <div ref={messagesEndRef} />
      </div>
    </div>
  )
}

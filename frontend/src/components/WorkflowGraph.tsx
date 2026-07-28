'use client'

import { useEffect, useRef } from 'react'
import {
  Search,
  FileText,
  Scale,
  ListChecks,
  Check,
  AlertTriangle,
  CircleDot,
  Loader2,
} from 'lucide-react'
import type {
  ServerMessage,
  LogIcon,
  AwaitingInputMessage,
  MissionPhase,
} from '@/lib/websocket'

interface WorkflowGraphProps {
  messages: ServerMessage[]
  phase: MissionPhase
  awaitingInput: AwaitingInputMessage | null
  onSendChoice: (choice: string) => void
}

const LOG_ICONS: Record<LogIcon, typeof Search> = {
  search: Search,
  read: FileText,
  compare: Scale,
  list: ListChecks,
  check: Check,
}

function formatTime(timestamp?: string) {
  if (!timestamp) return ''
  const date = new Date(timestamp)
  return Number.isNaN(date.getTime())
    ? ''
    : date.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

export function WorkflowGraph({
  messages,
  phase,
  awaitingInput,
  onSendChoice,
}: WorkflowGraphProps) {
  const endRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, awaitingInput])

  return (
    <section className="flex-1 flex flex-col min-w-0 bg-zinc-900/40">
      <header className="px-6 py-4 border-b border-zinc-800 flex items-center gap-2">
        <CircleDot className="w-4 h-4 text-blue-500" />
        <h2 className="text-sm font-semibold uppercase tracking-wider text-zinc-400">
          Thought Stream
        </h2>
        {phase === 'running' && (
          <Loader2 className="w-4 h-4 text-blue-400 animate-spin ml-auto" aria-label="Working" />
        )}
      </header>

      <div className="flex-1 overflow-y-auto px-6 py-4 space-y-2">
        {messages.length === 0 && (
          <div className="flex items-center justify-center h-full text-center">
            <div>
              <p className="text-sm text-zinc-500">No activity yet</p>
              <p className="text-xs text-zinc-600 mt-1">
                Start a research mission to watch the agent work
              </p>
            </div>
          </div>
        )}

        {messages.map((message, index) => {
          const key = `${index}-${message.type}`

          switch (message.type) {
            case 'STATUS_UPDATE':
              return (
                <div
                  key={key}
                  className="border-l-2 border-blue-500/60 pl-4 py-2 bg-blue-500/5 rounded-r-lg"
                >
                  <div className="text-[11px] uppercase tracking-widest text-blue-400 font-semibold">
                    {message.phase}
                  </div>
                  <div className="text-sm text-zinc-200 mt-0.5">{message.description}</div>
                  <div className="text-[11px] text-zinc-600 mt-1">
                    {formatTime(message.timestamp)}
                  </div>
                </div>
              )

            case 'LOG': {
              const Icon = LOG_ICONS[message.icon] ?? CircleDot
              return (
                <div key={key} className="flex gap-3 py-1.5 px-1">
                  <Icon className="w-4 h-4 mt-0.5 shrink-0 text-zinc-500" />
                  <div className="min-w-0 flex-1">
                    <p className="text-sm text-zinc-300 break-words">{message.message}</p>
                    <p className="text-[11px] text-zinc-600 mt-0.5">
                      {formatTime(message.timestamp)}
                    </p>
                  </div>
                </div>
              )
            }

            case 'SOURCE_FOUND':
              // Rendered in the Source Library panel, not the stream.
              return null

            case 'AWAITING_INPUT':
              // The live prompt is rendered below, pinned to the bottom.
              return (
                <div
                  key={key}
                  className="border-l-2 border-purple-500/60 pl-4 py-2 bg-purple-500/5 rounded-r-lg"
                >
                  <div className="text-[11px] uppercase tracking-widest text-purple-400 font-semibold">
                    Decision gate
                  </div>
                  <div className="text-sm text-zinc-200 mt-0.5">{message.question}</div>
                </div>
              )

            case 'ERROR':
              return (
                <div
                  key={key}
                  className="flex gap-3 p-3 bg-red-500/10 border border-red-500/30 rounded-lg"
                >
                  <AlertTriangle className="w-4 h-4 mt-0.5 shrink-0 text-red-400" />
                  <div className="min-w-0">
                    <p className="text-sm text-red-200 break-words">{message.message}</p>
                    <p className="text-[11px] text-red-400/60 mt-0.5">
                      {message.recoverable ? 'Recoverable' : 'Mission stopped'} ·{' '}
                      {formatTime(message.timestamp)}
                    </p>
                  </div>
                </div>
              )

            case 'COMPLETE':
              return (
                <div
                  key={key}
                  className="p-4 bg-emerald-500/10 border border-emerald-500/30 rounded-lg"
                >
                  <div className="flex items-center gap-2 mb-2">
                    <Check className="w-4 h-4 text-emerald-400" />
                    <p className="text-sm font-semibold text-emerald-300">Research complete</p>
                  </div>
                  <p className="text-sm text-emerald-100/80">{message.narrative}</p>

                  {!!message.data?.tasks?.length && (
                    <div className="mt-3">
                      <p className="text-[11px] uppercase tracking-wider text-emerald-400/70 mb-1">
                        Search tasks executed
                      </p>
                      <ol className="list-decimal list-inside space-y-0.5">
                        {message.data.tasks.map((task, i) => (
                          <li key={i} className="text-xs text-zinc-300 break-words">
                            {task}
                          </li>
                        ))}
                      </ol>
                    </div>
                  )}

                  {!!message.data?.decisions?.length && (
                    <div className="mt-3">
                      <p className="text-[11px] uppercase tracking-wider text-emerald-400/70 mb-1">
                        Your decisions
                      </p>
                      <ul className="space-y-0.5">
                        {message.data.decisions.map((decision, i) => (
                          <li key={i} className="text-xs text-zinc-300">
                            <span className="text-zinc-500">{decision.gate_id}:</span>{' '}
                            {decision.label}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              )

            default:
              return null
          }
        })}

        <div ref={endRef} />
      </div>

      {awaitingInput && (
        <div className="border-t border-purple-500/40 bg-purple-500/10 px-6 py-4">
          <p className="text-[11px] uppercase tracking-widest text-purple-300 font-semibold mb-2">
            The agent needs your decision
          </p>
          <p className="text-sm text-zinc-100 mb-4">{awaitingInput.question}</p>
          <div className="flex flex-wrap gap-3">
            {awaitingInput.options.map((option) => (
              <button
                key={option}
                onClick={() => onSendChoice(option)}
                className="flex-1 min-w-[200px] px-4 py-3 bg-purple-600 hover:bg-purple-500 text-white text-sm font-medium rounded-lg transition-colors"
              >
                {option}
              </button>
            ))}
          </div>
        </div>
      )}
    </section>
  )
}

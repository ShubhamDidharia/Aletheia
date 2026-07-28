'use client'

import { useEffect, useRef } from 'react'
import {
  Search, FileText, Scale, ListChecks, Check, AlertTriangle, Circle, GitBranch,
} from 'lucide-react'
import type { ServerMessage, LogIcon, AwaitingInputMessage, MissionPhase } from '@/lib/websocket'
import { ResultPanel } from '@/components/ResultPanel'
import { DecisionGate } from '@/components/DecisionGate'

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
    : date.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' })
}

/**
 * The live thought stream: a vertical rail with the agent's actions on it.
 * Phase changes are the anchors; individual logs hang off them.
 */
export function WorkflowGraph({
  messages, phase, awaitingInput, onSendChoice,
}: WorkflowGraphProps) {
  const endRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
  }, [messages.length, awaitingInput])

  const visible = messages.filter(
    (m) => m.type !== 'SOURCE_FOUND' && m.type !== 'SOURCES_SYNC'
  )

  return (
    <div className="flex-1 overflow-y-auto scroll-slim">
      <div className="mx-auto max-w-3xl px-4 sm:px-6 py-5">
        {visible.length === 0 && phase === 'running' && (
          <p className="text-sm text-ink-3 py-8 text-center">Starting the agent…</p>
        )}

        <ol className="relative">
          {/* the rail */}
          <span aria-hidden className="absolute left-[11px] top-2 bottom-2 w-px bg-hairline" />

          {visible.map((message, index) => {
            const key = `${index}-${message.type}`

            switch (message.type) {
              case 'STATUS_UPDATE':
                return (
                  <li key={key} className="relative pl-9 py-2.5">
                    <span className="absolute left-0 top-3 w-[23px] grid place-items-center">
                      <span className="w-2.5 h-2.5 rounded-full bg-brand ring-4 ring-plane" />
                    </span>
                    <div className="flex flex-wrap items-baseline gap-x-2">
                      <span className="text-[11px] font-semibold uppercase tracking-widest text-brand">
                        {message.phase}
                      </span>
                      <span className="text-[10px] text-ink-3 tabular-nums">
                        {formatTime(message.timestamp)}
                      </span>
                    </div>
                    <p className="text-sm text-ink mt-0.5 break-words">{message.description}</p>
                  </li>
                )

              case 'LOG': {
                const Icon = LOG_ICONS[message.icon] ?? Circle
                return (
                  <li key={key} className="relative pl-9 py-1">
                    <span className="absolute left-0 top-1.5 w-[23px] grid place-items-center">
                      <span className="w-[23px] h-[23px] rounded-full bg-plane grid place-items-center">
                        <Icon className="w-3.5 h-3.5 text-ink-3" />
                      </span>
                    </span>
                    <p className="text-[13px] text-ink-2 leading-relaxed break-words">
                      {message.message}
                    </p>
                  </li>
                )
              }

              case 'AWAITING_INPUT':
                return (
                  <li key={key} className="relative pl-9 py-2">
                    <span className="absolute left-0 top-2.5 w-[23px] grid place-items-center">
                      <span className="w-[23px] h-[23px] rounded-full bg-plane grid place-items-center">
                        <GitBranch className="w-3.5 h-3.5 text-decision" />
                      </span>
                    </span>
                    <p className="text-[13px] text-decision/90 leading-relaxed break-words">
                      {message.question}
                    </p>
                  </li>
                )

              case 'ERROR':
                return (
                  <li key={key} className="relative pl-9 py-2">
                    <span className="absolute left-0 top-2.5 w-[23px] grid place-items-center">
                      <span className="w-[23px] h-[23px] rounded-full bg-plane grid place-items-center">
                        <AlertTriangle className="w-3.5 h-3.5 text-critical" />
                      </span>
                    </span>
                    <div className="rounded-lg border border-critical/30 bg-critical/10 px-3 py-2">
                      <p className="text-[13px] text-ink break-words">{message.message}</p>
                      <p className="text-[10px] text-critical/80 mt-1">
                        {message.recoverable ? 'Recoverable' : 'Mission stopped'}
                      </p>
                    </div>
                  </li>
                )

              case 'COMPLETE':
                return (
                  <li key={key} className="relative pl-9 py-3">
                    <span className="absolute left-0 top-4 w-[23px] grid place-items-center">
                      <span className="w-2.5 h-2.5 rounded-full bg-good ring-4 ring-plane" />
                    </span>
                    <ResultPanel result={message} />
                  </li>
                )

              default:
                return null
            }
          })}
        </ol>

        {awaitingInput && (
          <div className="mt-4">
            <DecisionGate gate={awaitingInput} onChoose={onSendChoice} />
          </div>
        )}

        <div ref={endRef} className="h-2" />
      </div>
    </div>
  )
}

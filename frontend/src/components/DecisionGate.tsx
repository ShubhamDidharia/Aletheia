'use client'

import { useEffect, useRef } from 'react'
import { GitBranch } from 'lucide-react'
import type { AwaitingInputMessage } from '@/lib/websocket'

/** Plain-language framing for each ambiguity junction the agent can hit. */
const GATE_META: Record<string, { title: string; why: string }> = {
  scope: {
    title: 'How wide should I search?',
    why: 'Your goal is broad. Narrowing gives sharper sources; staying broad gives coverage.',
  },
  recency: {
    title: 'What about the older sources?',
    why: 'Some findings are more than three years old — useful history, or noise.',
  },
  conflict: {
    title: 'Sources disagree',
    why: 'Two sources state different facts. I can dig for a tie-breaker or report both.',
  },
}

interface DecisionGateProps {
  gate: AwaitingInputMessage
  onChoose: (choice: string) => void
}

export function DecisionGate({ gate, onChoose }: DecisionGateProps) {
  const firstOption = useRef<HTMLButtonElement>(null)

  // The agent is blocked on this — put the keyboard where the user needs it.
  useEffect(() => {
    firstOption.current?.focus()
  }, [gate.question])

  const meta = GATE_META[gate.gate_id ?? ''] ?? {
    title: 'The agent needs a decision',
    why: 'Choose how it should continue.',
  }

  return (
    <section
      aria-live="assertive"
      className="gate-attention rounded-xl border border-decision/40 bg-decision/[0.07] p-4 sm:p-5"
    >
      <div className="flex items-center gap-2 mb-3">
        <GitBranch className="w-4 h-4 text-decision" />
        <h2 className="text-sm font-semibold text-decision">{meta.title}</h2>
        <span className="ml-auto text-[10px] uppercase tracking-wider text-decision/70">
          Paused
        </span>
      </div>

      <p className="text-sm text-ink leading-relaxed">{gate.question}</p>
      <p className="mt-1.5 text-xs text-ink-3 leading-relaxed">{meta.why}</p>

      <div className="mt-4 grid gap-2 sm:grid-cols-2">
        {gate.options.map((option, index) => (
          <button
            key={option}
            ref={index === 0 ? firstOption : undefined}
            onClick={() => onChoose(option)}
            className="rounded-lg bg-decision/15 hover:bg-decision/25 border border-decision/40 px-4 py-3 text-left text-sm text-ink font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-decision focus-visible:ring-offset-2 focus-visible:ring-offset-plane"
          >
            {option}
          </button>
        ))}
      </div>
    </section>
  )
}

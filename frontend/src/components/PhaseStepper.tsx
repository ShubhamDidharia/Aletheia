'use client'

import { Check, Loader2, PauseCircle, AlertTriangle } from 'lucide-react'
import type { MissionPhase } from '@/lib/websocket'

/**
 * The agent's pipeline, in order. Each key matches the `phase` field the
 * backend sends on STATUS_UPDATE, so this stays in step with the graph.
 */
export const PHASES = [
  { key: 'planning', label: 'Plan', hint: 'Breaking the goal into search tasks' },
  { key: 'researching', label: 'Research', hint: 'Searching and validating sources' },
  { key: 'analyzing', label: 'Analyse', hint: 'Cross-referencing for conflicts' },
  { key: 'auditing', label: 'Audit', hint: 'Deleting claims without citations' },
  { key: 'synthesizing', label: 'Present', hint: 'Choosing how to show the findings' },
] as const

export type PhaseKey = (typeof PHASES)[number]['key']

interface PhaseStepperProps {
  currentPhase: PhaseKey | null
  missionPhase: MissionPhase
}

export function PhaseStepper({ currentPhase, missionPhase }: PhaseStepperProps) {
  const done = missionPhase === 'complete'
  const failed = missionPhase === 'error'
  const paused = missionPhase === 'awaiting_input'

  const activeIndex = done
    ? PHASES.length
    : currentPhase
      ? PHASES.findIndex((p) => p.key === currentPhase)
      : -1

  return (
    <ol className="flex items-center gap-1 overflow-x-auto scroll-slim" aria-label="Mission progress">
      {PHASES.map((phase, index) => {
        const isDone = index < activeIndex
        const isCurrent = index === activeIndex
        const state = isDone ? 'done' : isCurrent ? 'current' : 'todo'

        return (
          <li key={phase.key} className="flex items-center gap-1 shrink-0">
            <div
              title={phase.hint}
              aria-current={isCurrent ? 'step' : undefined}
              className={[
                'flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[11px] font-medium transition-colors',
                state === 'done' && 'bg-good/10 text-good',
                state === 'current' && failed && 'bg-critical/15 text-critical',
                state === 'current' && paused && 'bg-decision/15 text-decision',
                state === 'current' && !failed && !paused && 'bg-brand/15 text-brand',
                state === 'todo' && 'text-ink-3',
              ]
                .filter(Boolean)
                .join(' ')}
            >
              <StepIcon state={state} failed={failed} paused={paused} />
              <span>{phase.label}</span>
            </div>

            {index < PHASES.length - 1 && (
              <span
                aria-hidden
                className={`h-px w-4 shrink-0 ${isDone ? 'bg-good/40' : 'bg-hairline'}`}
              />
            )}
          </li>
        )
      })}
    </ol>
  )
}

function StepIcon({
  state,
  failed,
  paused,
}: {
  state: 'done' | 'current' | 'todo'
  failed: boolean
  paused: boolean
}) {
  if (state === 'done') return <Check className="w-3 h-3" aria-label="done" />
  if (state === 'current') {
    if (failed) return <AlertTriangle className="w-3 h-3" aria-label="failed" />
    if (paused) return <PauseCircle className="w-3 h-3" aria-label="waiting for you" />
    return <Loader2 className="w-3 h-3 animate-spin" aria-label="in progress" />
  }
  return <span className="w-3 h-3 rounded-full border border-current opacity-40" aria-hidden />
}

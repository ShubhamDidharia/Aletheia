'use client'

import { useState } from 'react'
import { Search, CornerDownLeft, Telescope } from 'lucide-react'

const EXAMPLES = [
  "Compare Tesla vs BYD's 2026 solid-state battery roadmaps",
  'Compare Apple and Microsoft 2026 ESG carbon targets',
  'Lithium supply chain risks for European EV makers in 2026',
]

interface ComposerProps {
  disabled: boolean
  onStart: (query: string) => void
}

/** The idle state: one obvious thing to do, with real examples to click. */
export function Composer({ disabled, onStart }: ComposerProps) {
  const [query, setQuery] = useState('')

  const submit = (goal: string) => {
    if (!disabled && goal.trim()) onStart(goal.trim())
  }

  return (
    <div className="flex-1 grid place-items-center px-4 py-10 overflow-y-auto scroll-slim">
      <div className="w-full max-w-2xl">
        <div className="flex flex-col items-center text-center mb-8">
          <span className="w-11 h-11 rounded-xl bg-brand/15 grid place-items-center text-brand mb-4">
            <Telescope className="w-5 h-5" />
          </span>
          <h1 className="text-2xl sm:text-3xl font-semibold tracking-tight text-ink">
            What do you want to investigate?
          </h1>
          <p className="mt-2 text-sm text-ink-3 max-w-md leading-relaxed">
            Aletheia breaks your goal into searches, gathers and verifies sources, and asks you
            when it hits a genuine ambiguity.
          </p>
        </div>

        <form
          onSubmit={(e) => {
            e.preventDefault()
            submit(query)
          }}
        >
          <div className="relative rounded-2xl border border-hairline bg-panel focus-within:border-brand/60 transition-colors">
            <Search className="absolute left-4 top-4 w-4 h-4 text-ink-3 pointer-events-none" />
            <textarea
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              disabled={disabled}
              rows={3}
              autoFocus
              placeholder="e.g. Compare Apple and Microsoft 2026 ESG carbon targets"
              className="w-full bg-transparent resize-none pl-11 pr-4 pt-3.5 pb-12 text-sm text-ink placeholder:text-ink-3 focus:outline-none disabled:opacity-50"
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault()
                  submit(query)
                }
              }}
            />
            <div className="absolute bottom-3 right-3 flex items-center gap-3">
              <span className="text-[11px] text-ink-3 hidden sm:inline">
                Enter to start · Shift+Enter for a new line
              </span>
              <button
                type="submit"
                disabled={disabled || !query.trim()}
                className="flex items-center gap-1.5 h-8 px-3 rounded-lg bg-brand hover:bg-brand/90 disabled:bg-raised disabled:text-ink-3 text-white text-xs font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand focus-visible:ring-offset-2 focus-visible:ring-offset-panel"
              >
                Investigate
                <CornerDownLeft className="w-3 h-3" />
              </button>
            </div>
          </div>
        </form>

        <div className="mt-6">
          <p className="text-[11px] uppercase tracking-wider text-ink-3 mb-2.5">Try one</p>
          <div className="flex flex-col gap-2">
            {EXAMPLES.map((example) => (
              <button
                key={example}
                onClick={() => submit(example)}
                disabled={disabled}
                className="text-left px-3.5 py-2.5 rounded-lg border border-hairline bg-panel/60 hover:bg-raised hover:border-brand/30 text-xs text-ink-2 transition-colors disabled:opacity-50"
              >
                {example}
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}

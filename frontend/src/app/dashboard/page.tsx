'use client'

import { Suspense, useEffect, useState } from 'react'
import { useSearchParams } from 'next/navigation'
import { Zap, Shield, RotateCcw, AlertTriangle } from 'lucide-react'

import { useWebSocket } from '@/lib/websocket'
import { useSession } from '@/lib/session'
import { WorkflowGraph } from '@/components/WorkflowGraph'
import { SourceLibrary } from '@/components/SourceLibrary'

const STATUS_STYLES = {
  connecting: { dot: 'bg-amber-500', label: 'Connecting' },
  connected: { dot: 'bg-emerald-500', label: 'Connected' },
  disconnected: { dot: 'bg-red-500', label: 'Disconnected' },
} as const

// useSearchParams needs a Suspense boundary or Next fails the prerender.
export default function DashboardPage() {
  return (
    <Suspense
      fallback={
        <div className="h-screen flex items-center justify-center bg-zinc-950 text-zinc-500">
          Loading...
        </div>
      }
    >
      <Dashboard />
    </Suspense>
  )
}

function Dashboard() {
  const { sessionId, resetSession } = useSession()
  const searchParams = useSearchParams()
  const [query, setQuery] = useState('')
  const [autoStarted, setAutoStarted] = useState(false)

  const {
    messages,
    sources,
    status,
    phase,
    awaitingInput,
    error,
    sendChoice,
    sendStartMission,
  } = useWebSocket(sessionId ?? '')

  // Prefill from the home page search box.
  useEffect(() => {
    const initial = searchParams.get('q')
    if (initial) setQuery(initial)
  }, [searchParams])

  // Launch it once the socket is live.
  useEffect(() => {
    const initial = searchParams.get('q')
    if (initial && !autoStarted && status === 'connected' && phase === 'idle') {
      setAutoStarted(true)
      sendStartMission(initial)
    }
  }, [searchParams, autoStarted, status, phase, sendStartMission])

  if (!sessionId) {
    return (
      <div className="h-screen flex items-center justify-center bg-zinc-950 text-zinc-500">
        Loading session...
      </div>
    )
  }

  const busy = phase === 'running'
  const canStart = status === 'connected' && query.trim().length > 0 && !busy && !awaitingInput

  const start = () => {
    if (canStart) sendStartMission(query)
  }

  const startNewMission = () => {
    resetSession()
    setAutoStarted(true)
    setQuery('')
  }

  return (
    <div className="flex h-screen overflow-hidden bg-zinc-950 text-zinc-100">
      {/* ── Left: mission control ────────────────────────────────────────── */}
      <aside className="w-72 shrink-0 border-r border-zinc-800 flex flex-col p-5">
        <div className="flex items-center gap-2 mb-6">
          <Shield className="w-5 h-5 text-blue-500" />
          <div>
            <h1 className="text-lg font-bold leading-tight">Aletheia</h1>
            <p className="text-[11px] text-zinc-500">Strategic Intelligence Agent</p>
          </div>
        </div>

        <div className="mb-5 p-3 bg-zinc-900 rounded-lg border border-zinc-800">
          <div className="flex items-center gap-2">
            <span className={`w-2 h-2 rounded-full ${STATUS_STYLES[status].dot}`} />
            <span className="text-sm text-zinc-300">{STATUS_STYLES[status].label}</span>
          </div>
          <p className="text-[11px] text-zinc-600 mt-1.5 font-mono truncate">
            {sessionId.slice(0, 18)}
          </p>
        </div>

        <label className="text-[11px] uppercase tracking-wider text-zinc-500 mb-2">
          Research goal
        </label>
        <textarea
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          disabled={busy || !!awaitingInput}
          rows={4}
          placeholder="Compare Tesla vs BYD's 2026 solid-state battery roadmaps"
          className="w-full bg-zinc-900 border border-zinc-800 rounded-lg px-3 py-2.5 text-sm resize-none focus:outline-none focus:border-blue-500/60 disabled:opacity-50 disabled:cursor-not-allowed"
          onKeyDown={(e) => {
            if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) start()
          }}
        />

        <button
          onClick={start}
          disabled={!canStart}
          className="mt-3 w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-blue-600 hover:bg-blue-500 disabled:bg-zinc-800 disabled:text-zinc-600 disabled:cursor-not-allowed rounded-lg text-sm font-medium transition-colors"
        >
          <Zap className="w-4 h-4" />
          {busy ? 'Researching...' : 'Start Research'}
        </button>

        <button
          onClick={startNewMission}
          className="mt-2 w-full flex items-center justify-center gap-2 px-4 py-2 text-xs text-zinc-400 hover:text-zinc-200 hover:bg-zinc-900 rounded-lg transition-colors"
        >
          <RotateCcw className="w-3.5 h-3.5" />
          New mission
        </button>

        {error && (
          <div className="mt-4 p-3 bg-red-500/10 border border-red-500/30 rounded-lg flex gap-2">
            <AlertTriangle className="w-4 h-4 text-red-400 shrink-0 mt-0.5" />
            <p className="text-[11px] text-red-200 leading-relaxed break-words">{error}</p>
          </div>
        )}

        <div className="mt-auto pt-6 border-t border-zinc-800 grid grid-cols-2 gap-3">
          <div>
            <p className="text-[11px] text-zinc-500">Events</p>
            <p className="text-xl font-bold text-blue-400">{messages.length}</p>
          </div>
          <div>
            <p className="text-[11px] text-zinc-500">Sources</p>
            <p className="text-xl font-bold text-amber-400">{sources.length}</p>
          </div>
        </div>
      </aside>

      {/* ── Center: live thought stream + decision gates ──────────────────── */}
      <WorkflowGraph
        messages={messages}
        phase={phase}
        awaitingInput={awaitingInput}
        onSendChoice={sendChoice}
      />

      {/* ── Right: evidence gathered ─────────────────────────────────────── */}
      <SourceLibrary sources={sources} />
    </div>
  )
}

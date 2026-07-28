'use client'

import { Suspense, useCallback, useEffect, useRef, useState } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import { Menu, Library, AlertTriangle, Square } from 'lucide-react'

import { useWebSocket } from '@/lib/websocket'
import { useSession } from '@/lib/session'
import { useMissions, type MissionRecord } from '@/lib/missions'
import { createClient } from '@/lib/supabase/client'
import { WorkflowGraph } from '@/components/WorkflowGraph'
import { SourceLibrary } from '@/components/SourceLibrary'
import { MissionSidebar } from '@/components/MissionSidebar'
import { Composer } from '@/components/Composer'
import { PhaseStepper, type PhaseKey } from '@/components/PhaseStepper'

export default function DashboardPage() {
  return (
    <Suspense fallback={<Splash />}>
      <Dashboard />
    </Suspense>
  )
}

function Splash() {
  return (
    <div className="h-dvh grid place-items-center bg-plane text-ink-3 text-sm">Loading…</div>
  )
}

const CONNECTION = {
  connecting: { dot: 'bg-warning', label: 'Connecting' },
  connected: { dot: 'bg-good', label: 'Live' },
  disconnected: { dot: 'bg-critical', label: 'Offline' },
} as const

function Dashboard() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const { sessionId, resetSession, selectSession } = useSession()
  const { missions, startMission, updateMission, removeMission } = useMissions()

  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [evidenceOpen, setEvidenceOpen] = useState(false)
  const [activeQuery, setActiveQuery] = useState('')
  const autoStarted = useRef(false)

  const {
    messages, sources, status, phase, activePhase, awaitingInput, error, sendChoice, sendStartMission,
  } = useWebSocket(sessionId ?? '')

  const launch = useCallback(
    (query: string) => {
      if (!sessionId) return
      setActiveQuery(query)
      startMission(sessionId, query)
      sendStartMission(query)
      setSidebarOpen(false)
    },
    [sessionId, startMission, sendStartMission]
  )

  // Deep link: /dashboard?q=... starts the mission once the socket is live.
  useEffect(() => {
    const initial = searchParams.get('q')
    if (initial && !autoStarted.current && status === 'connected' && phase === 'idle') {
      autoStarted.current = true
      launch(initial)
      router.replace('/dashboard')
    }
  }, [searchParams, status, phase, launch, router])

  // Keep the sidebar entry in step with what the agent is doing.
  useEffect(() => {
    if (!sessionId || phase === 'idle') return
    updateMission(sessionId, {
      status:
        phase === 'complete' ? 'complete'
        : phase === 'error' ? 'error'
        : phase === 'awaiting_input' ? 'awaiting_input'
        : 'running',
      sourceCount: sources.length,
    })
  }, [sessionId, phase, sources.length, updateMission])

  // Restore the title when re-opening a past mission from the sidebar.
  useEffect(() => {
    const known = missions.find((m) => m.sessionId === sessionId)
    if (known && !activeQuery) setActiveQuery(known.query)
  }, [missions, sessionId, activeQuery])

  if (!sessionId) return <Splash />

  const newMission = () => {
    resetSession()
    setActiveQuery('')
    autoStarted.current = true
    setSidebarOpen(false)
  }

  const openMission = (mission: MissionRecord) => {
    selectSession(mission.sessionId)
    setActiveQuery(mission.query)
    autoStarted.current = true
    setSidebarOpen(false)
  }

  const signOut = async () => {
    await createClient().auth.signOut()
    router.push('/login')
  }

  const idle = phase === 'idle' && messages.length === 0
  const connection = CONNECTION[status]

  return (
    <div className="h-dvh flex overflow-hidden bg-plane text-ink">
      <MissionSidebar
        missions={missions}
        activeSessionId={sessionId}
        open={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
        onNewMission={newMission}
        onSelect={openMission}
        onDelete={removeMission}
        onSignOut={signOut}
      />

      <main className="flex-1 flex flex-col min-w-0">
        <header className="h-14 shrink-0 px-3 sm:px-4 flex items-center gap-3 border-b border-hairline bg-plane/90 backdrop-blur">
          <button
            onClick={() => setSidebarOpen(true)}
            aria-label="Open missions"
            className="p-2 -ml-1 rounded-lg text-ink-3 hover:text-ink hover:bg-raised lg:hidden"
          >
            <Menu className="w-4 h-4" />
          </button>

          <div className="min-w-0 flex-1">
            {activeQuery ? (
              <p className="text-sm text-ink truncate" title={activeQuery}>
                {activeQuery}
              </p>
            ) : (
              <p className="text-sm text-ink-3">New mission</p>
            )}
          </div>

          {!idle && (
            <div className="hidden md:block">
              <PhaseStepper currentPhase={activePhase as PhaseKey | null} missionPhase={phase} />
            </div>
          )}

          <div
            className="flex items-center gap-1.5 shrink-0"
            title={`Backend ${connection.label.toLowerCase()}`}
          >
            <span className={`w-1.5 h-1.5 rounded-full ${connection.dot}`} />
            <span className="text-[11px] text-ink-3 hidden sm:inline">{connection.label}</span>
          </div>

          <button
            onClick={() => setEvidenceOpen(true)}
            aria-label="Open evidence panel"
            className="flex items-center gap-1.5 px-2 py-1.5 rounded-lg text-ink-3 hover:text-ink hover:bg-raised xl:hidden"
          >
            <Library className="w-4 h-4" />
            {sources.length > 0 && (
              <span className="text-[11px] tabular-nums">{sources.length}</span>
            )}
          </button>
        </header>

        {!idle && (
          <div className="md:hidden px-4 py-2 border-b border-hairline overflow-x-auto scroll-slim">
            <PhaseStepper currentPhase={activePhase as PhaseKey | null} missionPhase={phase} />
          </div>
        )}

        {error && (
          <div
            role="alert"
            className="mx-4 mt-3 flex items-start gap-2 rounded-lg border border-critical/30 bg-critical/10 px-3 py-2"
          >
            <AlertTriangle className="w-4 h-4 text-critical shrink-0 mt-0.5" />
            <p className="text-xs text-ink leading-relaxed flex-1 break-words">{error}</p>
          </div>
        )}

        {idle ? (
          <Composer disabled={status !== 'connected'} onStart={launch} />
        ) : (
          <>
            <WorkflowGraph
              messages={messages}
              phase={phase}
              awaitingInput={awaitingInput}
              onSendChoice={sendChoice}
            />
            <footer className="shrink-0 border-t border-hairline px-4 py-2.5 flex items-center gap-4 text-[11px] text-ink-3">
              <span className="tabular-nums">{messages.length} events</span>
              <span className="tabular-nums">{sources.length} sources</span>
              <button
                onClick={newMission}
                className="ml-auto flex items-center gap-1.5 px-2.5 py-1 rounded-md hover:bg-raised hover:text-ink transition-colors"
              >
                <Square className="w-3 h-3" />
                Start a new mission
              </button>
            </footer>
          </>
        )}
      </main>

      <SourceLibrary
        sources={sources}
        open={evidenceOpen}
        onClose={() => setEvidenceOpen(false)}
      />
    </div>
  )
}

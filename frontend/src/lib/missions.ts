'use client'

import { useCallback, useEffect, useState } from 'react'

const STORAGE_KEY = 'aletheia:missions'
const MAX_MISSIONS = 25

export type MissionStatus = 'running' | 'awaiting_input' | 'complete' | 'error'

export interface MissionRecord {
  sessionId: string
  query: string
  startedAt: string
  status: MissionStatus
  sourceCount: number
}

function read(): MissionRecord[] {
  if (typeof window === 'undefined') return []
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY)
    const parsed = raw ? JSON.parse(raw) : []
    return Array.isArray(parsed) ? parsed : []
  } catch {
    return []
  }
}

function write(missions: MissionRecord[]) {
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(missions.slice(0, MAX_MISSIONS)))
  } catch {
    // Quota or private mode — history is a convenience, never block on it.
  }
}

/**
 * Mission history for this browser.
 *
 * Deliberately local-only: server-side persistence of missions and reports is
 * Commit 10 (Supabase). This keeps the sidebar honest — it shows exactly what
 * we actually have — instead of a placeholder that never fills in.
 */
export function useMissions() {
  const [missions, setMissions] = useState<MissionRecord[]>([])

  useEffect(() => {
    setMissions(read())
  }, [])

  const persist = useCallback((next: MissionRecord[]) => {
    setMissions(next)
    write(next)
  }, [])

  const startMission = useCallback((sessionId: string, query: string) => {
    const next = [
      { sessionId, query, startedAt: new Date().toISOString(), status: 'running' as const, sourceCount: 0 },
      ...read().filter((m) => m.sessionId !== sessionId),
    ]
    persist(next)
  }, [persist])

  const updateMission = useCallback(
    (sessionId: string, patch: Partial<Omit<MissionRecord, 'sessionId'>>) => {
      const current = read()
      if (!current.some((m) => m.sessionId === sessionId)) return
      persist(current.map((m) => (m.sessionId === sessionId ? { ...m, ...patch } : m)))
    },
    [persist]
  )

  const removeMission = useCallback((sessionId: string) => {
    persist(read().filter((m) => m.sessionId !== sessionId))
  }, [persist])

  const clearMissions = useCallback(() => persist([]), [persist])

  return { missions, startMission, updateMission, removeMission, clearMissions }
}

export function relativeTime(iso: string): string {
  const then = new Date(iso).getTime()
  if (Number.isNaN(then)) return ''
  const seconds = Math.round((Date.now() - then) / 1000)
  if (seconds < 60) return 'just now'
  const minutes = Math.round(seconds / 60)
  if (minutes < 60) return `${minutes}m ago`
  const hours = Math.round(minutes / 60)
  if (hours < 24) return `${hours}h ago`
  const days = Math.round(hours / 24)
  return days === 1 ? 'yesterday' : `${days}d ago`
}

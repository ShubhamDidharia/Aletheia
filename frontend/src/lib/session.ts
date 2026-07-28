'use client'

import { useCallback, useEffect, useState } from 'react'

const STORAGE_KEY = 'aletheia:session_id'

function newId(): string {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) {
    return crypto.randomUUID()
  }
  return `s-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`
}

/**
 * A stable, URL-safe session id persisted per browser tab.
 *
 * This must survive a page refresh: the backend keys its Redis checkpoint and
 * its LangGraph thread on this id, so a reload only re-attaches to a running
 * mission (and replays the thought stream) if the id is the same one.
 *
 * Returns null until mounted, so the server and first client render agree.
 */
export function useSession(): { sessionId: string | null; resetSession: () => void } {
  const [sessionId, setSessionId] = useState<string | null>(null)

  useEffect(() => {
    let id = sessionStorage.getItem(STORAGE_KEY)
    if (!id) {
      id = newId()
      sessionStorage.setItem(STORAGE_KEY, id)
    }
    setSessionId(id)
  }, [])

  const resetSession = useCallback(() => {
    const id = newId()
    sessionStorage.setItem(STORAGE_KEY, id)
    setSessionId(id)
  }, [])

  return { sessionId, resetSession }
}

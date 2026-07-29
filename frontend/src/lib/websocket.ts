'use client'

import { useEffect, useRef, useState, useCallback } from 'react'

export type ServerMessageType =
  | 'STATUS_UPDATE'
  | 'LOG'
  | 'SOURCE_FOUND'
  | 'SOURCES_SYNC'
  | 'AWAITING_INPUT'
  | 'COMPLETE'
  | 'ERROR'

export type LogIcon = 'search' | 'read' | 'compare' | 'list' | 'check'

export interface Source {
  title: string
  url: string
  snippet?: string
  source_type: 'pdf' | 'web'
  published_year?: number | null
}

export interface StatusUpdateMessage {
  type: 'STATUS_UPDATE'
  phase: string
  description: string
  timestamp?: string
}

export interface LogMessage {
  type: 'LOG'
  message: string
  icon: LogIcon
  timestamp?: string
}

export interface SourceFoundMessage extends Source {
  type: 'SOURCE_FOUND'
  timestamp?: string
}

export interface SourcesSyncMessage {
  type: 'SOURCES_SYNC'
  sources: Source[]
  timestamp?: string
}

export interface AwaitingInputMessage {
  type: 'AWAITING_INPUT'
  question: string
  options: string[]
  gate_id?: string
  timestamp?: string
}

export interface Decision {
  gate_id: string
  action: string
  label: string
}

/** A finding whose citation the Auditor matched against a real gathered source. */
export interface VerifiedClaim {
  text: string
  source_url: string
  source_title: string
  snippet: string
}

export interface TableData {
  headers: string[]
  rows: string[][]
  /** Parallel to rows: the verified source URL backing each cell, or ''. */
  citations?: string[][]
  /** Rows whose sources contradict each other. */
  flagged_rows?: number[]
  /** Row index (as a string) -> why it is flagged. */
  flag_reasons?: Record<string, string>
}

export interface Contradiction {
  topic: string
  claim_a: string
  source_a: string
  claim_b: string
  source_b: string
}

export interface SWOTData {
  strengths: string[]
  weaknesses: string[]
  opportunities: string[]
  threats: string[]
}

export interface ChartPoint {
  label: string
  value: number
}

export interface ChartData {
  title: string
  x_label: string
  y_label: string
  points: ChartPoint[]
}

/** What the Visualizer decided the answer should look like. */
export type UIType = 'table' | 'swot' | 'chart' | 'report'

export interface CompleteMessage {
  type: 'COMPLETE'
  ui: UIType
  data: {
    table?: TableData
    swot?: SWOTData
    chart?: ChartData
    claims?: VerifiedClaim[]
    dropped_claims?: number
    contradictions?: Contradiction[]
    sources?: Source[]
    tasks?: string[]
    decisions?: Decision[]
  }
  narrative: string
  timestamp?: string
}

export interface ErrorMessage {
  type: 'ERROR'
  message: string
  recoverable?: boolean
  timestamp?: string
}

export type ServerMessage =
  | StatusUpdateMessage
  | LogMessage
  | SourceFoundMessage
  | SourcesSyncMessage
  | AwaitingInputMessage
  | CompleteMessage
  | ErrorMessage

export type MissionPhase = 'idle' | 'running' | 'awaiting_input' | 'complete' | 'error'

export interface UseWebSocketReturn {
  messages: ServerMessage[]
  sources: Source[]
  status: 'connecting' | 'connected' | 'disconnected'
  phase: MissionPhase
  /** The pipeline stage from the latest STATUS_UPDATE, e.g. "researching". */
  activePhase: string | null
  awaitingInput: AwaitingInputMessage | null
  result: CompleteMessage | null
  error: string | null
  sendChoice: (choice: string) => void
  sendStartMission: (query: string) => void
}

const MAX_RECONNECT_ATTEMPTS = 8

function wsUrlFor(sessionId: string): string {
  const base =
    process.env.NEXT_PUBLIC_WS_URL?.replace(/\/$/, '') ?? 'ws://localhost:8000/ws/research'
  return `${base}/${encodeURIComponent(sessionId)}`
}

export function useWebSocket(sessionId: string): UseWebSocketReturn {
  const [messages, setMessages] = useState<ServerMessage[]>([])
  const [sources, setSources] = useState<Source[]>([])
  const [status, setStatus] = useState<'connecting' | 'connected' | 'disconnected'>('connecting')
  const [phase, setPhase] = useState<MissionPhase>('idle')
  const [awaitingInput, setAwaitingInput] = useState<AwaitingInputMessage | null>(null)
  const [result, setResult] = useState<CompleteMessage | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [activePhase, setActivePhase] = useState<string | null>(null)

  const ws = useRef<WebSocket | null>(null)
  const attempts = useRef(0)
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const closedByUs = useRef(false)

  const handleMessage = useCallback((message: ServerMessage) => {
    message.timestamp = new Date().toISOString()

    // The backend replays history on reconnect, so rebuild rather than append
    // blindly: dedupe sources by URL and keep the newest state per type.
    switch (message.type) {
      case 'SOURCE_FOUND': {
        const { type: _t, timestamp: _ts, ...source } = message
        setSources((prev) =>
          prev.some((s) => s.url === source.url) ? prev : [...prev, source as Source]
        )
        setPhase('running')
        break
      }
      case 'SOURCES_SYNC':
        setSources(message.sources)
        break
      case 'AWAITING_INPUT':
        setAwaitingInput(message)
        setPhase('awaiting_input')
        break
      case 'COMPLETE':
        setResult(message)
        // Only adopt the final list when it actually has sources — an empty
        // array must never wipe evidence the user already watched arrive.
        if (message.data?.sources?.length) setSources(message.data.sources)
        setAwaitingInput(null)
        setPhase('complete')
        break
      case 'ERROR':
        setError(message.message)
        if (!message.recoverable) {
          setAwaitingInput(null)
          setPhase('error')
        }
        break
      case 'STATUS_UPDATE':
        setActivePhase(message.phase)
        setAwaitingInput(null)
        setPhase((p) => (p === 'complete' || p === 'error' ? p : 'running'))
        break
      case 'LOG':
        // Progress means the agent resumed past its last question.
        setAwaitingInput(null)
        setPhase((p) => (p === 'complete' || p === 'error' ? p : 'running'))
        break
    }

    if (message.type !== 'SOURCES_SYNC') {
      setMessages((prev) => [...prev, message])
    }
  }, [])

  const connect = useCallback(() => {
    if (!sessionId) return
    if (ws.current?.readyState === WebSocket.OPEN || ws.current?.readyState === WebSocket.CONNECTING) {
      return
    }

    // A reconnect replays the full history, so start from a clean slate to
    // avoid rendering every event twice. Mission state is reset too — the
    // replay re-derives it, and without this a new session would inherit the
    // previous mission's phase and never show the composer again.
    setMessages([])
    setSources([])
    setResult(null)
    setActivePhase(null)
    setPhase('idle')
    setAwaitingInput(null)

    try {
      const socket = new WebSocket(wsUrlFor(sessionId))
      ws.current = socket

      // Every handler ignores events from a socket that is no longer current.
      // Switching sessions closes the old socket, but its onclose fires *after*
      // the new one has opened — without this guard it would stamp
      // "disconnected" over a perfectly healthy connection.
      const isCurrent = () => ws.current === socket

      socket.onopen = () => {
        if (!isCurrent()) return
        setStatus('connected')
        setError(null)
        attempts.current = 0
      }

      socket.onmessage = (event) => {
        if (!isCurrent()) return
        try {
          handleMessage(JSON.parse(event.data) as ServerMessage)
        } catch (err) {
          console.error('Failed to parse message:', err)
        }
      }

      socket.onerror = () => {
        // onclose always follows; reconnect is handled there.
        if (isCurrent()) setStatus('disconnected')
      }

      socket.onclose = () => {
        if (!isCurrent()) return
        setStatus('disconnected')
        if (!closedByUs.current) scheduleReconnect()
      }
    } catch (err) {
      console.error('Failed to create WebSocket:', err)
      setStatus('disconnected')
      scheduleReconnect()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionId, handleMessage])

  const scheduleReconnect = useCallback(() => {
    if (attempts.current >= MAX_RECONNECT_ATTEMPTS) {
      setError('Lost connection to the research backend. Reload the page to retry.')
      return
    }
    const delay = Math.min(2 ** attempts.current * 1000, 15000)
    attempts.current += 1
    reconnectTimer.current = setTimeout(() => {
      setStatus('connecting')
      connect()
    }, delay)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [connect])

  const send = useCallback((payload: Record<string, unknown>): boolean => {
    if (ws.current?.readyState !== WebSocket.OPEN) {
      setError('Not connected to the backend.')
      return false
    }
    ws.current.send(JSON.stringify(payload))
    return true
  }, [])

  const sendChoice = useCallback(
    (choice: string) => {
      if (send({ type: 'USER_RESPONSE', choice })) {
        setAwaitingInput(null)
        setPhase('running')
      }
    },
    [send]
  )

  const sendStartMission = useCallback(
    (query: string) => {
      if (!query.trim()) return
      setMessages([])
      setSources([])
      setResult(null)
      setError(null)
      setActivePhase(null)
      if (send({ type: 'START_MISSION', query })) {
        setPhase('running')
      }
    },
    [send]
  )

  useEffect(() => {
    closedByUs.current = false
    connect()

    return () => {
      closedByUs.current = true
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current)
      const socket = ws.current
      // Clear the ref first so the closing socket's handlers see themselves as
      // stale and leave the next session's state alone.
      ws.current = null
      socket?.close()
    }
  }, [connect])

  return {
    messages,
    sources,
    status,
    phase,
    activePhase,
    awaitingInput,
    result,
    error,
    sendChoice,
    sendStartMission,
  }
}

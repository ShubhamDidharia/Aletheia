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

export interface CompleteMessage {
  type: 'COMPLETE'
  ui: string
  data: {
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
        if (message.data?.sources) setSources(message.data.sources)
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
      case 'LOG':
      case 'STATUS_UPDATE':
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
    // avoid rendering every event twice.
    setMessages([])
    setSources([])
    setResult(null)

    try {
      const socket = new WebSocket(wsUrlFor(sessionId))
      ws.current = socket

      socket.onopen = () => {
        setStatus('connected')
        setError(null)
        attempts.current = 0
      }

      socket.onmessage = (event) => {
        try {
          handleMessage(JSON.parse(event.data) as ServerMessage)
        } catch (err) {
          console.error('Failed to parse message:', err)
        }
      }

      socket.onerror = () => {
        // onclose always follows; reconnect is handled there.
        setStatus('disconnected')
      }

      socket.onclose = () => {
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
      ws.current?.close()
      ws.current = null
    }
  }, [connect])

  return {
    messages,
    sources,
    status,
    phase,
    awaitingInput,
    result,
    error,
    sendChoice,
    sendStartMission,
  }
}

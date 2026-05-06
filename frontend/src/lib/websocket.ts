'use client'

import { useEffect, useRef, useState, useCallback } from 'react'

export type ServerMessageType =
  | 'STATUS_UPDATE'
  | 'LOG'
  | 'SOURCE_FOUND'
  | 'AWAITING_INPUT'
  | 'COMPLETE'

export interface StatusUpdateMessage {
  type: 'STATUS_UPDATE'
  phase: string
  description: string
  timestamp?: string
}

export interface LogMessage {
  type: 'LOG'
  message: string
  icon: 'search' | 'read' | 'compare'
  timestamp?: string
}

export interface SourceFoundMessage {
  type: 'SOURCE_FOUND'
  title: string
  url: string
  source_type: 'pdf' | 'web'
  timestamp?: string
}

export interface AwaitingInputMessage {
  type: 'AWAITING_INPUT'
  question: string
  options: string[]
  timestamp?: string
}

export interface CompleteMessage {
  type: 'COMPLETE'
  ui: string
  data: Record<string, any>
  narrative: string
  timestamp?: string
}

export type ServerMessage =
  | StatusUpdateMessage
  | LogMessage
  | SourceFoundMessage
  | AwaitingInputMessage
  | CompleteMessage

export interface UseWebSocketReturn {
  messages: ServerMessage[]
  status: 'connecting' | 'connected' | 'disconnected'
  awaitingInput: AwaitingInputMessage | null
  sendChoice: (choice: string) => void
  sendStartMission: () => void
}

export function useWebSocket(sessionId: string): UseWebSocketReturn {
  const [messages, setMessages] = useState<ServerMessage[]>([])
  const [status, setStatus] = useState<'connecting' | 'connected' | 'disconnected'>('connecting')
  const [awaitingInput, setAwaitingInput] = useState<AwaitingInputMessage | null>(null)

  const ws = useRef<WebSocket | null>(null)
  const reconnectAttemptsRef = useRef(0)
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null)
  const maxReconnectAttemptsRef = useRef(5)

  const connect = useCallback(() => {
    if (ws.current?.readyState === WebSocket.OPEN) {
      return
    }

    const wsUrl = `ws://localhost:8000/ws/research/${sessionId}`

    try {
      ws.current = new WebSocket(wsUrl)

      ws.current.onopen = () => {
        console.log('WebSocket connected')
        setStatus('connected')
        reconnectAttemptsRef.current = 0
      }

      ws.current.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data) as ServerMessage
          message.timestamp = new Date().toISOString()

          setMessages((prev) => [...prev, message])

          if (message.type === 'AWAITING_INPUT') {
            setAwaitingInput(message as AwaitingInputMessage)
          }
        } catch (error) {
          console.error('Failed to parse message:', error)
        }
      }

      ws.current.onerror = (error) => {
        console.error('WebSocket error:', error)
        setStatus('disconnected')
      }

      ws.current.onclose = () => {
        console.log('WebSocket disconnected')
        setStatus('disconnected')
        attemptReconnect()
      }
    } catch (error) {
      console.error('Failed to create WebSocket:', error)
      setStatus('disconnected')
      attemptReconnect()
    }
  }, [sessionId])

  const attemptReconnect = useCallback(() => {
    if (reconnectAttemptsRef.current >= maxReconnectAttemptsRef.current) {
      console.error('Max reconnection attempts reached')
      return
    }

    const delay = Math.pow(2, reconnectAttemptsRef.current) * 1000
    reconnectAttemptsRef.current += 1

    console.log(
      `Attempting to reconnect in ${delay}ms (attempt ${reconnectAttemptsRef.current}/${maxReconnectAttemptsRef.current})`
    )

    reconnectTimeoutRef.current = setTimeout(() => {
      setStatus('connecting')
      connect()
    }, delay)
  }, [connect])

  const sendChoice = useCallback((choice: string) => {
    if (ws.current?.readyState === WebSocket.OPEN) {
      const message = {
        type: 'USER_CHOICE',
        choice,
      }
      ws.current.send(JSON.stringify(message))
      setAwaitingInput(null)
    }
  }, [])

  const sendStartMission = useCallback(() => {
    if (ws.current?.readyState === WebSocket.OPEN) {
      const message = {
        type: 'START_MISSION',
      }
      ws.current.send(JSON.stringify(message))
    }
  }, [])

  useEffect(() => {
    connect()

    return () => {
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current)
      }
      if (ws.current?.readyState === WebSocket.OPEN) {
        ws.current.close()
      }
    }
  }, [connect])

  return {
    messages,
    status,
    awaitingInput,
    sendChoice,
    sendStartMission,
  }
}

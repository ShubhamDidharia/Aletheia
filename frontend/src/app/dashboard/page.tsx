'use client'

import { useId } from 'react'
import { useWebSocket } from '@/lib/websocket'
import { WorkflowGraph } from '@/components/WorkflowGraph'
import { Zap } from 'lucide-react'

export default function DashboardPage() {
  const sessionId = useId()
  const { messages, status, awaitingInput, sendChoice, sendStartMission } =
    useWebSocket(sessionId)

  const statusColors = {
    connecting: 'bg-yellow-500',
    connected: 'bg-green-500',
    disconnected: 'bg-red-500',
  }

  const statusText = {
    connecting: 'Connecting',
    connected: 'Connected',
    disconnected: 'Disconnected',
  }

  return (
    <div className="flex h-screen overflow-hidden">
      {/* Left Panel - Controls */}
      <div className="w-64 bg-zinc-950 border-r border-zinc-800 flex flex-col p-6">
        <div className="mb-8">
          <h1 className="text-xl font-bold text-white mb-2">Aletheia</h1>
          <p className="text-xs text-zinc-500">Strategic Intelligence Agent</p>
        </div>

        {/* Connection Status */}
        <div className="mb-8 p-4 bg-zinc-900 rounded-lg border border-zinc-800">
          <div className="flex items-center gap-2 mb-2">
            <div className={`w-2 h-2 rounded-full ${statusColors[status]}`} />
            <span className="text-sm text-zinc-300">{statusText[status]}</span>
          </div>
          <p className="text-xs text-zinc-600">Session ID: {sessionId.slice(0, 12)}...</p>
        </div>

        {/* Start Button */}
        <button
          onClick={sendStartMission}
          disabled={status !== 'connected'}
          className="w-full flex items-center justify-center gap-2 px-4 py-3 bg-blue-600 hover:bg-blue-700 disabled:bg-zinc-700 disabled:cursor-not-allowed text-white rounded-lg font-medium transition-colors mb-6"
        >
          <Zap className="w-4 h-4" />
          Start Research
        </button>

        {/* Messages Count */}
        <div className="p-4 bg-zinc-900 rounded-lg border border-zinc-800">
          <p className="text-xs text-zinc-500 mb-1">Messages Received</p>
          <p className="text-2xl font-bold text-blue-400">{messages.length}</p>
        </div>

        {/* Awaiting Input Indicator */}
        {awaitingInput && (
          <div className="mt-6 p-3 bg-purple-500/10 border border-purple-500/30 rounded-lg">
            <p className="text-xs font-semibold text-purple-300 mb-2">Awaiting Input</p>
            <p className="text-xs text-purple-200">{awaitingInput.question}</p>
          </div>
        )}

        {/* Information */}
        <div className="mt-auto pt-8 border-t border-zinc-800">
          <p className="text-xs text-zinc-600 leading-relaxed">
            This is a demo of the real-time WebSocket communication layer. Click "Start Research"
            to simulate a research workflow with logs, sources, and human-in-the-loop interactions.
          </p>
        </div>
      </div>

      {/* Right Panel - Workflow Graph */}
      <WorkflowGraph messages={messages} onSendChoice={sendChoice} />
    </div>
  )
}

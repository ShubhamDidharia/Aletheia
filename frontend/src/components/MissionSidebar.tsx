'use client'

import {
  Plus, Loader2, Check, AlertTriangle, PauseCircle, Trash2, History, LogOut, X,
} from 'lucide-react'
import { relativeTime, type MissionRecord, type MissionStatus } from '@/lib/missions'

const STATUS_META: Record<MissionStatus, { icon: typeof Check; tone: string; label: string }> = {
  running: { icon: Loader2, tone: 'text-brand', label: 'Running' },
  awaiting_input: { icon: PauseCircle, tone: 'text-decision', label: 'Needs you' },
  complete: { icon: Check, tone: 'text-good', label: 'Complete' },
  error: { icon: AlertTriangle, tone: 'text-critical', label: 'Failed' },
}

interface MissionSidebarProps {
  missions: MissionRecord[]
  activeSessionId: string | null
  open: boolean
  onClose: () => void
  onNewMission: () => void
  onSelect: (mission: MissionRecord) => void
  onDelete: (sessionId: string) => void
  onSignOut: () => void
}

export function MissionSidebar({
  missions, activeSessionId, open, onClose, onNewMission, onSelect, onDelete, onSignOut,
}: MissionSidebarProps) {
  return (
    <>
      {/* Backdrop, mobile only */}
      {open && (
        <button
          aria-label="Close menu"
          onClick={onClose}
          className="fixed inset-0 z-30 bg-black/60 lg:hidden"
        />
      )}

      <aside
        className={[
          'z-40 w-[272px] shrink-0 bg-panel border-r border-hairline flex-col',
          // Off-canvas below lg, a permanent column at lg and up. Toggling
          // display (rather than a transform) keeps it genuinely out of the
          // way — a translated panel still overlays the content.
          'fixed inset-y-0 left-0 lg:static',
          open ? 'flex' : 'hidden lg:flex',
        ].join(' ')}
      >
        <div className="flex items-center gap-2 px-4 h-14 border-b border-hairline">
          <span className="w-6 h-6 rounded-md bg-brand/15 grid place-items-center text-brand text-xs font-bold">
            A
          </span>
          <span className="font-semibold tracking-tight">Aletheia</span>
          <button
            onClick={onClose}
            aria-label="Close menu"
            className="ml-auto p-1.5 rounded-md text-ink-3 hover:text-ink hover:bg-raised lg:hidden"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        <div className="p-3">
          <button
            onClick={onNewMission}
            className="w-full flex items-center justify-center gap-2 h-9 rounded-lg bg-brand hover:bg-brand/90 text-white text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand focus-visible:ring-offset-2 focus-visible:ring-offset-panel"
          >
            <Plus className="w-4 h-4" />
            New mission
          </button>
        </div>

        <div className="px-4 pb-2 flex items-center gap-2">
          <History className="w-3.5 h-3.5 text-ink-3" />
          <span className="text-[11px] uppercase tracking-wider text-ink-3">Recent</span>
          {missions.length > 0 && (
            <span className="ml-auto text-[11px] text-ink-3 tabular-nums">{missions.length}</span>
          )}
        </div>

        <nav className="flex-1 overflow-y-auto scroll-slim px-2 pb-2 space-y-0.5">
          {missions.length === 0 && (
            <p className="px-2 py-6 text-xs text-ink-3 leading-relaxed">
              Missions you run appear here. History is kept in this browser.
            </p>
          )}

          {missions.map((mission) => {
            const meta = STATUS_META[mission.status] ?? STATUS_META.complete
            const Icon = meta.icon
            const isActive = mission.sessionId === activeSessionId

            return (
              <div
                key={mission.sessionId}
                className={`group relative rounded-lg transition-colors ${
                  isActive ? 'bg-raised' : 'hover:bg-raised/60'
                }`}
              >
                <button
                  onClick={() => onSelect(mission)}
                  aria-current={isActive ? 'true' : undefined}
                  className="w-full text-left px-2.5 py-2 pr-8"
                >
                  <div className="flex items-start gap-2">
                    <Icon
                      className={`w-3.5 h-3.5 mt-0.5 shrink-0 ${meta.tone} ${
                        mission.status === 'running' ? 'animate-spin' : ''
                      }`}
                      aria-label={meta.label}
                    />
                    <span className="text-xs text-ink-2 line-clamp-2 leading-snug">
                      {mission.query}
                    </span>
                  </div>
                  <div className="mt-1 pl-5.5 flex items-center gap-2 text-[10px] text-ink-3">
                    <span>{relativeTime(mission.startedAt)}</span>
                    {mission.sourceCount > 0 && (
                      <span className="tabular-nums">{mission.sourceCount} sources</span>
                    )}
                  </div>
                </button>

                <button
                  onClick={() => onDelete(mission.sessionId)}
                  aria-label={`Remove mission: ${mission.query.slice(0, 40)}`}
                  className="absolute top-2 right-1.5 p-1 rounded text-ink-3 opacity-0 group-hover:opacity-100 focus-visible:opacity-100 hover:text-critical transition-opacity"
                >
                  <Trash2 className="w-3.5 h-3.5" />
                </button>
              </div>
            )
          })}
        </nav>

        <div className="p-3 border-t border-hairline">
          <button
            onClick={onSignOut}
            className="w-full flex items-center gap-2 px-2.5 py-2 rounded-lg text-xs text-ink-3 hover:text-ink hover:bg-raised transition-colors"
          >
            <LogOut className="w-3.5 h-3.5" />
            Sign out
          </button>
        </div>
      </aside>
    </>
  )
}

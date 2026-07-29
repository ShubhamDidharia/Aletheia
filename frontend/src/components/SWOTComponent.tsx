'use client'

import { TrendingUp, TrendingDown, Lightbulb, ShieldAlert } from 'lucide-react'
import type { SWOTData } from '@/lib/websocket'

const QUADRANTS = [
  { key: 'strengths', label: 'Strengths', icon: TrendingUp, ring: 'border-good/30', ink: 'text-good' },
  { key: 'weaknesses', label: 'Weaknesses', icon: TrendingDown, ring: 'border-critical/30', ink: 'text-critical' },
  { key: 'opportunities', label: 'Opportunities', icon: Lightbulb, ring: 'border-brand/30', ink: 'text-brand' },
  { key: 'threats', label: 'Threats', icon: ShieldAlert, ring: 'border-warning/30', ink: 'text-warning' },
] as const

/** Four-quadrant card grid. Each quadrant is labelled and icon-marked, so the
 *  quadrant is never identified by colour alone. */
export function SWOTComponent({ swot }: { swot: SWOTData }) {
  return (
    <div className="grid gap-2 sm:grid-cols-2">
      {QUADRANTS.map(({ key, label, icon: Icon, ring, ink }) => (
        <section key={key} className={`rounded-lg border ${ring} bg-white/[0.02] p-3`}>
          <h4 className={`flex items-center gap-1.5 text-[10px] uppercase tracking-wider font-semibold mb-2 ${ink}`}>
            <Icon className="w-3.5 h-3.5" />
            {label}
            <span className="ml-auto tabular-nums text-ink-3">{swot[key].length}</span>
          </h4>

          {swot[key].length === 0 ? (
            <p className="text-xs text-ink-3">None identified</p>
          ) : (
            <ul className="space-y-1.5">
              {swot[key].map((item, i) => (
                <li key={i} className="flex gap-1.5 text-xs text-ink-2 leading-relaxed">
                  <span className={`mt-1.5 w-1 h-1 rounded-full shrink-0 bg-current ${ink}`} />
                  {item}
                </li>
              ))}
            </ul>
          )}
        </section>
      ))}
    </div>
  )
}

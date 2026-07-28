'use client'

import { Check, ExternalLink, ShieldCheck, Trash2 } from 'lucide-react'
import type { CompleteMessage, VerifiedClaim } from '@/lib/websocket'

/**
 * Renders the Visualizer's chosen output shape.
 *
 * Commit 8 replaces this with the full ResponseDispatcher — a sortable/
 * filterable Shadcn DataTable, a four-quadrant SWOT grid, Recharts charts and
 * per-cell audit-trail tooltips. This is the plain version so Commit 7's
 * structured output is actually visible.
 */
export function ResultPanel({ result }: { result: CompleteMessage }) {
  const { ui, data, narrative } = result
  const claims = data.claims ?? []

  return (
    <div className="p-4 bg-emerald-500/10 border border-emerald-500/30 rounded-lg space-y-4">
      <div className="flex items-center gap-2">
        <Check className="w-4 h-4 text-emerald-400" />
        <p className="text-sm font-semibold text-emerald-300">Research complete</p>
        <span className="ml-auto px-2 py-0.5 rounded text-[10px] font-semibold uppercase tracking-wider bg-emerald-500/20 text-emerald-300">
          {ui}
        </span>
      </div>

      {narrative && <p className="text-sm text-emerald-50/90 leading-relaxed">{narrative}</p>}

      {ui === 'table' && data.table && <TableView table={data.table} />}
      {ui === 'swot' && data.swot && <SwotView swot={data.swot} />}
      {ui === 'chart' && data.chart && <ChartView chart={data.chart} />}

      {claims.length > 0 && <ClaimsView claims={claims} dropped={data.dropped_claims ?? 0} />}

      {!!data.tasks?.length && (
        <Section title="Search tasks executed">
          <ol className="list-decimal list-inside space-y-0.5">
            {data.tasks.map((task, i) => (
              <li key={i} className="text-xs text-zinc-300 break-words">
                {task}
              </li>
            ))}
          </ol>
        </Section>
      )}

      {!!data.decisions?.length && (
        <Section title="Your decisions">
          <ul className="space-y-0.5">
            {data.decisions.map((decision, i) => (
              <li key={i} className="text-xs text-zinc-300">
                <span className="text-zinc-500">{decision.gate_id}:</span> {decision.label}
              </li>
            ))}
          </ul>
        </Section>
      )}
    </div>
  )
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div>
      <p className="text-[11px] uppercase tracking-wider text-emerald-400/70 mb-1.5">{title}</p>
      {children}
    </div>
  )
}

function TableView({ table }: { table: NonNullable<CompleteMessage['data']['table']> }) {
  return (
    <div className="overflow-x-auto rounded-lg border border-zinc-800">
      <table className="w-full text-xs border-collapse">
        <thead>
          <tr className="bg-zinc-900">
            {table.headers.map((header, i) => (
              <th
                key={i}
                className="text-left font-semibold text-zinc-200 px-3 py-2 border-b border-zinc-800 whitespace-nowrap"
              >
                {header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {table.rows.map((row, r) => (
            <tr key={r} className="odd:bg-zinc-900/40">
              {row.map((cell, c) => (
                <td
                  key={c}
                  className={`px-3 py-2 align-top border-b border-zinc-800/60 ${
                    c === 0 ? 'font-medium text-zinc-300' : 'text-zinc-400'
                  }`}
                >
                  {cell}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

const SWOT_QUADRANTS = [
  { key: 'strengths', label: 'Strengths', tone: 'text-emerald-300 border-emerald-500/30' },
  { key: 'weaknesses', label: 'Weaknesses', tone: 'text-rose-300 border-rose-500/30' },
  { key: 'opportunities', label: 'Opportunities', tone: 'text-sky-300 border-sky-500/30' },
  { key: 'threats', label: 'Threats', tone: 'text-amber-300 border-amber-500/30' },
] as const

function SwotView({ swot }: { swot: NonNullable<CompleteMessage['data']['swot']> }) {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
      {SWOT_QUADRANTS.map(({ key, label, tone }) => (
        <div key={key} className={`p-3 rounded-lg border bg-zinc-900/50 ${tone.split(' ')[1]}`}>
          <p className={`text-[11px] uppercase tracking-wider font-semibold mb-1.5 ${tone.split(' ')[0]}`}>
            {label}
          </p>
          <ul className="space-y-1">
            {swot[key].length === 0 && <li className="text-xs text-zinc-600">None identified</li>}
            {swot[key].map((item, i) => (
              <li key={i} className="text-xs text-zinc-300 leading-relaxed">
                • {item}
              </li>
            ))}
          </ul>
        </div>
      ))}
    </div>
  )
}

function ChartView({ chart }: { chart: NonNullable<CompleteMessage['data']['chart']> }) {
  const max = Math.max(...chart.points.map((p) => Math.abs(p.value)), 1)

  return (
    <div className="p-3 rounded-lg border border-zinc-800 bg-zinc-900/50">
      {chart.title && <p className="text-xs font-medium text-zinc-200 mb-3">{chart.title}</p>}
      <div className="space-y-2">
        {chart.points.map((point, i) => (
          <div key={i} className="flex items-center gap-2">
            <span className="w-28 shrink-0 text-[11px] text-zinc-400 truncate" title={point.label}>
              {point.label}
            </span>
            <div className="flex-1 h-4 bg-zinc-800 rounded overflow-hidden">
              <div
                className="h-full bg-blue-500/70 rounded"
                style={{ width: `${(Math.abs(point.value) / max) * 100}%` }}
              />
            </div>
            <span className="w-16 shrink-0 text-[11px] text-zinc-300 text-right font-mono">
              {point.value}
            </span>
          </div>
        ))}
      </div>
      {chart.y_label && <p className="text-[11px] text-zinc-600 mt-2">{chart.y_label}</p>}
    </div>
  )
}

function ClaimsView({ claims, dropped }: { claims: VerifiedClaim[]; dropped: number }) {
  return (
    <div>
      <div className="flex items-center gap-2 mb-1.5">
        <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
        <p className="text-[11px] uppercase tracking-wider text-emerald-400/70">
          {claims.length} verified claim{claims.length === 1 ? '' : 's'}
        </p>
        {dropped > 0 && (
          <span className="flex items-center gap-1 text-[11px] text-amber-400/80">
            <Trash2 className="w-3 h-3" />
            {dropped} uncited claim{dropped === 1 ? '' : 's'} deleted
          </span>
        )}
      </div>
      <ul className="space-y-1.5">
        {claims.map((claim, i) => (
          <li key={i} className="text-xs text-zinc-300 leading-relaxed">
            <span>{claim.text}</span>{' '}
            <a
              href={claim.source_url}
              target="_blank"
              rel="noopener noreferrer"
              title={claim.snippet}
              className="inline-flex items-center gap-0.5 text-emerald-400/80 hover:text-emerald-300 underline decoration-dotted underline-offset-2"
            >
              {claim.source_title.slice(0, 40)}
              <ExternalLink className="w-2.5 h-2.5" />
            </a>
          </li>
        ))}
      </ul>
    </div>
  )
}

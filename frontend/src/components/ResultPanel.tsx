'use client'

import { Check, ExternalLink, ShieldCheck, Trash2, Table2, Grid2x2, BarChart3, FileText } from 'lucide-react'
import type { CompleteMessage, VerifiedClaim, UIType } from '@/lib/websocket'

const UI_META: Record<UIType, { icon: typeof Table2; label: string }> = {
  table: { icon: Table2, label: 'Comparison table' },
  swot: { icon: Grid2x2, label: 'SWOT' },
  chart: { icon: BarChart3, label: 'Chart' },
  report: { icon: FileText, label: 'Report' },
}

/**
 * Renders the Visualizer's chosen output shape.
 *
 * Commit 8 replaces this with the full ResponseDispatcher — a sortable/
 * filterable Shadcn DataTable, Recharts charts and per-cell audit-trail
 * tooltips. This is the plain version so Commit 7's output is visible.
 */
export function ResultPanel({ result }: { result: CompleteMessage }) {
  const { ui, data, narrative } = result
  const claims = data.claims ?? []
  const meta = UI_META[ui] ?? UI_META.report
  const Icon = meta.icon

  return (
    <section className="rounded-xl border border-good/25 bg-good/[0.05] overflow-hidden">
      <header className="flex items-center gap-2 px-4 py-3 border-b border-good/15">
        <Check className="w-4 h-4 text-good" />
        <h2 className="text-sm font-semibold text-ink">Research complete</h2>
        <span className="ml-auto flex items-center gap-1.5 px-2 py-0.5 rounded-full bg-white/[0.06] text-[10px] font-medium text-ink-2">
          <Icon className="w-3 h-3" />
          {meta.label}
        </span>
      </header>

      <div className="p-4 space-y-4">
        {narrative && <p className="text-sm text-ink leading-relaxed">{narrative}</p>}

        {ui === 'table' && data.table && <TableView table={data.table} />}
        {ui === 'swot' && data.swot && <SwotView swot={data.swot} />}
        {ui === 'chart' && data.chart && <ChartView chart={data.chart} />}

        {claims.length > 0 && <ClaimsView claims={claims} dropped={data.dropped_claims ?? 0} />}

        <div className="grid gap-4 sm:grid-cols-2">
          {!!data.tasks?.length && (
            <Section title={`${data.tasks.length} search tasks`}>
              <ol className="space-y-1">
                {data.tasks.map((task, i) => (
                  <li key={i} className="text-xs text-ink-2 break-words flex gap-1.5">
                    <span className="text-ink-3 tabular-nums shrink-0">{i + 1}.</span>
                    {task}
                  </li>
                ))}
              </ol>
            </Section>
          )}

          {!!data.decisions?.length && (
            <Section title="Your decisions">
              <ul className="space-y-1">
                {data.decisions.map((decision, i) => (
                  <li key={i} className="text-xs text-ink-2">
                    <span className="text-ink-3">{decision.gate_id}: </span>
                    {decision.label}
                  </li>
                ))}
              </ul>
            </Section>
          )}
        </div>
      </div>
    </section>
  )
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div>
      <p className="text-[10px] uppercase tracking-wider text-ink-3 mb-1.5">{title}</p>
      {children}
    </div>
  )
}

function TableView({ table }: { table: NonNullable<CompleteMessage['data']['table']> }) {
  return (
    <div className="overflow-x-auto scroll-slim rounded-lg border border-hairline">
      <table className="w-full text-xs border-collapse">
        <thead>
          <tr className="bg-white/[0.04]">
            {table.headers.map((header, i) => (
              <th
                key={i}
                scope="col"
                className="text-left font-semibold text-ink px-3 py-2 whitespace-nowrap border-b border-hairline"
              >
                {header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {table.rows.map((row, r) => (
            <tr key={r} className="border-b border-hairline/60 last:border-0">
              {row.map((cell, c) =>
                c === 0 ? (
                  <th key={c} scope="row" className="text-left px-3 py-2 align-top font-medium text-ink-2">
                    {cell}
                  </th>
                ) : (
                  <td key={c} className="px-3 py-2 align-top text-ink-2">
                    {cell}
                  </td>
                )
              )}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

const SWOT_QUADRANTS = [
  { key: 'strengths', label: 'Strengths', ring: 'border-good/30', ink: 'text-good' },
  { key: 'weaknesses', label: 'Weaknesses', ring: 'border-critical/30', ink: 'text-critical' },
  { key: 'opportunities', label: 'Opportunities', ring: 'border-brand/30', ink: 'text-brand' },
  { key: 'threats', label: 'Threats', ring: 'border-warning/30', ink: 'text-warning' },
] as const

function SwotView({ swot }: { swot: NonNullable<CompleteMessage['data']['swot']> }) {
  return (
    <div className="grid gap-2 sm:grid-cols-2">
      {SWOT_QUADRANTS.map(({ key, label, ring, ink }) => (
        <div key={key} className={`rounded-lg border ${ring} bg-white/[0.02] p-3`}>
          <p className={`text-[10px] uppercase tracking-wider font-semibold mb-2 ${ink}`}>{label}</p>
          {swot[key].length === 0 ? (
            <p className="text-xs text-ink-3">None identified</p>
          ) : (
            <ul className="space-y-1.5">
              {swot[key].map((item, i) => (
                <li key={i} className="text-xs text-ink-2 leading-relaxed flex gap-1.5">
                  <span className={`mt-1.5 w-1 h-1 rounded-full shrink-0 ${ink} bg-current`} />
                  {item}
                </li>
              ))}
            </ul>
          )}
        </div>
      ))}
    </div>
  )
}

/**
 * Single-series magnitude: one sequential hue, so no legend is needed — the
 * title names the measure. Values are direct-labelled, bars carry a 4px
 * rounded data-end anchored to the baseline with a 2px gap between them.
 */
function ChartView({ chart }: { chart: NonNullable<CompleteMessage['data']['chart']> }) {
  const max = Math.max(...chart.points.map((p) => Math.abs(p.value)), 1)

  return (
    <figure className="rounded-lg border border-hairline bg-white/[0.02] p-3">
      {chart.title && (
        <figcaption className="text-xs font-medium text-ink mb-3">{chart.title}</figcaption>
      )}
      <div className="flex flex-col gap-0.5">
        {chart.points.map((point, i) => (
          <div key={i} className="group flex items-center gap-2" title={`${point.label}: ${point.value}`}>
            <span className="w-24 sm:w-28 shrink-0 text-[11px] text-ink-3 truncate text-right">
              {point.label}
            </span>
            <div className="flex-1 h-5 min-w-0">
              <div
                className="h-full bg-[--color-brand] transition-[width] group-hover:brightness-110"
                style={{
                  width: `${Math.max((Math.abs(point.value) / max) * 100, 1.5)}%`,
                  borderRadius: '0 4px 4px 0',
                }}
              />
            </div>
            <span className="w-14 shrink-0 text-[11px] text-ink-2 text-right tabular-nums">
              {point.value}
            </span>
          </div>
        ))}
      </div>
      {chart.y_label && <p className="text-[10px] text-ink-3 mt-2.5">{chart.y_label}</p>}
    </figure>
  )
}

function ClaimsView({ claims, dropped }: { claims: VerifiedClaim[]; dropped: number }) {
  return (
    <div>
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1 mb-2">
        <span className="flex items-center gap-1.5 text-[10px] uppercase tracking-wider text-good">
          <ShieldCheck className="w-3.5 h-3.5" />
          {claims.length} verified claim{claims.length === 1 ? '' : 's'}
        </span>
        {dropped > 0 && (
          <span className="flex items-center gap-1.5 text-[10px] uppercase tracking-wider text-warning">
            <Trash2 className="w-3 h-3" />
            {dropped} uncited deleted
          </span>
        )}
      </div>
      <ul className="space-y-1.5">
        {claims.map((claim, i) => (
          <li key={i} className="text-xs text-ink-2 leading-relaxed">
            {claim.text}{' '}
            <a
              href={claim.source_url}
              target="_blank"
              rel="noopener noreferrer"
              title={claim.snippet}
              className="inline-flex items-center gap-0.5 text-brand hover:underline decoration-dotted underline-offset-2"
            >
              {claim.source_title.slice(0, 36)}
              <ExternalLink className="w-2.5 h-2.5" />
            </a>
          </li>
        ))}
      </ul>
    </div>
  )
}

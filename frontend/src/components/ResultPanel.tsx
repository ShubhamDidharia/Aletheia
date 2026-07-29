'use client'

import {
  Check, ExternalLink, ShieldCheck, Trash2, Table2, Grid2x2, BarChart3, FileText,
  AlertTriangle,
} from 'lucide-react'
import type { CompleteMessage, VerifiedClaim, Contradiction, UIType } from '@/lib/websocket'
import { ResponseDispatcher } from '@/components/ResponseDispatcher'

const UI_META: Record<UIType, { icon: typeof Table2; label: string }> = {
  table: { icon: Table2, label: 'Comparison table' },
  swot: { icon: Grid2x2, label: 'SWOT' },
  chart: { icon: BarChart3, label: 'Chart' },
  report: { icon: FileText, label: 'Report' },
}

/**
 * The frame around a finished mission: headline, narrative, and the
 * generative-UI payload (delegated to ResponseDispatcher), then the evidence
 * that backs it — verified claims, contradictions, tasks and decisions.
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

        <ResponseDispatcher result={result} />

        {!!data.contradictions?.length && (
          <ContradictionsView contradictions={data.contradictions} />
        )}

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

/** Commit 9: disagreements found across sources, both sides shown and linked. */
function ContradictionsView({ contradictions }: { contradictions: Contradiction[] }) {
  return (
    <div className="rounded-lg border border-warning/30 bg-warning/[0.06] p-3">
      <p className="flex items-center gap-1.5 text-[10px] uppercase tracking-wider text-warning mb-2">
        <AlertTriangle className="w-3.5 h-3.5" />
        {contradictions.length} contradiction{contradictions.length === 1 ? '' : 's'} found
      </p>

      <ul className="space-y-2.5">
        {contradictions.map((conflict, i) => (
          <li key={i}>
            <p className="text-[11px] font-medium text-ink">{conflict.topic}</p>
            <div className="mt-1 space-y-1">
              {[
                { claim: conflict.claim_a, url: conflict.source_a },
                { claim: conflict.claim_b, url: conflict.source_b },
              ].map((side, s) => (
                <p key={s} className="text-[11px] text-ink-2 leading-relaxed flex gap-1.5">
                  <span className="text-warning shrink-0">{s === 0 ? 'A' : 'B'}</span>
                  <span>
                    “{side.claim}”{' '}
                    <a
                      href={side.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-brand hover:underline decoration-dotted underline-offset-2"
                    >
                      source
                      <ExternalLink className="inline w-2.5 h-2.5 ml-0.5" />
                    </a>
                  </span>
                </p>
              ))}
            </div>
          </li>
        ))}
      </ul>
    </div>
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

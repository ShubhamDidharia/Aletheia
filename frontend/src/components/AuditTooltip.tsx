'use client'

import { useId, useState, type ReactNode } from 'react'
import { ExternalLink, Quote } from 'lucide-react'
import type { VerifiedClaim, Source } from '@/lib/websocket'

export interface Provenance {
  url: string
  title: string
  snippet: string
}

/**
 * Build a URL -> provenance lookup from the claims and sources in a COMPLETE
 * event, so a cell citation can be resolved to the exact snippet it came from.
 */
export function buildProvenance(
  claims: VerifiedClaim[] = [],
  sources: Source[] = []
): Map<string, Provenance> {
  const map = new Map<string, Provenance>()
  for (const source of sources) {
    map.set(source.url, {
      url: source.url,
      title: source.title,
      snippet: source.snippet ?? '',
    })
  }
  // Claims win: their snippet is the passage the Auditor actually verified.
  for (const claim of claims) {
    map.set(claim.source_url, {
      url: claim.source_url,
      title: claim.source_title,
      snippet: claim.snippet,
    })
  }
  return map
}

function hostOf(url: string): string {
  try {
    return new URL(url).hostname.replace(/^www\./, '')
  } catch {
    return url
  }
}

interface AuditTooltipProps {
  provenance: Provenance
  children: ReactNode
  /** Anchor to the right edge when the cell is near the end of a row. */
  align?: 'left' | 'right'
}

/**
 * The Audit Trail: hover (or focus) a cited value to see the exact source
 * snippet and a link to the page it came from.
 *
 * Focusable so the trail is reachable by keyboard, not just by mouse.
 */
export function AuditTooltip({ provenance, children, align = 'left' }: AuditTooltipProps) {
  // Hover and keyboard-focus are handled in CSS (group-hover / group-focus-within)
  // so they work without depending on synthetic focus events. React state only
  // pins the tooltip open on click, which is the touch-device path.
  const [pinned, setPinned] = useState(false)
  const id = useId()

  return (
    <span className="group relative inline-flex">
      <button
        type="button"
        aria-describedby={id}
        aria-label={`${String(children)} — cited from ${hostOf(provenance.url)}`}
        aria-expanded={pinned}
        onClick={() => setPinned((v) => !v)}
        onKeyDown={(e) => {
          if (e.key === 'Escape' && pinned) {
            e.stopPropagation()
            setPinned(false)
          }
        }}
        className="text-left underline decoration-dotted decoration-brand/50 underline-offset-4 hover:decoration-brand focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand rounded-sm"
      >
        {children}
      </button>

      <span
        id={id}
        role="tooltip"
        data-open={pinned || undefined}
        className={[
          'absolute z-50 top-full mt-1.5 w-72 rounded-lg border border-hairline bg-raised p-3 shadow-xl',
          'text-left font-normal normal-case tracking-normal',
          'hidden group-hover:block group-focus-within:block data-[open]:block',
          align === 'right' ? 'right-0' : 'left-0',
        ].join(' ')}
      >
        <span className="flex items-center gap-1.5 text-[10px] uppercase tracking-wider text-brand">
          <Quote className="w-3 h-3" />
          Source snippet
        </span>

        <span className="mt-1.5 block text-[11px] leading-relaxed text-ink-2 line-clamp-6">
          {provenance.snippet || 'No snippet captured for this source.'}
        </span>

        <a
          href={provenance.url}
          target="_blank"
          rel="noopener noreferrer"
          className="mt-2 flex items-center gap-1 text-[11px] text-brand hover:underline"
        >
          <span className="truncate">{provenance.title || hostOf(provenance.url)}</span>
          <ExternalLink className="w-2.5 h-2.5 shrink-0" />
        </a>
      </span>
    </span>
  )
}

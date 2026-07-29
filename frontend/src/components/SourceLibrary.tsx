'use client'

import { useMemo, useState } from 'react'
import { Library, ExternalLink, FileText, Search, X } from 'lucide-react'
import type { Source } from '@/lib/websocket'

const STALENESS_YEARS = 3

function hostOf(url: string): string {
  try {
    return new URL(url).hostname.replace(/^www\./, '')
  } catch {
    return url
  }
}

function faviconFor(url: string): string | null {
  try {
    return `https://www.google.com/s2/favicons?domain=${new URL(url).hostname}&sz=64`
  } catch {
    return null
  }
}

interface SourceLibraryProps {
  sources: Source[]
  open: boolean
  onClose: () => void
}

export function SourceLibrary({ sources, open, onClose }: SourceLibraryProps) {
  const [filter, setFilter] = useState('')
  const currentYear = new Date().getFullYear()

  const shown = useMemo(() => {
    const needle = filter.trim().toLowerCase()
    if (!needle) return sources
    return sources.filter(
      (s) =>
        s.title.toLowerCase().includes(needle) ||
        hostOf(s.url).toLowerCase().includes(needle) ||
        (s.snippet ?? '').toLowerCase().includes(needle)
    )
  }, [sources, filter])

  return (
    <>
      {open && (
        <button
          aria-label="Close evidence panel"
          onClick={onClose}
          className="fixed inset-0 z-30 bg-black/60 xl:hidden"
        />
      )}

      <aside
        className={[
          'z-40 w-[336px] shrink-0 bg-panel border-l border-hairline flex-col',
          // Off-canvas below xl, a permanent column at xl and up.
          'fixed inset-y-0 right-0 xl:static',
          open ? 'flex' : 'hidden xl:flex',
        ].join(' ')}
      >
        <header className="h-14 px-4 flex items-center gap-2 border-b border-hairline shrink-0">
          <Library className="w-4 h-4 text-ink-3" />
          <h2 className="text-sm font-medium text-ink-2">Evidence</h2>
          <span className="ml-auto text-xs text-ink-3 tabular-nums">{sources.length}</span>
          <button
            onClick={onClose}
            aria-label="Close evidence panel"
            className="p-1.5 rounded-md text-ink-3 hover:text-ink hover:bg-raised xl:hidden"
          >
            <X className="w-4 h-4" />
          </button>
        </header>

        {sources.length > 4 && (
          <div className="px-3 py-2.5 border-b border-hairline shrink-0">
            <div className="relative">
              <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-ink-3 pointer-events-none" />
              <input
                value={filter}
                onChange={(e) => setFilter(e.target.value)}
                placeholder="Filter sources"
                aria-label="Filter sources"
                className="w-full h-8 pl-8 pr-7 rounded-lg bg-raised border border-transparent focus:border-brand/50 text-xs text-ink placeholder:text-ink-3 focus:outline-none"
              />
              {filter && (
                <button
                  onClick={() => setFilter('')}
                  aria-label="Clear filter"
                  className="absolute right-2 top-1/2 -translate-y-1/2 text-ink-3 hover:text-ink"
                >
                  <X className="w-3.5 h-3.5" />
                </button>
              )}
            </div>
          </div>
        )}

        <div className="flex-1 overflow-y-auto scroll-slim p-2.5 space-y-1.5">
          {sources.length === 0 && (
            <div className="px-5 py-10 text-center">
              <span className="w-10 h-10 rounded-full bg-raised grid place-items-center mx-auto mb-3">
                <Library className="w-4 h-4 text-ink-3" />
              </span>
              <p className="text-xs text-ink-3 leading-relaxed">
                Every page the agent reads lands here, with its publication year.
              </p>
            </div>
          )}

          {sources.length > 0 && shown.length === 0 && (
            <p className="px-3 py-6 text-xs text-ink-3 text-center">
              No sources match “{filter}”.
            </p>
          )}

          {shown.map((source) => {
            const favicon = faviconFor(source.url)
            const stale =
              typeof source.published_year === 'number' &&
              source.published_year < currentYear - STALENESS_YEARS

            return (
              <a
                key={source.url}
                href={source.url}
                target="_blank"
                rel="noopener noreferrer"
                title={source.snippet ?? source.title}
                className="source-pop block p-2.5 rounded-lg border border-hairline bg-raised/50 hover:bg-raised hover:border-brand/25 transition-colors group focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand"
              >
                <div className="flex items-start gap-2.5">
                  {favicon ? (
                    /* eslint-disable-next-line @next/next/no-img-element */
                    <img
                      src={favicon}
                      alt=""
                      width={16}
                      height={16}
                      className="w-4 h-4 mt-0.5 rounded-sm shrink-0"
                      onError={(e) => {
                        e.currentTarget.style.visibility = 'hidden'
                      }}
                    />
                  ) : (
                    <FileText className="w-4 h-4 mt-0.5 text-ink-3 shrink-0" />
                  )}

                  <div className="min-w-0 flex-1">
                    <p className="text-xs font-medium text-ink-2 group-hover:text-ink line-clamp-2 leading-snug">
                      {source.title}
                    </p>

                    <div className="mt-1.5 flex items-center gap-1.5 text-[10px] text-ink-3">
                      <span className="truncate">{hostOf(source.url)}</span>
                      <ExternalLink className="w-2.5 h-2.5 shrink-0 opacity-0 group-hover:opacity-100 transition-opacity" />
                    </div>

                    {(source.source_type === 'pdf' || source.published_year) && (
                      <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
                        {source.source_type === 'pdf' && (
                          <span className="px-1.5 py-px rounded text-[10px] font-medium bg-serious/15 text-serious">
                            PDF
                          </span>
                        )}
                        {source.published_year && (
                          <span
                            className={`px-1.5 py-px rounded text-[10px] font-medium tabular-nums ${
                              stale ? 'bg-warning/15 text-warning' : 'bg-white/[0.06] text-ink-3'
                            }`}
                          >
                            {source.published_year}
                            {stale && ' · dated'}
                          </span>
                        )}
                      </div>
                    )}
                  </div>
                </div>
              </a>
            )
          })}
        </div>
      </aside>
    </>
  )
}

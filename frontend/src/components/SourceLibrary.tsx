'use client'

import { Library, ExternalLink, FileText } from 'lucide-react'
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

export function SourceLibrary({ sources }: { sources: Source[] }) {
  const currentYear = new Date().getFullYear()

  return (
    <aside className="w-80 shrink-0 bg-zinc-950/60 border-l border-zinc-800 flex flex-col">
      <header className="px-5 py-4 border-b border-zinc-800 flex items-center gap-2">
        <Library className="w-4 h-4 text-zinc-400" />
        <h2 className="text-sm font-semibold uppercase tracking-wider text-zinc-400">
          Evidence
        </h2>
        <span className="ml-auto text-xs font-mono text-zinc-500">{sources.length}</span>
      </header>

      <div className="flex-1 overflow-y-auto p-3 space-y-2">
        {sources.length === 0 && (
          <div className="flex items-center justify-center h-full px-6 text-center">
            <p className="text-sm text-zinc-600">
              Sources the agent reads will appear here.
            </p>
          </div>
        )}

        {sources.map((source) => {
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
              className="block p-3 bg-zinc-900/70 hover:bg-zinc-900 border border-zinc-800 hover:border-zinc-700 rounded-lg transition-colors group"
            >
              <div className="flex items-start gap-2.5">
                {favicon ? (
                  // eslint-disable-next-line @next/next/no-img-element
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
                  <FileText className="w-4 h-4 mt-0.5 text-zinc-600 shrink-0" />
                )}

                <div className="min-w-0 flex-1">
                  <p className="text-xs font-medium text-zinc-200 line-clamp-2 group-hover:text-white">
                    {source.title}
                  </p>
                  <div className="flex items-center gap-1.5 mt-1.5 text-[11px] text-zinc-500">
                    <span className="truncate">{hostOf(source.url)}</span>
                    <ExternalLink className="w-3 h-3 shrink-0 opacity-0 group-hover:opacity-100 transition-opacity" />
                  </div>

                  <div className="flex flex-wrap items-center gap-1.5 mt-2">
                    {source.source_type === 'pdf' && (
                      <span className="px-1.5 py-0.5 rounded text-[10px] font-medium bg-rose-500/15 text-rose-300">
                        PDF
                      </span>
                    )}
                    {source.published_year && (
                      <span
                        className={`px-1.5 py-0.5 rounded text-[10px] font-medium ${
                          stale
                            ? 'bg-amber-500/15 text-amber-300'
                            : 'bg-zinc-700/50 text-zinc-400'
                        }`}
                      >
                        {source.published_year}
                        {stale && ' · dated'}
                      </span>
                    )}
                  </div>

                  {source.snippet && (
                    <p className="text-[11px] text-zinc-500 mt-2 line-clamp-3 leading-relaxed">
                      {source.snippet}
                    </p>
                  )}
                </div>
              </div>
            </a>
          )
        })}
      </div>
    </aside>
  )
}

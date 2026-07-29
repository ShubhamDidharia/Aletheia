'use client'

import { useMemo, useState } from 'react'
import { ArrowUp, ArrowDown, ChevronsUpDown, Search, X, AlertTriangle } from 'lucide-react'
import type { TableData } from '@/lib/websocket'
import { AuditTooltip, type Provenance } from '@/components/AuditTooltip'

interface DataTableProps {
  table: TableData
  provenance: Map<string, Provenance>
}

type SortDirection = 'asc' | 'desc' | null

/** Sort numerically when both values are numbers, alphabetically otherwise. */
function compare(a: string, b: string): number {
  const numA = Number(String(a).replace(/[^0-9.-]/g, ''))
  const numB = Number(String(b).replace(/[^0-9.-]/g, ''))
  const bothNumeric =
    Number.isFinite(numA) && Number.isFinite(numB) && /\d/.test(a) && /\d/.test(b)
  if (bothNumeric && numA !== numB) return numA - numB
  return String(a).localeCompare(String(b))
}

export function DataTable({ table, provenance }: DataTableProps) {
  const [sortColumn, setSortColumn] = useState<number | null>(null)
  const [direction, setDirection] = useState<SortDirection>(null)
  const [filter, setFilter] = useState('')

  const flagged = useMemo(() => new Set(table.flagged_rows ?? []), [table.flagged_rows])
  const reasons = table.flag_reasons ?? {}
  const citations = table.citations ?? []

  // Carry the original index so citations and flags stay attached after sorting.
  const prepared = useMemo(() => {
    const indexed = table.rows.map((cells, index) => ({ cells, index }))

    const needle = filter.trim().toLowerCase()
    const matched = needle
      ? indexed.filter((row) => row.cells.some((c) => String(c).toLowerCase().includes(needle)))
      : indexed

    if (sortColumn === null || direction === null) return matched

    return [...matched].sort((a, b) => {
      const result = compare(a.cells[sortColumn] ?? '', b.cells[sortColumn] ?? '')
      return direction === 'asc' ? result : -result
    })
  }, [table.rows, filter, sortColumn, direction])

  const toggleSort = (column: number) => {
    if (sortColumn !== column) {
      setSortColumn(column)
      setDirection('asc')
      return
    }
    if (direction === 'asc') setDirection('desc')
    else if (direction === 'desc') {
      setSortColumn(null)
      setDirection(null)
    } else setDirection('asc')
  }

  return (
    <div className="space-y-2">
      {table.rows.length > 3 && (
        <div className="relative max-w-xs">
          <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-ink-3 pointer-events-none" />
          <input
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            placeholder="Filter rows"
            aria-label="Filter table rows"
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
      )}

      <div className="overflow-x-auto scroll-slim rounded-lg border border-hairline">
        <table className="w-full text-xs border-collapse">
          <thead>
            <tr className="bg-white/[0.04]">
              {table.headers.map((header, column) => {
                const active = sortColumn === column
                const Icon = !active ? ChevronsUpDown : direction === 'asc' ? ArrowUp : ArrowDown
                return (
                  <th
                    key={column}
                    scope="col"
                    aria-sort={
                      active ? (direction === 'asc' ? 'ascending' : 'descending') : 'none'
                    }
                    className="text-left border-b border-hairline p-0"
                  >
                    <button
                      onClick={() => toggleSort(column)}
                      className="w-full flex items-center gap-1.5 px-3 py-2 font-semibold text-ink hover:bg-white/[0.04] transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-brand"
                    >
                      <span className="whitespace-nowrap">{header}</span>
                      <Icon
                        className={`w-3 h-3 shrink-0 ${active ? 'text-brand' : 'text-ink-3'}`}
                        aria-hidden
                      />
                    </button>
                  </th>
                )
              })}
            </tr>
          </thead>

          <tbody>
            {prepared.length === 0 && (
              <tr>
                <td
                  colSpan={table.headers.length}
                  className="px-3 py-6 text-center text-ink-3"
                >
                  No rows match “{filter}”.
                </td>
              </tr>
            )}

            {prepared.map(({ cells, index }) => {
              const isFlagged = flagged.has(index)
              return (
                <tr
                  key={index}
                  className={`border-b border-hairline/60 last:border-0 ${
                    isFlagged ? 'bg-warning/[0.07]' : ''
                  }`}
                >
                  {cells.map((cell, column) => {
                    const url = citations[index]?.[column] ?? ''
                    const source = url ? provenance.get(url) : undefined
                    const isRowHeader = column === 0

                    const content = source ? (
                      <AuditTooltip
                        provenance={source}
                        align={column >= cells.length - 1 ? 'right' : 'left'}
                      >
                        {cell}
                      </AuditTooltip>
                    ) : (
                      cell
                    )

                    const className = `px-3 py-2 align-top ${
                      isRowHeader ? 'font-medium text-ink-2' : 'text-ink-2'
                    }`

                    if (isRowHeader) {
                      return (
                        <th key={column} scope="row" className={`text-left ${className}`}>
                          <span className="flex items-start gap-1.5">
                            {isFlagged && (
                              <span title={reasons[String(index)]} className="shrink-0 mt-0.5">
                                <AlertTriangle
                                  className="w-3.5 h-3.5 text-warning"
                                  aria-label="Sources disagree on this row"
                                />
                              </span>
                            )}
                            <span>{content}</span>
                          </span>
                        </th>
                      )
                    }

                    return (
                      <td key={column} className={className}>
                        {content}
                      </td>
                    )
                  })}
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      {flagged.size > 0 && (
        <ul className="space-y-1">
          {[...flagged].map((index) => (
            <li key={index} className="flex items-start gap-1.5 text-[11px] text-warning">
              <AlertTriangle className="w-3 h-3 shrink-0 mt-0.5" />
              <span className="text-ink-2 leading-relaxed">{reasons[String(index)]}</span>
            </li>
          ))}
        </ul>
      )}

      <p className="text-[10px] text-ink-3">
        Underlined values are cited — hover or focus one to see its source snippet.
      </p>
    </div>
  )
}

'use client'

import { useMemo } from 'react'
import { FileText } from 'lucide-react'
import type { CompleteMessage } from '@/lib/websocket'
import { DataTable } from '@/components/DataTable'
import { SWOTComponent } from '@/components/SWOTComponent'
import { ChartComponent } from '@/components/ChartComponent'
import { buildProvenance } from '@/components/AuditTooltip'

/**
 * The switchboard (Commit 8).
 *
 * Reads `ui` from the COMPLETE event and renders the matching component. The
 * backend already guarantees the payload matches the declared shape — it
 * downgrades to "report" when it doesn't — so the fallbacks here are a second
 * line of defence, not the primary check.
 */
export function ResponseDispatcher({ result }: { result: CompleteMessage }) {
  const { ui, data } = result

  const provenance = useMemo(
    () => buildProvenance(data.claims ?? [], data.sources ?? []),
    [data.claims, data.sources]
  )

  switch (ui) {
    case 'table':
      return data.table?.rows?.length ? (
        <DataTable table={data.table} provenance={provenance} />
      ) : (
        <ReportFallback />
      )

    case 'swot':
      return data.swot ? <SWOTComponent swot={data.swot} /> : <ReportFallback />

    case 'chart':
      return data.chart?.points?.length ? (
        <ChartComponent chart={data.chart} />
      ) : (
        <ReportFallback />
      )

    case 'report':
      // The narrative and claim list are rendered by ResultPanel around this.
      return null

    default:
      return <ReportFallback />
  }
}

function ReportFallback() {
  return (
    <p className="flex items-center gap-1.5 text-[11px] text-ink-3">
      <FileText className="w-3.5 h-3.5" />
      Presented as a written summary — the findings didn’t fit a table, SWOT or chart.
    </p>
  )
}

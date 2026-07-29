'use client'

import { useMemo, useState } from 'react'
import {
  Bar, BarChart, CartesianGrid, Cell, Line, LineChart,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'
import { Table2, BarChart3 } from 'lucide-react'
import type { ChartData } from '@/lib/websocket'

// Dark-mode chart chrome, per the project's palette.
const SERIES = '#3987e5'
const SERIES_HOVER = '#5598e7'
const GRID = '#2c2c2a'
const AXIS = '#383835'
const MUTED = '#898781'
const SURFACE = '#1a1a19'

/** Time-ish labels (years, quarters, month names) read better as a line. */
function looksTemporal(labels: string[]): boolean {
  if (labels.length < 3) return false
  const temporal = /^(19|20)\d{2}|^q[1-4]\b|^(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)/i
  return labels.every((l) => temporal.test(l.trim()))
}

function ChartTooltip({ active, payload, label, unit }: any) {
  if (!active || !payload?.length) return null
  return (
    <div className="rounded-lg border border-hairline bg-raised px-2.5 py-2 shadow-xl">
      <p className="text-[11px] font-medium text-ink">{label}</p>
      <p className="text-[11px] text-ink-2 tabular-nums">
        {payload[0].value}
        {unit ? ` ${unit}` : ''}
      </p>
    </div>
  )
}

/**
 * Single-series magnitude, so one sequential hue and no legend — the title
 * names the measure. A table view is always available, which is both the
 * accessibility fallback and the honest way to read exact values.
 */
export function ChartComponent({ chart }: { chart: ChartData }) {
  const [asTable, setAsTable] = useState(false)

  const labels = useMemo(() => chart.points.map((p) => p.label), [chart.points])
  const isLine = useMemo(() => looksTemporal(labels), [labels])
  const data = useMemo(
    () => chart.points.map((p) => ({ label: p.label, value: p.value })),
    [chart.points]
  )
  const [hovered, setHovered] = useState<number | null>(null)

  return (
    <figure className="rounded-lg border border-hairline bg-white/[0.02] p-3">
      <div className="flex items-start gap-2 mb-3">
        <figcaption className="text-xs font-medium text-ink">
          {chart.title || chart.y_label || 'Findings'}
        </figcaption>
        <button
          onClick={() => setAsTable((v) => !v)}
          className="ml-auto flex items-center gap-1 px-2 py-0.5 rounded-md text-[10px] text-ink-3 hover:text-ink hover:bg-raised transition-colors"
          aria-pressed={asTable}
        >
          {asTable ? <BarChart3 className="w-3 h-3" /> : <Table2 className="w-3 h-3" />}
          {asTable ? 'Chart' : 'Table'}
        </button>
      </div>

      {asTable ? (
        <div className="overflow-x-auto scroll-slim rounded-lg border border-hairline">
          <table className="w-full text-xs">
            <thead>
              <tr className="bg-white/[0.04]">
                <th scope="col" className="text-left px-3 py-2 font-semibold text-ink">
                  {chart.x_label || 'Label'}
                </th>
                <th scope="col" className="text-right px-3 py-2 font-semibold text-ink">
                  {chart.y_label || 'Value'}
                </th>
              </tr>
            </thead>
            <tbody>
              {data.map((point, i) => (
                <tr key={i} className="border-t border-hairline/60">
                  <th scope="row" className="text-left px-3 py-1.5 font-medium text-ink-2">
                    {point.label}
                  </th>
                  <td className="px-3 py-1.5 text-right text-ink-2 tabular-nums">{point.value}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="h-64 w-full">
          <ResponsiveContainer width="100%" height="100%">
            {isLine ? (
              <LineChart data={data} margin={{ top: 8, right: 12, bottom: 4, left: 4 }}>
                <CartesianGrid stroke={GRID} vertical={false} />
                <XAxis
                  dataKey="label"
                  tick={{ fill: MUTED, fontSize: 11 }}
                  axisLine={{ stroke: AXIS }}
                  tickLine={false}
                />
                <YAxis
                  tick={{ fill: MUTED, fontSize: 11 }}
                  axisLine={false}
                  tickLine={false}
                  width={44}
                />
                <Tooltip
                  content={<ChartTooltip unit={chart.y_label} />}
                  cursor={{ stroke: AXIS }}
                />
                <Line
                  type="monotone"
                  dataKey="value"
                  stroke={SERIES}
                  strokeWidth={2}
                  dot={{ r: 4, fill: SERIES, stroke: SURFACE, strokeWidth: 2 }}
                  activeDot={{ r: 6, fill: SERIES, stroke: SURFACE, strokeWidth: 2 }}
                />
              </LineChart>
            ) : (
              <BarChart
                data={data}
                margin={{ top: 8, right: 12, bottom: 4, left: 4 }}
                onMouseLeave={() => setHovered(null)}
              >
                <CartesianGrid stroke={GRID} vertical={false} />
                <XAxis
                  dataKey="label"
                  tick={{ fill: MUTED, fontSize: 11 }}
                  axisLine={{ stroke: AXIS }}
                  tickLine={false}
                  interval={0}
                  height={40}
                />
                <YAxis
                  tick={{ fill: MUTED, fontSize: 11 }}
                  axisLine={false}
                  tickLine={false}
                  width={44}
                />
                <Tooltip
                  content={<ChartTooltip unit={chart.y_label} />}
                  cursor={{ fill: 'rgba(255,255,255,0.04)' }}
                />
                <Bar
                  dataKey="value"
                  radius={[4, 4, 0, 0]}
                  maxBarSize={56}
                  onMouseEnter={(_, index) => setHovered(index)}
                >
                  {data.map((_, index) => (
                    <Cell key={index} fill={hovered === index ? SERIES_HOVER : SERIES} />
                  ))}
                </Bar>
              </BarChart>
            )}
          </ResponsiveContainer>
        </div>
      )}

      {chart.y_label && !asTable && (
        <p className="text-[10px] text-ink-3 mt-2">{chart.y_label}</p>
      )}
    </figure>
  )
}

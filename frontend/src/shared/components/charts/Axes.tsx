import type { ScaleLinear } from 'd3-scale'
import { formatCompact, formatCredits } from '@/shared/utils/format'

/** Hairline gridlines at clean values, with their labels on the left. */
export function YGrid({ y, width, ticks = 4 }: { y: ScaleLinear<number, number>; width: number; ticks?: number }) {
  const compact = y.domain()[1] >= 10_000
  return (
    <g aria-hidden>
      {y.ticks(ticks).map((t) => (
        <g key={t} transform={`translate(0,${Math.round(y(t)) + 0.5})`}>
          <line x2={width} className={t === 0 ? 'stroke-chart-axis' : 'stroke-chart-grid'} />
          <text x={-8} dy="0.32em" textAnchor="end" className="fill-chart-label text-2xs tabular-nums">
            {compact ? formatCompact(t) : formatCredits(t)}
          </text>
        </g>
      ))}
    </g>
  )
}

/** Labels under the plot; the outermost ones hug the edges instead of overflowing them. */
export function XLabels({ ticks, y, width }: { ticks: { x: number; label: string }[]; y: number; width: number }) {
  return (
    <g aria-hidden>
      {ticks.map(({ x, label }) => (
        <text
          key={label}
          x={x}
          y={y}
          dy="1.1em"
          textAnchor={x < 24 ? 'start' : x > width - 24 ? 'end' : 'middle'}
          className="fill-chart-label text-2xs"
        >
          {label}
        </text>
      ))}
    </g>
  )
}

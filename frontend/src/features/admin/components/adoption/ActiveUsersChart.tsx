import { line } from 'd3-shape'
import { XLabels, YGrid } from '@/shared/components/charts/Axes'
import { ChartTooltip, LineKey, TooltipRow } from '@/shared/components/charts/ChartTooltip'
import { Legend, LegendItem } from '@/shared/components/charts/Legend'
import { MARGIN, columnPath } from '@/shared/components/charts/chartMath'
import { useDayBars } from '@/shared/components/charts/useDayBars'
import { Swatch } from '@/shared/components/ui/Swatch'
import { formatCredits, formatDay, formatLongDay, formatPercent } from '@/shared/utils/format'
import type { OrgAdoption } from '@/features/admin/api/admin'

type AdoptionDay = OrgAdoption['daily'][number]

const MAX_BAR = 22 // px

/**
 * People active each day (bars), and active on any day of the last 7 and 28 days (lines).
 * Hover a day, or focus the chart and use ←/→, for its numbers.
 */
export function ActiveUsersChart({ daily, seats }: { daily: AdoptionDay[]; seats: number }) {
  const { boxRef, width, height, innerW, innerH, y, barW, centre, barLeft, slot, ticks, cursor, onPointerMove } =
    useDayBars(
      daily.map((d) => d.day),
      Math.max(0, ...daily.map((d) => d.active_28d)),
      MAX_BAR,
    )
  const path = (value: (d: AdoptionDay) => number) =>
    line<AdoptionDay>()
      .x((_, i) => centre(i))
      .y((d) => y(value(d)))(daily) ?? ''

  const active = cursor.active
  const hover = active === null ? null : daily[active]
  const first = daily[0]
  const last = daily[daily.length - 1]

  return (
    <div className="flex flex-col gap-3">
      <div
        ref={boxRef}
        className="relative rounded-sm outline-offset-4 focus-visible:outline-2 focus-visible:outline-accent"
        style={{ height }}
        role="group"
        aria-roledescription="chart"
        aria-label={
          first
            ? `People active per day, ${formatDay(first.day)} to ${formatDay(last.day)}, with the number active ` +
              `in the last 7 and 28 days. Use the arrow keys to read each day.`
            : 'No days with usage metrics yet'
        }
        {...cursor.focusProps}
      >
        {width > 0 && (
          <svg
            width={width}
            height={height}
            className="block touch-pan-y select-none"
            onPointerMove={onPointerMove}
            onPointerDown={onPointerMove}
            onPointerLeave={() => cursor.setActive(null)}
            aria-hidden
          >
            <g transform={`translate(${MARGIN.left},${MARGIN.top})`}>
              <YGrid y={y} width={innerW} />
              <XLabels ticks={ticks} y={innerH + 6} width={innerW} />
              {active !== null && <rect {...slot(active)} height={innerH} className="fill-well" rx={3} />}
              {daily.map((d, i) => (
                <path
                  key={d.day}
                  d={columnPath(barLeft(i), y(d.active_users), barW, innerH - y(d.active_users))}
                  className="fill-series-3 transition-opacity duration-100"
                  opacity={active !== null && active !== i ? 0.45 : 1}
                />
              ))}
              <path
                d={path((d) => d.active_28d)}
                className="fill-none stroke-chart-projection"
                strokeWidth={1.5}
                strokeDasharray="4 3"
              />
              <path d={path((d) => d.active_7d)} className="fill-none stroke-chart-line" strokeWidth={2} />
              <line x2={innerW} y1={innerH + 0.5} y2={innerH + 0.5} className="stroke-chart-axis" />
            </g>
          </svg>
        )}
        {hover && active !== null && (
          <ChartTooltip
            x={MARGIN.left + centre(active)}
            y={MARGIN.top + Math.max(0, Math.min(y(hover.active_28d), innerH - 110))}
            boxWidth={width}
            title={formatLongDay(hover.day)}
          >
            <TooltipRow
              mark={<Swatch className="bg-series-3" />}
              value={formatCredits(hover.active_users)}
              label="active that day"
            />
            <TooltipRow
              mark={<LineKey className="bg-chart-line" />}
              value={formatCredits(hover.active_7d)}
              label="in the last 7 days"
            />
            <TooltipRow
              mark={<LineKey dashed className="border-chart-projection" />}
              value={formatCredits(hover.active_28d)}
              label={`in the last 28 days${seats ? ` · ${formatPercent(hover.active_28d / seats)} of seats` : ''}`}
            />
            <TooltipRow value={formatCredits(hover.prompts)} label="prompts" />
            <TooltipRow value={formatPercent(hover.acceptance_rate)} label="acceptance" />
          </ChartTooltip>
        )}
        <div className="sr-only" aria-live="polite">
          {hover &&
            `${formatLongDay(hover.day)}: ${hover.active_users} active that day, ${hover.active_7d} in the last 7 days, ` +
              `${hover.active_28d} in the last 28 days`}
        </div>
      </div>
      <Legend>
        <LegendItem mark={<Swatch className="bg-series-3" />}>Active that day</LegendItem>
        <LegendItem mark={<LineKey className="bg-chart-line" />}>Active in the last 7 days</LegendItem>
        <LegendItem mark={<LineKey dashed className="border-chart-projection" />}>
          Active in the last 28 days
        </LegendItem>
      </Legend>
    </div>
  )
}

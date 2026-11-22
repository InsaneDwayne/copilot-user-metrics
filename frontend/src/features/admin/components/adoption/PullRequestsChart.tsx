import { XLabels, YGrid } from '@/shared/components/charts/Axes'
import { ChartTooltip, TooltipRow } from '@/shared/components/charts/ChartTooltip'
import { Legend, LegendItem } from '@/shared/components/charts/Legend'
import { MARGIN, columnPath } from '@/shared/components/charts/chartMath'
import { useDayBars } from '@/shared/components/charts/useDayBars'
import { Swatch } from '@/shared/components/ui/Swatch'
import { formatCredits, formatDay, formatLongDay } from '@/shared/utils/format'
import type { OrgReport } from '@/features/admin/api/admin'

type PullRequestDay = OrgReport['daily'][number]

const MAX_BAR = 22 // px
const GAP = 2 // px of surface between the two segments

/**
 * Pull requests created each day, split into those Copilot created and the rest.
 * Hover a day, or focus the chart and use ←/→, for its numbers.
 */
export function PullRequestsChart({ daily }: { daily: PullRequestDay[] }) {
  const { boxRef, width, height, innerW, innerH, y, barW, centre, barLeft, slot, ticks, cursor, onPointerMove } =
    useDayBars(
      daily.map((d) => d.day),
      Math.max(0, ...daily.map((d) => d.created)),
      MAX_BAR,
    )

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
            ? `Pull requests created per day, ${formatDay(first.day)} to ${formatDay(last.day)}, ` +
              `split into those Copilot created and the rest. Use the arrow keys to read each day.`
            : 'No pull request numbers yet'
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
              {daily.map((d, i) => {
                const left = barLeft(i)
                const copilotTop = y(d.created_by_copilot)
                const top = y(d.created)
                const others = d.created - d.created_by_copilot
                // Copilot's part sits on the baseline; the rest stacks above it with a surface gap.
                const gap = d.created_by_copilot > 0 && copilotTop - top > GAP + 1 ? GAP : 0
                return (
                  <g
                    key={d.day}
                    className="transition-opacity duration-100"
                    opacity={active !== null && active !== i ? 0.45 : 1}
                  >
                    {d.created_by_copilot > 0 && (
                      <path
                        d={
                          others > 0
                            ? `M${left},${innerH}V${copilotTop}H${left + barW}V${innerH}Z`
                            : columnPath(left, copilotTop, barW, innerH - copilotTop)
                        }
                        className="fill-series-1"
                      />
                    )}
                    {others > 0 && (
                      <path d={columnPath(left, top, barW, copilotTop - top - gap)} className="fill-series-7" />
                    )}
                  </g>
                )
              })}
              <line x2={innerW} y1={innerH + 0.5} y2={innerH + 0.5} className="stroke-chart-axis" />
            </g>
          </svg>
        )}
        {hover && active !== null && (
          <ChartTooltip
            x={MARGIN.left + centre(active)}
            y={MARGIN.top + Math.max(0, Math.min(y(hover.created), innerH - 110))}
            boxWidth={width}
            title={formatLongDay(hover.day)}
          >
            <TooltipRow
              mark={<Swatch className="bg-series-1" />}
              value={formatCredits(hover.created_by_copilot)}
              label="created by Copilot"
            />
            <TooltipRow
              mark={<Swatch className="bg-series-7" />}
              value={formatCredits(hover.created - hover.created_by_copilot)}
              label="created by people"
            />
            <TooltipRow
              value={formatCredits(hover.merged)}
              label={`merged (${formatCredits(hover.merged_created_by_copilot)} by Copilot)`}
            />
            <TooltipRow value={formatCredits(hover.reviewed_by_copilot)} label="reviewed by Copilot" />
          </ChartTooltip>
        )}
        <div className="sr-only" aria-live="polite">
          {hover &&
            `${formatLongDay(hover.day)}: ${hover.created} pull requests created, ${hover.created_by_copilot} by Copilot; ` +
              `${hover.merged} merged`}
        </div>
      </div>
      <Legend>
        <LegendItem mark={<Swatch className="bg-series-1" />}>Created by Copilot</LegendItem>
        <LegendItem mark={<Swatch className="bg-series-7" />}>Created by people</LegendItem>
      </Legend>
    </div>
  )
}

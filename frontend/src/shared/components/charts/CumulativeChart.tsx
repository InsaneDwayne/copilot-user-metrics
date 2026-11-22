import { scaleLinear } from 'd3-scale'
import { area, line } from 'd3-shape'
import { useId, useMemo, type PointerEvent, type ReactNode } from 'react'
import type { DailyCredits, Projection } from '@/shared/api/schemas'
import { eachDay } from '@/shared/utils/dates'
import { formatDay, formatLongDay, formatUsd } from '@/shared/utils/format'
import type { Measure } from '@/shared/utils/measures'
import { XLabels, YGrid } from './Axes'
import { ChartTooltip, LineKey, TooltipRow } from './ChartTooltip'
import { Legend, LegendItem } from './Legend'
import { MARGIN, axisDays, cumulative, cumulativeAt, type ChartPeriod } from './chartMath'
import { useChartCursor } from './useChartCursor'
import { fluidChartHeight, useChartWidth } from './useChartSize'

interface CumulativeChartProps {
  daily: DailyCredits[]
  period: ChartPeriod
  projection: Projection | null
  /** What the line counts. */
  measure: Measure
}

/**
 * Running total of a measure (e.g. AI credits), with a straight-line projection to the end of the period.
 * Hover (or focus and use ←/→) to read the total at any day.
 */
export function CumulativeChart({ daily, period, projection, measure }: CumulativeChartProps) {
  const [boxRef, width] = useChartWidth<HTMLDivElement>()
  const height = fluidChartHeight(width)
  const gradientId = useId()
  const days = useMemo(() => eachDay(period.start, period.end), [period.start, period.end])
  const c = useMemo(() => cumulative(daily, period, projection), [daily, period, projection])
  const showProjection = projection !== null && c.elapsed < c.total
  // Cursor index i (0-based) is the end of days[i], i.e. x = i + 1 on the plot.
  const cursor = useChartCursor(days.length, Math.max(0, c.elapsed - 1))

  const innerW = Math.max(0, width - MARGIN.left - MARGIN.right)
  const innerH = height - MARGIN.top - MARGIN.bottom
  const x = scaleLinear().domain([0, c.total]).range([0, innerW])
  const y = scaleLinear()
    .domain([0, Math.max(c.projectedEnd, c.used, 1) * 1.08])
    .range([innerH, 0])
    .nice(4)

  const actual: [number, number][] = [[0, 0], ...c.points]
  const linePath = line<[number, number]>()
    .x(([d]) => x(d))
    .y(([, v]) => y(v))(actual)
  const areaPath = area<[number, number]>()
    .x(([d]) => x(d))
    .y0(innerH)
    .y1(([, v]) => y(v))(actual)
  const today = { x: x(c.elapsed), y: y(c.used) }
  const end = { x: x(c.total), y: y(c.projectedEnd) }

  const onPointerMove = (e: PointerEvent<SVGSVGElement>) => {
    const px = e.clientX - e.currentTarget.getBoundingClientRect().left - MARGIN.left
    cursor.setActive(x.invert(px) - 1)
  }

  const active = cursor.active
  const hover = active === null ? null : describe(active + 1)
  function describe(index: number) {
    const known = index <= c.elapsed
    const future = !known && showProjection
    const value = cumulativeAt(c, index)
    const day = days[index - 1]
    const dayCredits = known ? value - cumulativeAt(c, index - 1) : null
    const text = known
      ? `${formatLongDay(day)}: ${measure.format(value)} ${measure.label} so far, ${measure.format(dayCredits ?? 0)} that day`
      : future
        ? `${formatLongDay(day)}: about ${measure.format(value)} ${measure.label} projected`
        : `${formatLongDay(day)}: no data yet`
    return { index, day, known, future, value, dayCredits, text, px: x(index), py: y(value) }
  }

  const summary =
    `Cumulative ${measure.label}, ${formatDay(period.start)} to ${formatDay(period.end)}: ` +
    `${measure.format(c.used)} used` +
    (showProjection ? `, about ${measure.format(c.projectedEnd)} projected by the end of the period.` : '.')

  return (
    <div className="flex flex-col gap-4">
      <Legend>
        <LegendItem mark={<span className="h-0.5 w-3.5 bg-chart-line" />}>Used</LegendItem>
        {showProjection && projection && (
          <LegendItem mark={<span className="w-3.5 border-t-2 border-dashed border-chart-projection" />}>
            Projected · ≈ {formatUsd(projection.projected_gross_usd)} list value
          </LegendItem>
        )}
      </Legend>
      <div
        ref={boxRef}
        className="relative rounded-sm outline-offset-4 focus-visible:outline-2 focus-visible:outline-accent"
        style={{ height }}
        role="group"
        aria-roledescription="chart"
        aria-label={`${summary} Use the arrow keys to read each day.`}
        {...cursor.focusProps}
      >
        {width > 0 && (
          <svg
            width={width}
            height={height}
            className="block touch-pan-y overflow-visible select-none"
            onPointerMove={onPointerMove}
            onPointerDown={onPointerMove}
            onPointerLeave={() => cursor.setActive(null)}
            aria-hidden
          >
            <defs>
              <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1" className="text-chart-line">
                <stop offset="0" stopColor="currentColor" stopOpacity="0.22" />
                <stop offset="1" stopColor="currentColor" stopOpacity="0" />
              </linearGradient>
            </defs>
            <g transform={`translate(${MARGIN.left},${MARGIN.top})`}>
              <YGrid y={y} width={innerW} />
              <XLabels
                ticks={axisDays(period, innerW).map((d) => ({ x: x(days.indexOf(d) + 1), label: formatDay(d) }))}
                y={innerH + 6}
                width={innerW}
              />
              {areaPath && <path d={areaPath} fill={`url(#${gradientId})`} />}
              {showProjection && (
                <path
                  d={`M${today.x},${today.y}L${end.x},${end.y}`}
                  className="fill-none stroke-chart-projection"
                  strokeWidth={2}
                  strokeDasharray="5 4"
                />
              )}
              {linePath && (
                <path
                  d={linePath}
                  className="fill-none stroke-chart-line"
                  strokeWidth={2}
                  strokeLinejoin="round"
                  strokeLinecap="round"
                />
              )}
              {showProjection && (
                // Above the line's end: the line falls away to the left, so it never crosses the label.
                <text
                  x={end.x}
                  y={end.y}
                  dy="-0.8em"
                  textAnchor="end"
                  className="fill-fg-soft stroke-surface text-xs tabular-nums [paint-order:stroke]"
                  strokeWidth={4}
                  strokeLinejoin="round"
                >
                  ~{measure.format(c.projectedEnd)} projected
                </text>
              )}

              {/* "Today": the latest known total, labelled directly unless the cursor is out. */}
              {c.elapsed > 0 && (
                <circle
                  cx={today.x}
                  cy={today.y}
                  r={4.5}
                  className="fill-chart-line stroke-surface drop-shadow-glow"
                  strokeWidth={2}
                />
              )}
              {c.elapsed > 0 && !hover && (
                <TodayLabel x={today.x} y={today.y} leftOfDot={c.elapsed > c.total * 0.7}>
                  {measure.format(c.used)}
                  {showProjection ? ' · today' : ''}
                </TodayLabel>
              )}

              {hover && (
                <g className="pointer-events-none">
                  <line
                    x1={hover.px}
                    x2={hover.px}
                    y1={0}
                    y2={innerH}
                    className="stroke-chart-cursor"
                    shapeRendering="crispEdges"
                  />
                  {(hover.known || hover.future) && (
                    <circle
                      cx={hover.px}
                      cy={hover.py}
                      r={4.5}
                      className={
                        hover.known ? 'fill-chart-line stroke-surface' : 'fill-chart-projection stroke-surface'
                      }
                      strokeWidth={2}
                    />
                  )}
                </g>
              )}
            </g>
          </svg>
        )}
        {hover && (
          <ChartTooltip
            x={MARGIN.left + hover.px}
            y={MARGIN.top + Math.min(hover.py, innerH - 64)}
            boxWidth={width}
            title={formatLongDay(hover.day)}
          >
            {hover.known ? (
              <>
                <TooltipRow
                  mark={<LineKey className="bg-chart-line" />}
                  value={measure.format(hover.value)}
                  label="running total"
                />
                <TooltipRow value={`+${measure.format(hover.dayCredits ?? 0)}`} label="that day" />
              </>
            ) : hover.future ? (
              <TooltipRow
                mark={<LineKey dashed className="border-chart-projection" />}
                value={`~${measure.format(hover.value)}`}
                label="projected total"
              />
            ) : (
              <div className="text-fg-muted">No data for this day yet</div>
            )}
          </ChartTooltip>
        )}
        <div className="sr-only" aria-live="polite">
          {hover?.text}
        </div>
      </div>
    </div>
  )
}

function TodayLabel({ x, y, leftOfDot, children }: { x: number; y: number; leftOfDot: boolean; children: ReactNode }) {
  return (
    <text
      x={leftOfDot ? x - 10 : x + 10}
      y={y}
      dy="1.4em"
      textAnchor={leftOfDot ? 'end' : 'start'}
      className="fill-fg stroke-surface text-xs tabular-nums [paint-order:stroke]"
      strokeWidth={4}
      strokeLinejoin="round"
    >
      {children}
    </text>
  )
}

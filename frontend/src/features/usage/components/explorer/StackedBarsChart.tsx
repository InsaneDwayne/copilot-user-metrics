import { cumsum } from 'd3-array'
import { scaleBand, scaleLinear } from 'd3-scale'
import type { PointerEvent } from 'react'
import { XLabels, YGrid } from '@/shared/components/charts/Axes'
import { ChartTooltip, LineKey, TooltipRow } from '@/shared/components/charts/ChartTooltip'
import { MARGIN, columnPath } from '@/shared/components/charts/chartMath'
import { useChartCursor } from '@/shared/components/charts/useChartCursor'
import { fluidChartHeight, useChartWidth } from '@/shared/components/charts/useChartSize'
import { Swatch } from '@/shared/components/ui/Swatch'
import { seriesBg, seriesFill } from '@/shared/theme/tokens'
import { formatUsd } from '@/shared/utils/format'
import { bucketLabel, tickIndexes, tickLabel } from '@/features/usage/utils/bucketLabels'
import type { Measure } from '@/shared/utils/measures'
import type { Bucket, Granularity, ModelSeries } from '@/features/usage/utils/usageSeries'

interface StackedBarsChartProps {
  buckets: Bucket[]
  granularity: Granularity
  series: ModelSeries[]
  /** A model picked in the models list: the others fade back; nothing is repainted or restacked. */
  focus: string | null
  /** Admins and organization readers also see what GitHub billed. */
  showBilling: boolean
  /** What the bars count. */
  measure: Measure
}

const MAX_BAR = 28 // px: bars never fill a wide slot
const GAP = 2 // px of surface between stacked segments

/**
 * AI credits per day, week or month, each bar stacked by model (biggest model at the bottom).
 * Bars after today show the projection as a dashed outline. Hover a bar, or focus the chart
 * and use ←/→, for its per-model numbers.
 */
export function StackedBarsChart({ buckets, granularity, series, focus, showBilling, measure }: StackedBarsChartProps) {
  const [boxRef, width] = useChartWidth<HTMLDivElement>()
  const height = fluidChartHeight(width)
  const lastKnown = buckets.findLastIndex((b) => b.known)
  const cursor = useChartCursor(buckets.length, Math.max(0, lastKnown))
  const byKey = new Map(series.map((s) => [s.key, s]))

  const innerW = Math.max(0, width - MARGIN.left - MARGIN.right)
  const innerH = height - MARGIN.top - MARGIN.bottom
  const x = scaleBand<string>()
    .domain(buckets.map((b) => b.start))
    .range([0, innerW])
    .paddingInner(buckets.length > 62 ? 0.12 : 0.22)
    .paddingOuter(0.1)
  const y = scaleLinear()
    .domain([0, Math.max(1, ...buckets.map((b) => b.credits + b.projected)) * 1.08])
    .range([innerH, 0])
    .nice(4)
  const barW = Math.min(MAX_BAR, x.bandwidth())
  const centre = (i: number) => (x(buckets[i].start) ?? 0) + x.bandwidth() / 2

  const onPointerMove = (e: PointerEvent<SVGSVGElement>) => {
    if (!buckets.length) return
    const px = e.clientX - e.currentTarget.getBoundingClientRect().left - MARGIN.left
    cursor.setActive((px - centre(0)) / x.step())
  }

  const active = cursor.active
  const hover = active === null ? null : buckets[active]
  const total = buckets.reduce((sum, b) => sum + b.credits, 0)
  const anyProjected = buckets.some((b) => b.projected > 0)

  return (
    <div className="flex flex-col gap-3">
      <div
        ref={boxRef}
        className="relative rounded-sm outline-offset-4 focus-visible:outline-2 focus-visible:outline-accent"
        style={{ height }}
        role="group"
        aria-roledescription="chart"
        aria-label={
          `${measure.label} per ${granularity} by model, ${bucketLabel(buckets[0], 'day')} to ` +
          `${bucketLabel({ ...buckets[buckets.length - 1], start: buckets[buckets.length - 1].end }, 'day')}: ` +
          `${measure.format(total)} in total. Use the arrow keys to read each ${granularity}.`
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
              <XLabels
                ticks={tickIndexes(buckets.length, innerW).map((i) => ({
                  x: centre(i),
                  label: tickLabel(buckets[i], granularity),
                }))}
                y={innerH + 6}
                width={innerW}
              />
              {active !== null && (
                <rect
                  x={(x(buckets[active].start) ?? 0) - (x.step() - x.bandwidth()) / 2}
                  width={x.step()}
                  height={innerH}
                  className="fill-well"
                  rx={3}
                />
              )}
              {buckets.map((b, i) => (
                <StackedColumn
                  key={b.start}
                  bucket={b}
                  x={(x(b.start) ?? 0) + (x.bandwidth() - barW) / 2}
                  width={barW}
                  y={y}
                  indexOf={(key) => byKey.get(key)?.index ?? 0}
                  focus={focus}
                  dimmed={active !== null && active !== i}
                />
              ))}
              <line x2={innerW} y1={innerH + 0.5} y2={innerH + 0.5} className="stroke-chart-axis" />
            </g>
          </svg>
        )}
        {hover && active !== null && (
          <ChartTooltip
            x={MARGIN.left + centre(active)}
            y={MARGIN.top + Math.max(0, Math.min(y(hover.credits), innerH - 48 - hover.segments.length * 20))}
            boxWidth={width}
            title={bucketLabel(hover, granularity)}
          >
            <Readout bucket={hover} byKey={byKey} focus={focus} showBilling={showBilling} measure={measure} />
          </ChartTooltip>
        )}
        <div className="sr-only" aria-live="polite">
          {hover && describe(hover, granularity, byKey, measure)}
        </div>
      </div>
      {anyProjected && (
        <div className="flex items-center gap-1.5 text-xs text-fg-muted">
          <Swatch className="border border-dashed border-chart-axis bg-transparent" />
          Projected at the pace so far
        </div>
      )}
    </div>
  )
}

function StackedColumn({
  bucket: b,
  x,
  width,
  y,
  indexOf,
  focus,
  dimmed,
}: {
  bucket: Bucket
  x: number
  width: number
  y: (v: number) => number
  indexOf: (key: string) => number
  focus: string | null
  dimmed: boolean
}) {
  // Running total at the top of each segment.
  const tops = cumsum(b.segments, (s) => s.credits)
  const last = b.segments.length - 1
  const projectedTop = y(b.credits + b.projected)
  const actualTop = y(b.credits)
  return (
    <g opacity={dimmed ? 0.45 : 1} className="transition-opacity duration-100">
      {b.segments.map((s, i) => {
        const bottom = y(tops[i] - s.credits)
        const top = y(tops[i])
        // A surface gap above every segment but the top one, when there's room for it.
        const gap = i < last && bottom - top > GAP + 1 ? GAP : 0
        const h = bottom - top - gap
        if (h <= 0) return null
        return (
          <path
            key={s.key}
            d={i === last ? columnPath(x, top, width, h) : `M${x},${bottom}V${top + gap}H${x + width}V${bottom}Z`}
            className={seriesFill(indexOf(s.key))}
            opacity={focus && focus !== s.key ? 0.22 : 1}
          />
        )
      })}
      {b.projected > 0 && actualTop - projectedTop > 1 && (
        <path
          d={columnPath(x + 0.5, projectedTop + 0.5, width - 1, actualTop - projectedTop - (b.credits > 0 ? GAP : 0.5))}
          className="fill-none stroke-chart-axis"
          strokeDasharray="3 2"
        />
      )}
    </g>
  )
}

function Readout({
  bucket: b,
  byKey,
  focus,
  showBilling,
  measure: { label, format, none },
}: {
  bucket: Bucket
  byKey: Map<string, ModelSeries>
  focus: string | null
  showBilling: boolean
  measure: Measure
}) {
  if (!b.known)
    return b.projected > 0 ? (
      <TooltipRow
        mark={<LineKey dashed className="border-chart-projection" />}
        value={`~${format(b.projected)}`}
        label={`${label} projected`}
      />
    ) : (
      <div className="text-fg-muted">No data yet</div>
    )
  // Top of the stack first, as the bar reads.
  const rows = [...b.segments].reverse()
  return (
    <>
      <TooltipRow value={format(b.credits)} label={label} />
      {rows.map((s) => {
        const model = byKey.get(s.key)
        return (
          <div key={s.key} className={focus && focus !== s.key ? 'opacity-50' : undefined}>
            <TooltipRow
              mark={<Swatch className={seriesBg(model?.index ?? 0)} />}
              value={format(s.credits)}
              label={model?.label ?? s.key}
            />
          </div>
        )
      })}
      {b.credits === 0 && <div className="text-fg-muted">{none}</div>}
      {b.projected > 0 && (
        <TooltipRow
          mark={<LineKey dashed className="border-chart-projection" />}
          value={`~${format(b.credits + b.projected)}`}
          label="projected"
        />
      )}
      {showBilling && b.credits > 0 && (
        <TooltipRow value={formatUsd(b.billed_usd)} label={`billed of ${formatUsd(b.gross_usd)} list value`} />
      )}
    </>
  )
}

function describe(b: Bucket, g: Granularity, byKey: Map<string, ModelSeries>, m: Measure): string {
  const when = bucketLabel(b, g)
  if (!b.known) return `${when}: about ${m.format(b.projected)} ${m.label} projected`
  if (b.credits === 0) return `${when}: ${m.none}`
  const parts = b.segments.map((s) => `${byKey.get(s.key)?.label ?? s.key} ${m.format(s.credits)}`)
  return `${when}: ${m.format(b.credits)} ${m.label} — ${parts.join(', ')}`
}

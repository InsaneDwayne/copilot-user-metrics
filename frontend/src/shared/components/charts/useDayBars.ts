import { scaleBand, scaleLinear } from 'd3-scale'
import type { PointerEvent } from 'react'
import type { IsoDay } from '@/shared/utils/dates'
import { formatDay } from '@/shared/utils/format'
import { MARGIN, axisDays } from './chartMath'
import { useChartCursor } from './useChartCursor'
import { fluidChartHeight, useChartWidth } from './useChartSize'

/**
 * The frame of a chart with one bar per day: its size, a band per day, a y scale from 0 to a
 * little above `maxValue`, day ticks, and a cursor driven by pointer and keyboard (it starts on
 * the last day).
 */
export function useDayBars(days: IsoDay[], maxValue: number, maxBar: number) {
  const [boxRef, width] = useChartWidth<HTMLDivElement>()
  const height = fluidChartHeight(width)
  const cursor = useChartCursor(days.length, days.length - 1)

  const innerW = Math.max(0, width - MARGIN.left - MARGIN.right)
  const innerH = height - MARGIN.top - MARGIN.bottom
  const x = scaleBand<string>()
    .domain(days)
    .range([0, innerW])
    .paddingInner(days.length > 62 ? 0.12 : 0.28)
    .paddingOuter(0.1)
  const y = scaleLinear()
    .domain([0, Math.max(1, maxValue) * 1.08])
    .range([innerH, 0])
    .nice(4)
  const barW = Math.min(maxBar, x.bandwidth())
  const band = (i: number) => x(days[i]) ?? 0
  const centre = (i: number) => band(i) + x.bandwidth() / 2

  const onPointerMove = (e: PointerEvent<SVGSVGElement>) => {
    if (!days.length) return
    const px = e.clientX - e.currentTarget.getBoundingClientRect().left - MARGIN.left
    cursor.setActive((px - centre(0)) / x.step())
  }

  const indexOf = new Map(days.map((d, i) => [d, i]))
  const ticks = days.length
    ? axisDays({ start: days[0], end: days[days.length - 1] }, innerW).map((day) => ({
        x: centre(indexOf.get(day) ?? 0),
        label: formatDay(day),
      }))
    : []

  return {
    boxRef,
    width,
    height,
    innerW,
    innerH,
    y,
    barW,
    centre,
    /** Left edge of day `i`'s bar. */
    barLeft: (i: number) => band(i) + (x.bandwidth() - barW) / 2,
    /** Day `i`'s whole slot, gaps included, for the hover highlight. */
    slot: (i: number) => ({ x: band(i) - (x.step() - x.bandwidth()) / 2, width: x.step() }),
    ticks,
    cursor,
    onPointerMove,
  }
}

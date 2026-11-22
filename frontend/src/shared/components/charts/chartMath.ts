import type { DailyCredits, Projection } from '@/shared/api/schemas'
import { daysBetween, eachDay, type IsoDay } from '@/shared/utils/dates'

/** Room around the plot for tick labels; every chart uses the same so they line up. */
export const MARGIN = { top: 12, right: 12, bottom: 26, left: 44 }

export interface ChartPeriod {
  start: IsoDay
  end: IsoDay
}

export interface Cumulative {
  points: [number, number][] // [day index 1..n, running total at the end of that day]
  used: number
  elapsed: number
  total: number
  projectedEnd: number
}

/** Running total per day up to the last known day (missing days count as 0). */
export function cumulative(daily: DailyCredits[], period: ChartPeriod, projection: Projection | null): Cumulative {
  const byDay = new Map(daily.map((d) => [d.day, d.credits]))
  const lastKnown = daily.at(-1)?.day
  let running = 0
  const points: [number, number][] = lastKnown
    ? eachDay(period.start, lastKnown).map((day, i) => {
        running += byDay.get(day) ?? 0
        return [i + 1, running]
      })
    : []
  return {
    points,
    used: running,
    elapsed: points.length,
    total: daysBetween(period.start, period.end) + 1,
    projectedEnd: projection ? projection.projected_credits : running,
  }
}

/** Running total at the end of day `index` (1-based): actual up to `elapsed`, then the projection line. */
export function cumulativeAt(c: Cumulative, index: number): number {
  if (index <= 0) return 0
  if (index <= c.elapsed) return c.points[index - 1][1]
  const remaining = c.total - c.elapsed
  return remaining > 0 ? c.used + ((c.projectedEnd - c.used) * (index - c.elapsed)) / remaining : c.used
}

/** Evenly spaced axis labels: five, or three where a narrow plot has no room for more. */
export function axisDays(period: ChartPeriod, plotWidth = Infinity): IsoDay[] {
  const days = eachDay(period.start, period.end)
  const count = plotWidth < 400 ? 3 : 5
  const picks = Array.from({ length: count }, (_, i) => days[Math.round((i / (count - 1)) * (days.length - 1))])
  return [...new Set(picks)]
}

export function clampIndex(i: number, count: number): number {
  return Math.max(0, Math.min(count - 1, Math.round(i)))
}

/** A bar path: rounded data-end (top), square at the baseline. */
export function columnPath(x: number, y: number, width: number, height: number, radius = 4): string {
  if (width <= 0 || height <= 0) return ''
  const r = Math.min(radius, width / 2, height)
  return (
    `M${x},${y + height}V${y + r}A${r},${r} 0 0 1 ${x + r},${y}` +
    `H${x + width - r}A${r},${r} 0 0 1 ${x + width},${y + r}V${y + height}Z`
  )
}

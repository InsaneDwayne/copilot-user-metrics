import { formatDay, formatLongDay, formatLongMonth, formatMonth } from '@/shared/utils/format'
import type { Bucket, Granularity } from './usageSeries'

/** Axis label: "Nov 3" for days and weeks, "Nov 2026" for months. */
export const tickLabel = (b: Bucket, g: Granularity) => (g === 'month' ? formatMonth(b.start) : formatDay(b.start))

/** Tooltip and table label: "Nov 3, 2026", "Nov 2 – Nov 8, 2026", "November 2026". */
export function bucketLabel(b: Bucket, g: Granularity): string {
  if (g === 'day' || b.start === b.end) return formatLongDay(b.start)
  if (g === 'month' && b.start.endsWith('-01') && b.end.slice(0, 7) === b.start.slice(0, 7)) {
    // A whole month, or the part of it up to the range end.
    return formatLongMonth(b.start)
  }
  return `${formatDay(b.start)} – ${formatLongDay(b.end)}`
}

/** Evenly spaced bar indexes to label, as many as fit at ~72px apart (at least 2). */
export function tickIndexes(count: number, plotWidth: number, spacing = 72): number[] {
  if (count <= 0) return []
  const fit = Math.max(2, Math.min(count, Math.floor(plotWidth / spacing)))
  if (fit >= count) return Array.from({ length: count }, (_, i) => i)
  return [...new Set(Array.from({ length: fit }, (_, i) => Math.round((i / (fit - 1)) * (count - 1))))]
}

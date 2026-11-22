import { useCallback, useMemo } from 'react'
import { useSearchParams } from 'react-router'
import { resolvePeriod, type DayRange, type PeriodPreset, type ResolvedPeriod } from '@/shared/utils/period'

const PRESETS: readonly PeriodPreset[] = ['cycle', 'last', 'custom']

/** The URL params that hold the period; the only ones that carry over between pages. */
const PERIOD_PARAMS = ['period', 'from', 'to'] as const

/**
 * A search string for another page: the current period, plus that page's own `extra` params.
 * Everything else in the URL (a table's filter, order or page, a chart's view) stays behind.
 */
export function periodSearch(params: URLSearchParams, extra: Record<string, string> = {}): string {
  const kept = new URLSearchParams()
  for (const k of PERIOD_PARAMS) for (const v of params.getAll(k)) kept.append(k, v)
  for (const [k, v] of Object.entries(extra)) kept.set(k, v)
  return kept.toString()
}

/** The selected period lives in the URL (?period=&from=&to=) so views are shareable and survive reloads. */
export function usePeriod(): ResolvedPeriod & {
  setPreset: (preset: PeriodPreset) => void
  setCustom: (range: Partial<DayRange>) => void
} {
  const [params, setParams] = useSearchParams()
  const raw = params.get('period')
  const preset: PeriodPreset = PRESETS.includes(raw as PeriodPreset) ? (raw as PeriodPreset) : 'cycle'
  const from = params.get('from') ?? undefined
  const to = params.get('to') ?? undefined
  const resolved = useMemo(() => resolvePeriod(preset, { from, to }), [preset, from, to])

  const setPreset = useCallback(
    (next: PeriodPreset) =>
      setParams((p) => {
        p.set('period', next)
        if (next === 'custom' && !p.get('from')) {
          p.set('from', resolved.range.from)
          p.set('to', resolved.range.to)
        }
        if (next !== 'custom') {
          p.delete('from')
          p.delete('to')
        }
        return p
      }),
    [setParams, resolved.range],
  )

  const setCustom = useCallback(
    (range: Partial<DayRange>) =>
      setParams((p) => {
        p.set('period', 'custom')
        if (range.from) p.set('from', range.from)
        if (range.to) p.set('to', range.to)
        return p
      }),
    [setParams],
  )

  return { ...resolved, setPreset, setCustom }
}

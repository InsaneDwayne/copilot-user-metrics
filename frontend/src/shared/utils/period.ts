import { addDays, cycleOf, daysBetween, todayUtc, type IsoDay } from './dates'
import { formatLongDay } from './format'

export type PeriodPreset = 'cycle' | 'last' | 'custom'

/** A type (not an interface) so it can be passed straight to `apiGet` as query params. */
export type DayRange = {
  from: IsoDay
  to: IsoDay
}

export interface ResolvedPeriod {
  preset: PeriodPreset
  range: DayRange
  isCurrentCycle: boolean
  label: string
}

export function resolvePeriod(
  preset: PeriodPreset,
  custom: Partial<DayRange>,
  today: IsoDay = todayUtc(),
): ResolvedPeriod {
  const current = cycleOf(today)
  if (preset === 'last') {
    const last = cycleOf(addDays(current.start, -1))
    return {
      preset,
      range: { from: last.start, to: last.end },
      isCurrentCycle: false,
      label: `${formatLongDay(last.start)} – ${formatLongDay(last.end)} · closed cycle`,
    }
  }
  if (preset === 'custom' && custom.from && custom.to && custom.from <= custom.to) {
    return {
      preset,
      range: { from: custom.from, to: custom.to },
      isCurrentCycle: false,
      label: `${formatLongDay(custom.from)} – ${formatLongDay(custom.to)} (UTC)`,
    }
  }
  const day = daysBetween(current.start, today) + 1
  const total = daysBetween(current.start, current.end) + 1
  return {
    preset: preset === 'custom' ? 'custom' : 'cycle',
    range: { from: current.start, to: current.end },
    isCurrentCycle: true,
    label: `${formatLongDay(current.start)} – ${formatLongDay(current.end)} · day ${day} of ${total}`,
  }
}

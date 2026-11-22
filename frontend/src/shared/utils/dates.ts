/** ISO calendar days ("2026-11-09") in UTC — the unit GitHub bills and reports in. */
export type IsoDay = string

const DAY_MS = 86_400_000

function toIsoDay(date: Date): IsoDay {
  return date.toISOString().slice(0, 10)
}

export function parseIsoDay(day: IsoDay): Date {
  return new Date(`${day}T00:00:00Z`)
}

export function todayUtc(now: Date = new Date()): IsoDay {
  return toIsoDay(now)
}

export function addDays(day: IsoDay, days: number): IsoDay {
  return toIsoDay(new Date(parseIsoDay(day).getTime() + days * DAY_MS))
}

/** Whole days from `from` to `to` (positive when `to` is later). */
export function daysBetween(from: IsoDay, to: IsoDay): number {
  return Math.round((parseIsoDay(to).getTime() - parseIsoDay(from).getTime()) / DAY_MS)
}

export function eachDay(start: IsoDay, end: IsoDay): IsoDay[] {
  const days: IsoDay[] = []
  for (let day = start; day <= end; day = addDays(day, 1)) days.push(day)
  return days
}

/** The billing cycle (calendar month, UTC) containing `day`. */
export function cycleOf(day: IsoDay): { start: IsoDay; end: IsoDay } {
  const d = parseIsoDay(day)
  const start = new Date(Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), 1))
  const end = new Date(Date.UTC(d.getUTCFullYear(), d.getUTCMonth() + 1, 0))
  return { start: toIsoDay(start), end: toIsoDay(end) }
}

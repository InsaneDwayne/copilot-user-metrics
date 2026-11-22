import { parseIsoDay, type IsoDay } from './dates'

const locale = 'en-US'
const integer = new Intl.NumberFormat(locale, { maximumFractionDigits: 0 })
const compact = new Intl.NumberFormat(locale, { notation: 'compact', maximumFractionDigits: 1 })
const usd = new Intl.NumberFormat(locale, { style: 'currency', currency: 'USD' })
const percent = new Intl.NumberFormat(locale, { style: 'percent', maximumFractionDigits: 0 })
const shortDay = new Intl.DateTimeFormat(locale, { month: 'short', day: 'numeric', timeZone: 'UTC' })
const longDay = new Intl.DateTimeFormat(locale, { month: 'short', day: 'numeric', year: 'numeric', timeZone: 'UTC' })
const month = new Intl.DateTimeFormat(locale, { month: 'short', year: 'numeric', timeZone: 'UTC' })
const longMonth = new Intl.DateTimeFormat(locale, { month: 'long', year: 'numeric', timeZone: 'UTC' })
const relative = new Intl.RelativeTimeFormat(locale, { numeric: 'auto' })

export const formatCredits = (n: number) => integer.format(n)
/** "12K", "1.5M" - for axis ticks that reach 10,000. */
export const formatCompact = (n: number) => compact.format(n)
export const formatUsd = (n: number) => usd.format(n)
export const formatPercent = (ratio: number | null | undefined) => (ratio == null ? '—' : percent.format(ratio))
export const formatDay = (day: IsoDay) => shortDay.format(parseIsoDay(day))
export const formatLongDay = (day: IsoDay) => longDay.format(parseIsoDay(day))
/** "Nov 2026" */
export const formatMonth = (day: IsoDay) => month.format(parseIsoDay(day))
/** "November 2026" */
export const formatLongMonth = (day: IsoDay) => longMonth.format(parseIsoDay(day))
export const formatDate = (iso: string | null | undefined) => (iso ? longDay.format(new Date(iso)) : '—')

/** "18 min ago", "26 hours ago", "yesterday". */
export function formatAgo(iso: string | null | undefined, now: Date = new Date()): string {
  if (!iso) return 'never'
  const minutes = Math.round((new Date(iso).getTime() - now.getTime()) / 60_000)
  if (Math.abs(minutes) < 60) return relative.format(minutes, 'minute')
  const hours = Math.round(minutes / 60)
  if (Math.abs(hours) < 48) return relative.format(hours, 'hour')
  return relative.format(Math.round(hours / 24), 'day')
}

/** "ML" for "Maja Lindqvist", "MA" for "mlindqvist" without a name. */
export function initials(nameOrLogin: string): string {
  const words = nameOrLogin.split(/[\s_-]+/).filter(Boolean)
  const letters = words.length > 1 ? words[0][0] + words[1][0] : nameOrLogin.slice(0, 2)
  return letters.toUpperCase()
}

/** A duration in minutes, in the unit that reads best: "45 min", "3.5 h", "2.1 days". */
export function formatMinutes(minutes: number | null | undefined): string {
  if (minutes == null) return '—'
  if (minutes < 60) return `${Math.round(minutes)} min`
  if (minutes < 48 * 60) return `${(minutes / 60).toFixed(1)} h`
  return `${(minutes / (24 * 60)).toFixed(1)} days`
}

/** `part` of `whole` as 0…1; null when the whole is zero, which `formatPercent` shows as "—". */
export const share = (part: number, whole: number) => (whole > 0 ? part / whole : null)

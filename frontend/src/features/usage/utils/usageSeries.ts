/**
 * Pure arithmetic behind the usage explorer: the day × model line items GitHub reports,
 * folded into colour series, stacked per day, grouped into weeks or months, and projected
 * to the end of a period that contains today.
 */
import type { DailyCredits, Projection } from '@/shared/api/schemas'
import { SERIES_COUNT } from '@/shared/theme/tokens'
import { csvCell } from '@/shared/utils/csv'
import { addDays, cycleOf, daysBetween, eachDay, parseIsoDay, type IsoDay } from '@/shared/utils/dates'
import type { DayRange } from '@/shared/utils/period'
import type { DailyModelUsage, ModelTokens } from '@/features/usage/api/usage'

/** Key of the folded series that holds every model past the named ones. */
export const OTHER = '__other__'

export type Granularity = 'day' | 'week' | 'month'

export interface ModelSeries {
  key: string
  label: string
  /** Colour slot (seriesBg / seriesFill). Follows the model, never its position in a filtered view. */
  index: number
  credits: number
  gross_usd: number
  billed_usd: number
  /** 0..1 of all credits in the period. */
  share: number
}

export interface Amounts {
  credits: number
  gross_usd: number
  included_usd: number
  billed_usd: number
}

export interface StackSegment extends Amounts {
  key: string
}

export interface Bucket extends Amounts {
  /** First day of the bucket (clipped to the range). */
  start: IsoDay
  /** Last day of the bucket (clipped to the range). */
  end: IsoDay
  /** False when every day of the bucket is after today. */
  known: boolean
  /** Credits the projection expects on the bucket's days after today (0 without a projection). */
  projected: number
  /** In series order, bottom of the stack first; empty segments left out. */
  segments: StackSegment[]
}

const zero = (): Amounts => ({ credits: 0, gross_usd: 0, included_usd: 0, billed_usd: 0 })

function add(into: Amounts, from: Amounts) {
  into.credits += from.credits
  into.gross_usd += from.gross_usd
  into.included_usd += from.included_usd
  into.billed_usd += from.billed_usd
}

/**
 * Models by credits in the period, biggest first. Past the colour slots the rest fold
 * into one "Other models" series, so no hue is ever reused for a second model.
 */
export function modelSeries(items: DailyModelUsage[], slots = SERIES_COUNT): ModelSeries[] {
  const totals = new Map<string, Amounts>()
  for (const i of items) {
    const t = totals.get(i.model) ?? zero()
    add(t, i)
    totals.set(i.model, t)
  }
  const ranked = [...totals]
    .filter(([, t]) => t.credits > 0)
    .sort((a, b) => b[1].credits - a[1].credits || a[0].localeCompare(b[0]))
  const all = ranked.reduce((sum, [, t]) => sum + t.credits, 0) || 1
  const entry = (key: string, label: string, index: number, t: Amounts): ModelSeries => ({
    key,
    label,
    index,
    credits: t.credits,
    gross_usd: t.gross_usd,
    billed_usd: t.billed_usd,
    share: t.credits / all,
  })
  if (ranked.length <= slots) return ranked.map(([model, t], i) => entry(model, model, i, t))
  const rest = ranked.slice(slots - 1)
  const other = zero()
  for (const [, t] of rest) add(other, t)
  return [
    ...ranked.slice(0, slots - 1).map(([model, t], i) => entry(model, model, i, t)),
    entry(OTHER, `Other models (${rest.length})`, slots - 1, other),
  ]
}

/** The series a model is drawn in: its own, or "Other". */
function seriesKeyOf(model: string, series: ModelSeries[]): string {
  return series.some((s) => s.key === model) ? model : OTHER
}

/** Only the line items of one series (all of them without a focus). */
export function itemsOf(items: DailyModelUsage[], series: ModelSeries[], focus: string | null): DailyModelUsage[] {
  return focus ? items.filter((i) => seriesKeyOf(i.model, series) === focus) : items
}

/** Monday of the ISO week containing `day`. */
export function weekStart(day: IsoDay): IsoDay {
  const weekday = (parseIsoDay(day).getUTCDay() + 6) % 7 // Monday = 0
  return addDays(day, -weekday)
}

function bucketStart(day: IsoDay, granularity: Granularity, rangeStart: IsoDay): IsoDay {
  const start = granularity === 'week' ? weekStart(day) : granularity === 'month' ? cycleOf(day).start : day
  return start < rangeStart ? rangeStart : start
}

/** Credits per day after today at the pace so far, when the range contains today. */
export function dailyPace(items: DailyModelUsage[], range: DayRange, today: IsoDay): number | null {
  if (today < range.from || today > range.to) return null
  const elapsed = daysBetween(range.from, today) + 1
  return items.reduce((sum, i) => sum + i.credits, 0) / elapsed
}

/**
 * Every day (or week, or month) of the range, each split into the model series.
 * `project: false` leaves out the projection after today (for figures that aren't spend).
 */
export function buckets(
  items: DailyModelUsage[],
  range: DayRange,
  series: ModelSeries[],
  granularity: Granularity,
  today: IsoDay,
  { project = true }: { project?: boolean } = {},
): Bucket[] {
  const order = new Map(series.map((s, i) => [s.key, i]))
  const pace = project ? (dailyPace(items, range, today) ?? 0) : 0
  const byStart = new Map<IsoDay, Bucket & { bySeries: Map<string, StackSegment> }>()
  for (const day of eachDay(range.from, range.to)) {
    const start = bucketStart(day, granularity, range.from)
    let b = byStart.get(start)
    if (!b) {
      b = { start, end: day, known: false, projected: 0, segments: [], bySeries: new Map(), ...zero() }
      byStart.set(start, b)
    }
    b.end = day
    if (day <= today) b.known = true
    else b.projected += pace
  }
  for (const i of items) {
    if (i.credits <= 0 || i.day < range.from || i.day > range.to) continue
    const b = byStart.get(bucketStart(i.day, granularity, range.from))
    if (!b) continue
    const key = seriesKeyOf(i.model, series)
    const seg = b.bySeries.get(key) ?? { key, ...zero() }
    add(seg, i)
    add(b, i)
    b.bySeries.set(key, seg)
  }
  return [...byStart.values()].map(({ bySeries, ...b }) => ({
    ...b,
    segments: [...bySeries.values()].sort((x, y) => (order.get(x.key) ?? 0) - (order.get(y.key) ?? 0)),
  }))
}

/**
 * Daily totals through today and a straight-line projection, for the running-total chart.
 * `project: false` leaves the projection out.
 */
export function runningTotal(
  items: DailyModelUsage[],
  range: DayRange,
  today: IsoDay,
  { project = true }: { project?: boolean } = {},
): { daily: DailyCredits[]; projection: Projection | null } {
  const days = buckets(items, range, [], 'day', today, { project }).filter((b) => b.known)
  const daily = days.map((d) => ({
    day: d.start,
    credits: d.credits,
    gross_usd: d.gross_usd,
    billed_usd: d.billed_usd,
  }))
  const pace = project ? dailyPace(items, range, today) : null
  if (pace === null) return { daily, projection: null }
  const total = daysBetween(range.from, range.to) + 1
  const elapsed = days.length
  const used = daily.reduce((sum, d) => sum + d.credits, 0)
  const gross = daily.reduce((sum, d) => sum + d.gross_usd, 0)
  return {
    daily,
    projection: {
      elapsed_days: elapsed,
      total_days: total,
      daily_average: pace,
      projected_credits: (used * total) / elapsed,
      projected_gross_usd: (gross * total) / elapsed,
    },
  }
}

export interface UsageStats {
  /** Days of the period up to today. */
  elapsedDays: number
  activeDays: number
  averagePerActiveDay: number
  peak: { day: IsoDay; credits: number } | null
}

/** Headline figures from the per-day totals the summary endpoint returns (through today). */
export function usageStats(daily: DailyCredits[]): UsageStats {
  const active = daily.filter((d) => d.credits > 0)
  const total = active.reduce((sum, d) => sum + d.credits, 0)
  const peak = active.reduce<DailyCredits | null>((best, d) => (!best || d.credits > best.credits ? d : best), null)
  return {
    elapsedDays: daily.length,
    activeDays: active.length,
    averagePerActiveDay: active.length ? total / active.length : 0,
    peak: peak && { day: peak.day, credits: peak.credits },
  }
}

/** The aggregation that suits a range when the reader hasn't picked one: at most about 60 day bars or 27 week bars. */
export function defaultGranularity(range: DayRange): Granularity {
  const days = daysBetween(range.from, range.to) + 1
  return days <= 62 ? 'day' : days <= 190 ? 'week' : 'month'
}

/** Months only make sense when the range touches more than one. */
export const spansMonths = (range: DayRange) => cycleOf(range.from).start !== cycleOf(range.to).start

/** The line items as CSV, oldest day first, for spreadsheets. Billing columns for owners only. */
export function toCsv(items: DailyModelUsage[], withBilling: boolean): string {
  const header = [
    'date',
    'model',
    'ai_credits',
    'list_value_usd',
    ...(withBilling ? ['included_usd', 'billed_usd'] : []),
  ]
  const rows = [...items]
    .sort((a, b) => a.day.localeCompare(b.day) || b.credits - a.credits)
    .map((i) =>
      [i.day, i.model, i.credits, i.gross_usd, ...(withBilling ? [i.included_usd, i.billed_usd] : [])]
        .map(csvCell)
        .join(','),
    )
  return [header.join(','), ...rows].join('\n') + '\n'
}

export interface ModelCalls {
  requests: number
  prompt_tokens: number
  output_tokens: number
}

/** The usage-metrics rows as CSV (GitHub's metrics model names), oldest day first. */
export function toCallsCsv(tokens: ModelTokens[]): string {
  const header = ['date', 'model', 'requests', 'prompt_tokens', 'output_tokens']
  const rows = [...tokens]
    .sort((a, b) => a.day.localeCompare(b.day) || a.model.localeCompare(b.model))
    .map((t) => [t.day, t.model, t.requests, t.prompt_tokens, t.output_tokens].map(csvCell).join(','))
  return [header.join(','), ...rows].join('\n') + '\n'
}

export interface ModelRank {
  model: string
  /** The chart series it is drawn in (its own, or "Other"), for its colour and the focus. */
  seriesKey: string
  credits: number
  gross_usd: number
  billed_usd: number
  /** 0..1 of all credits in the period. */
  share: number
  /** Days with credits on this model. */
  days: number
}

/** Every model of the period on its own row, most AI credits first (nothing folded). */
export function modelRanking(items: DailyModelUsage[], series: ModelSeries[]): ModelRank[] {
  const byModel = new Map<string, { amounts: Amounts; days: Set<IsoDay> }>()
  for (const i of items) {
    if (i.credits <= 0) continue
    const entry = byModel.get(i.model) ?? { amounts: zero(), days: new Set<IsoDay>() }
    add(entry.amounts, i)
    entry.days.add(i.day)
    byModel.set(i.model, entry)
  }
  const all = [...byModel.values()].reduce((sum, e) => sum + e.amounts.credits, 0) || 1
  return [...byModel]
    .map(([model, { amounts, days }]) => ({
      model,
      seriesKey: seriesKeyOf(model, series),
      credits: amounts.credits,
      gross_usd: amounts.gross_usd,
      billed_usd: amounts.billed_usd,
      share: amounts.credits / all,
      days: days.size,
    }))
    .sort((a, b) => b.credits - a.credits || a.model.localeCompare(b.model))
}

/**
 * Billing ("Claude Sonnet 4.6") and metrics ("claude-sonnet-4.6") name the same model
 * differently; compare them without case, spaces or dashes.
 */
const modelKey = (name: string) => name.toLowerCase().replace(/[^a-z0-9.]/g, '')

/** Maps a metrics model name to its billing name where one matches, else keeps it. */
function billingNameOf(billingNames: string[]): (metricsName: string) => string {
  const byKey = new Map(billingNames.map((n) => [modelKey(n), n]))
  return (metricsName) => byKey.get(modelKey(metricsName)) ?? metricsName
}

export const totalTokens = (c: ModelCalls) => c.prompt_tokens + c.output_tokens

export type CallsMetric = 'tokens' | 'requests'

/**
 * The metrics rows as chart line items: the chosen figure in `credits` (the field the
 * chart stacks), under the billing name where one matches so labels agree with the credits chart.
 */
export function callsItems(tokens: ModelTokens[], metric: CallsMetric, billingNames: string[]): DailyModelUsage[] {
  const nameOf = billingNameOf(billingNames)
  return tokens.map((t) => ({
    day: t.day,
    model: nameOf(t.model),
    credits: metric === 'tokens' ? totalTokens(t) : t.requests,
    gross_usd: 0,
    included_usd: 0,
    billed_usd: 0,
  }))
}

export interface CallsRank extends ModelCalls {
  model: string
  /** The chart series it is drawn in (its own, or "Other"). */
  seriesKey: string
  /** 0..1 of the chosen figure in the period. */
  share: number
  /** Days with model calls. */
  days: number
}

/** Every model of the metrics on its own row, most of the chosen figure first (nothing folded). */
export function callsRanking(
  tokens: ModelTokens[],
  metric: CallsMetric,
  billingNames: string[],
  series: ModelSeries[],
): CallsRank[] {
  const nameOf = billingNameOf(billingNames)
  const byModel = new Map<string, { calls: ModelCalls; days: Set<IsoDay> }>()
  for (const t of tokens) {
    const model = nameOf(t.model)
    const entry = byModel.get(model) ?? {
      calls: { requests: 0, prompt_tokens: 0, output_tokens: 0 },
      days: new Set<IsoDay>(),
    }
    entry.calls.requests += t.requests
    entry.calls.prompt_tokens += t.prompt_tokens
    entry.calls.output_tokens += t.output_tokens
    entry.days.add(t.day)
    byModel.set(model, entry)
  }
  const value = (c: ModelCalls) => (metric === 'tokens' ? totalTokens(c) : c.requests)
  const rows = [...byModel].filter(([, e]) => value(e.calls) > 0)
  const all = rows.reduce((sum, [, e]) => sum + value(e.calls), 0) || 1
  return rows
    .map(([model, { calls, days }]) => ({
      model,
      seriesKey: seriesKeyOf(model, series),
      ...calls,
      share: value(calls) / all,
      days: days.size,
    }))
    .sort((a, b) => value(b) - value(a) || a.model.localeCompare(b.model))
}

/**
 * Series for a second chart of the same models: a model already in `palette` keeps its
 * colour; the others take the slots the palette leaves free, and past those fold into
 * "Other models" (last slot), so no colour ever stands for two models across both charts.
 */
export function alignedSeries(items: DailyModelUsage[], palette: ModelSeries[], slots = SERIES_COUNT): ModelSeries[] {
  const totals = new Map<string, number>()
  for (const i of items) totals.set(i.model, (totals.get(i.model) ?? 0) + i.credits)
  const ranked = [...totals].filter(([, v]) => v > 0).sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))
  const all = ranked.reduce((sum, [, v]) => sum + v, 0) || 1
  const last = slots - 1
  const pinned = new Map(palette.filter((s) => s.key !== OTHER).map((s) => [s.key, s.index]))
  const taken = new Set(palette.map((s) => s.index))
  let free = [...Array(slots).keys()].filter((i) => !taken.has(i))
  if (ranked.filter(([model]) => !pinned.has(model)).length > free.length) {
    // Some models fold into "Other", which takes the last slot: free it, and if a model
    // holds it in the palette (a full palette without "Other"), that model folds in too.
    free = free.filter((i) => i !== last)
    for (const [key, index] of pinned) if (index === last) pinned.delete(key)
  }
  const entry = (key: string, label: string, index: number, value: number): ModelSeries => ({
    key,
    label,
    index,
    credits: value,
    gross_usd: 0,
    billed_usd: 0,
    share: value / all,
  })
  const own: ModelSeries[] = []
  let other = 0
  let folded = 0
  for (const [model, value] of ranked) {
    const index = pinned.get(model) ?? free.shift()
    if (index === undefined) {
      other += value
      folded += 1
    } else own.push(entry(model, model, index, value))
  }
  return folded ? [...own, entry(OTHER, `Other models (${folded})`, last, other)] : own
}

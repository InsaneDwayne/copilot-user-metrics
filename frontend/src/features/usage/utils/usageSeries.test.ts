import { describe, expect, it } from 'vitest'
import {
  OTHER,
  buckets,
  dailyPace,
  defaultGranularity,
  itemsOf,
  modelRanking,
  modelSeries,
  runningTotal,
  spansMonths,
  toCsv,
  usageStats,
  weekStart,
  alignedSeries,
  buckets as bucketsOf,
  callsItems,
  callsRanking,
  toCallsCsv,
} from './usageSeries'

const item = (day: string, model: string, credits: number, billed = 0) => ({
  day,
  model,
  credits,
  gross_usd: credits / 100,
  included_usd: credits / 100 - billed,
  billed_usd: billed,
})

const items = [
  item('2026-11-02', 'GPT-5.5', 300),
  item('2026-11-02', 'Claude Sonnet 4.6', 100),
  item('2026-11-03', 'Claude Sonnet 4.6', 250, 0.5),
  item('2026-11-09', 'Gemini 3', 20),
  item('2026-11-04', 'Unused', 0),
]
const nov = { from: '2026-11-01', to: '2026-11-30' }

describe('model series', () => {
  it('ranks models by credits with their share and keeps colour slots in that order', () => {
    expect(modelSeries(items).map((s) => [s.key, s.index, s.credits])).toEqual([
      ['Claude Sonnet 4.6', 0, 350],
      ['GPT-5.5', 1, 300],
      ['Gemini 3', 2, 20],
    ])
    expect(modelSeries(items)[0].share).toBeCloseTo(350 / 670)
  })

  it('folds models past the colour slots into one "Other" series', () => {
    const series = modelSeries(items, 2)
    expect(series.map((s) => [s.key, s.index, s.credits])).toEqual([
      ['Claude Sonnet 4.6', 0, 350],
      [OTHER, 1, 320],
    ])
    expect(series[1].label).toBe('Other models (2)')
    expect(itemsOf(items, series, OTHER).map((i) => i.model)).toEqual(['GPT-5.5', 'Gemini 3', 'Unused'])
  })
})

describe('model ranking', () => {
  it('ranks every model with its share and days used, keeping its chart series', () => {
    const ranking = modelRanking(items, modelSeries(items, 2))
    expect(ranking.map((r) => [r.model, r.credits, r.days, r.seriesKey])).toEqual([
      ['Claude Sonnet 4.6', 350, 2, 'Claude Sonnet 4.6'],
      ['GPT-5.5', 300, 1, OTHER],
      ['Gemini 3', 20, 1, OTHER],
    ])
    expect(ranking[1].share).toBeCloseTo(300 / 670)
  })
})

describe('buckets', () => {
  const series = modelSeries(items)

  it('stacks every day, biggest model at the bottom, and projects the days after today', () => {
    const days = buckets(items, nov, series, 'day', '2026-11-10')
    expect(days).toHaveLength(30)
    expect(days[1].segments.map((s) => [s.key, s.credits])).toEqual([
      ['Claude Sonnet 4.6', 100],
      ['GPT-5.5', 300],
    ])
    expect(days[2]).toMatchObject({ start: '2026-11-03', known: true, credits: 250, billed_usd: 0.5, projected: 0 })
    expect(days[10]).toMatchObject({ known: false, credits: 0, projected: 67 })
  })

  it('groups Monday-to-Sunday weeks, clipped to the range', () => {
    expect(weekStart('2026-11-01')).toBe('2026-10-26')
    const weeks = buckets(items, nov, series, 'week', '2026-11-10')
    expect(weeks.map((w) => [w.start, w.end, w.credits])).toEqual([
      ['2026-11-01', '2026-11-01', 0],
      ['2026-11-02', '2026-11-08', 650],
      ['2026-11-09', '2026-11-15', 20],
      ['2026-11-16', '2026-11-22', 0],
      ['2026-11-23', '2026-11-29', 0],
      ['2026-11-30', '2026-11-30', 0],
    ])
    // Five days of the third week are still ahead.
    expect(weeks[2].projected).toBeCloseTo(5 * 67)
  })

  it('groups calendar months', () => {
    const range = { from: '2026-10-15', to: '2026-11-30' }
    const months = buckets(items, range, series, 'month', '2026-12-01')
    expect(months.map((m) => [m.start, m.end, m.credits])).toEqual([
      ['2026-10-15', '2026-10-31', 0],
      ['2026-11-01', '2026-11-30', 670],
    ])
  })
})

describe('running total', () => {
  it('projects only a range that contains today', () => {
    expect(dailyPace(items, nov, '2026-12-01')).toBeNull()
    const { daily, projection } = runningTotal(items, nov, '2026-11-10')
    expect(daily).toHaveLength(10)
    expect(projection).toMatchObject({ elapsed_days: 10, total_days: 30, daily_average: 67, projected_credits: 2010 })
  })
})

describe('helpers', () => {
  it('summarises active days, the peak and the average', () => {
    const daily = runningTotal(items, nov, '2026-11-10').daily
    expect(usageStats(daily)).toEqual({
      elapsedDays: 10,
      activeDays: 3,
      averagePerActiveDay: 670 / 3,
      peak: { day: '2026-11-02', credits: 400 },
    })
  })

  it('picks an aggregation that keeps the bar count readable', () => {
    expect(defaultGranularity(nov)).toBe('day')
    expect(defaultGranularity({ from: '2026-06-01', to: '2026-11-30' })).toBe('week')
    expect(defaultGranularity({ from: '2026-01-01', to: '2026-11-30' })).toBe('month')
    expect(spansMonths(nov)).toBe(false)
    expect(spansMonths({ from: '2026-10-15', to: '2026-11-14' })).toBe(true)
  })

  it('writes CSV oldest day first, quotes awkward names and adds billing for owners', () => {
    const rows = [item('2026-11-02', 'a, "b"', 1), item('2026-11-01', 'c', 2)]
    expect(toCsv(rows, false).split('\n')).toEqual([
      'date,model,ai_credits,list_value_usd',
      '2026-11-01,c,2,0.02',
      '2026-11-02,"a, ""b""",1,0.01',
      '',
    ])
    expect(toCsv(rows, true).split('\n')[0]).toBe('date,model,ai_credits,list_value_usd,included_usd,billed_usd')
  })
})

describe('callsItems and alignedSeries', () => {
  const t = (day: string, model: string, requests: number, prompt: number, output = 0) => ({
    day,
    model,
    requests,
    prompt_tokens: prompt,
    output_tokens: output,
  })
  const palette = modelSeries(items, 3) // Claude Sonnet 4.6 → 0, GPT-5.5 → 1, Other (Gemini 3) → 2

  it('uses billing names where they match and the chosen figure as the stacked value', () => {
    const rows = callsItems([t('2026-11-03', 'gpt-5.5', 2, 100, 50), t('2026-11-03', 'gpt-5-mini', 9, 10)], 'tokens', [
      'GPT-5.5',
    ])
    expect(rows.map((r) => [r.model, r.credits])).toEqual([
      ['GPT-5.5', 150],
      ['gpt-5-mini', 10],
    ])
    expect(callsItems([t('2026-11-03', 'gpt-5.5', 2, 100)], 'requests', [])[0].credits).toBe(2)
  })

  it('keeps palette colours and gives new models the free slots', () => {
    const rows = callsItems([t('2026-11-03', 'gpt-5-mini', 1, 900), t('2026-11-03', 'GPT-5.5', 1, 100)], 'tokens', [])
    const series = alignedSeries(rows, palette.slice(0, 2), 3)
    expect(series.map((s) => [s.key, s.index])).toEqual([
      ['gpt-5-mini', 2],
      ['GPT-5.5', 1],
    ])
  })

  it('folds what does not fit into Other on the last slot, never reusing a colour', () => {
    const rows = callsItems(
      [
        t('2026-11-03', 'a', 1, 500),
        t('2026-11-03', 'b', 1, 400),
        t('2026-11-03', 'Claude Sonnet 4.6', 1, 300),
        t('2026-11-03', 'GPT-5.5', 1, 200),
      ],
      'tokens',
      [],
    )
    // Full palette without Other: Gemini 3 holds slot 2, so Other takes it and a and b fold in.
    const full = modelSeries(items.slice(0, 4), 3).filter((s) => s.key !== OTHER)
    const fullPalette = [...full, { ...full[0], key: 'Gemini 3', label: 'Gemini 3', index: 2 }]
    const series = alignedSeries(rows, fullPalette, 3)
    expect(series.map((s) => [s.key, s.index, s.credits])).toEqual([
      ['Claude Sonnet 4.6', 0, 300],
      ['GPT-5.5', 1, 200],
      [OTHER, 2, 900],
    ])
    expect(new Set(series.map((s) => s.index)).size).toBe(series.length)
  })

  it('can leave the projection out', () => {
    const rows = callsItems([t('2026-11-03', 'x', 1, 100)], 'tokens', [])
    const series = alignedSeries(rows, [])
    const b = bucketsOf(rows, nov, series, 'day', '2026-11-10', { project: false })
    expect(b.every((x) => x.projected === 0)).toBe(true)
    expect(b.find((x) => x.start === '2026-11-03')?.credits).toBe(100)
  })
})

describe('callsRanking', () => {
  const t = (day: string, model: string, requests: number, prompt: number, output = 0) => ({
    day,
    model,
    requests,
    prompt_tokens: prompt,
    output_tokens: output,
  })
  const tokens = [
    t('2026-11-03', 'claude-sonnet-4.6', 2, 800, 200),
    t('2026-11-04', 'claude-sonnet-4.6', 1, 500),
    t('2026-11-03', 'gpt-5-mini', 30, 400),
    t('2026-11-03', 'idle', 0, 0),
  ]
  const names = ['Claude Sonnet 4.6']
  const series = alignedSeries(callsItems(tokens, 'tokens', names), [], 1) // one slot: gpt-5-mini folds into Other

  it('ranks every model by the chosen figure under its billing name, nothing folded', () => {
    expect(callsRanking(tokens, 'tokens', names, series).map((r) => [r.model, r.seriesKey, r.days])).toEqual([
      ['Claude Sonnet 4.6', OTHER, 2],
      ['gpt-5-mini', OTHER, 1],
    ])
    const byRequests = callsRanking(tokens, 'requests', names, series)
    expect(byRequests.map((r) => [r.model, r.requests])).toEqual([
      ['gpt-5-mini', 30],
      ['Claude Sonnet 4.6', 3],
    ])
    expect(byRequests[0].share).toBeCloseTo(30 / 33)
  })
})

describe('model calls in the explorer', () => {
  const calls = [
    { day: '2026-11-04', model: 'gpt-5-mini', requests: 3, prompt_tokens: 900, output_tokens: 100 },
    { day: '2026-11-03', model: 'claude-sonnet-4.6', requests: 1, prompt_tokens: 50, output_tokens: 5 },
  ]

  it('exports the metrics rows as CSV, oldest day first', () => {
    expect(toCallsCsv(calls)).toBe(
      'date,model,requests,prompt_tokens,output_tokens\n' +
        '2026-11-03,claude-sonnet-4.6,1,50,5\n' +
        '2026-11-04,gpt-5-mini,3,900,100\n',
    )
  })

  it('runs a total without a projection when asked', () => {
    const rows = callsItems(calls, 'tokens', [])
    const { daily, projection } = runningTotal(rows, nov, '2026-11-10', { project: false })
    expect(projection).toBeNull()
    expect(daily.reduce((sum, d) => sum + d.credits, 0)).toBe(1055)
  })
})

import { describe, expect, it } from 'vitest'
import { axisDays, clampIndex, columnPath, cumulative, cumulativeAt } from './chartMath'

const period = { start: '2026-11-01', end: '2026-11-30' }
const daily = [
  { day: '2026-11-01', credits: 100, gross_usd: 1, billed_usd: 0 },
  { day: '2026-11-02', credits: 100, gross_usd: 1, billed_usd: 0.25 },
]
const projection = {
  elapsed_days: 2,
  total_days: 30,
  daily_average: 100,
  projected_credits: 3000,
  projected_gross_usd: 30,
}

describe('chart math', () => {
  it('accumulates usage and keeps the projected end', () => {
    const c = cumulative(daily, period, projection)
    expect(c.points).toEqual([
      [1, 100],
      [2, 200],
    ])
    expect(c.projectedEnd).toBe(3000)
  })

  it('counts days missing from the data as zero', () => {
    const sparse = [daily[0], { day: '2026-11-03', credits: 50, gross_usd: 0.5, billed_usd: 0 }]
    expect(cumulative(sparse, period, null).points).toEqual([
      [1, 100],
      [2, 100],
      [3, 150],
    ])
  })

  it('reads the running total, then follows the projection line', () => {
    const c = cumulative(daily, period, projection)
    expect(cumulativeAt(c, 0)).toBe(0)
    expect(cumulativeAt(c, 2)).toBe(200)
    expect(cumulativeAt(c, 30)).toBe(3000)
    expect(cumulativeAt(c, 16)).toBe(1600)
  })

  it('spreads fewer axis labels over a narrow plot', () => {
    expect(axisDays(period)).toEqual(['2026-11-01', '2026-11-08', '2026-11-16', '2026-11-23', '2026-11-30'])
    expect(axisDays(period, 300)).toEqual(['2026-11-01', '2026-11-16', '2026-11-30'])
  })

  it('clamps cursor positions to the data', () => {
    expect(clampIndex(-3, 10)).toBe(0)
    expect(clampIndex(4.4, 10)).toBe(4)
    expect(clampIndex(42, 10)).toBe(9)
  })

  it('draws columns rounded at the top only, and nothing for empty ones', () => {
    expect(columnPath(0, 0, 10, 0)).toBe('')
    expect(columnPath(0, 10, 10, 20)).toBe('M0,30V14A4,4 0 0 1 4,10H6A4,4 0 0 1 10,14V30Z')
  })
})

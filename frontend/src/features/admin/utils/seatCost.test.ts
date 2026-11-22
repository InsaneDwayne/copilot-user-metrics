import { describe, expect, it } from 'vitest'
import { includedUsage, seatCostView, totalCostView } from './seatCost'

const cost = (month: string, userMonths: number) => ({
  month,
  seats: userMonths,
  price_per_seat_usd: 19,
  gross_usd: userMonths * 19,
  net_usd: userMonths * 19,
})

describe('seatCostView', () => {
  it('shows the current month as every assigned seat at the seat price, not the billed-so-far part', () => {
    const v = seatCostView(cost('2026-11-01', 37.27), 86, '2026-11-13')
    expect(v.value).toBe('$1,634.00')
    expect(v.meta).toBe('86 seats × $19.00 this month')
  })

  it('shows a closed month as what GitHub billed', () => {
    const v = seatCostView(cost('2026-10-01', 84.5), 86, '2026-11-13')
    expect(v.value).toBe('$1,605.50')
    expect(v.meta).toBe('Billed by GitHub · $19.00 per seat')
  })
})

const totals = { credits: 0, gross_usd: 1300, included_usd: 1000, billed_usd: 300 }

describe('totalCostView', () => {
  it('adds the billed AI credits to the seat commitment', () => {
    const v = totalCostView(cost('2026-11-01', 37.27), 86, totals, '2026-11-13')
    expect(v.value).toBe('$1,934.00')
    expect(v.meta).toBe('$1,634.00 seats + $300.00 billed credits')
  })
})

describe('includedUsage', () => {
  it('measures included credits against a pool worth the seat cost while nothing is billed', () => {
    const u = includedUsage(cost('2026-11-01', 37.27), 86, { ...totals, billed_usd: 0 }, '2026-11-13')
    expect(u.pool).toBe(1634)
    expect(u.used).toBe(1000)
    expect(u.exhausted).toBe(false)
    expect(u.ratio).toBeCloseTo(1000 / 1634)
  })

  it('shows the pool as used up once GitHub bills beyond it, even if the estimate is larger', () => {
    const u = includedUsage(cost('2026-11-01', 37.27), 86, { ...totals, included_usd: 1620 }, '2026-11-13')
    expect(u.exhausted).toBe(true)
    expect(u.pool).toBe(1620)
    expect(u.ratio).toBe(1)
  })

  it('reports no usage when there is no seat cost', () => {
    expect(includedUsage(cost('2026-10-01', 0), 0, { ...totals, billed_usd: 0 }, '2026-11-13').ratio).toBe(0)
  })
})

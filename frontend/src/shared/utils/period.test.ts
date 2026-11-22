import { describe, expect, it } from 'vitest'
import { resolvePeriod } from './period'

describe('resolvePeriod', () => {
  const today = '2026-11-09'

  it('defaults to the current billing cycle', () => {
    const p = resolvePeriod('cycle', {}, today)
    expect(p.range).toEqual({ from: '2026-11-01', to: '2026-11-30' })
    expect(p.isCurrentCycle).toBe(true)
    expect(p.label).toContain('day 9 of 30')
  })

  it('resolves last cycle across a year boundary', () => {
    expect(resolvePeriod('last', {}, '2027-01-15').range).toEqual({ from: '2026-12-01', to: '2026-12-31' })
  })

  it('uses a valid custom range', () => {
    const p = resolvePeriod('custom', { from: '2026-10-03', to: '2026-11-02' }, today)
    expect(p.range).toEqual({ from: '2026-10-03', to: '2026-11-02' })
    expect(p.isCurrentCycle).toBe(false)
  })
})

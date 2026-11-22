import { describe, expect, it } from 'vitest'
import { periodSearch } from './usePeriod'

describe('periodSearch', () => {
  it('keeps only the period, so one page’s filters do not follow you to another', () => {
    const params = new URLSearchParams('period=custom&from=2026-10-01&to=2026-10-31&team=web&sort=budget&page=3')
    expect(periodSearch(params)).toBe('period=custom&from=2026-10-01&to=2026-10-31')
  })

  it('adds the target page’s own params', () => {
    expect(periodSearch(new URLSearchParams('period=last&team=web'), { team: 'ops' })).toBe('period=last&team=ops')
  })
})

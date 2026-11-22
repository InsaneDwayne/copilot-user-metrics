import { describe, expect, it } from 'vitest'
import { idleDaysParam, parseIdleDays } from './seats'

describe('idle threshold param', () => {
  it('accepts only the offered thresholds', () => {
    expect(parseIdleDays('30')).toBe(30)
    expect(parseIdleDays('31')).toBe(7)
    expect(parseIdleDays(null)).toBe(7)
  })

  it('leaves the default out of the URL', () => {
    expect(idleDaysParam(7)).toBeNull()
    expect(idleDaysParam(60)).toBe('60')
  })
})

import { describe, expect, it } from 'vitest'
import { formatMinutes } from './format'

describe('formatMinutes', () => {
  it('picks minutes, hours or days', () => {
    expect(formatMinutes(44.6)).toBe('45 min')
    expect(formatMinutes(210)).toBe('3.5 h')
    expect(formatMinutes(3 * 24 * 60)).toBe('3.0 days')
    expect(formatMinutes(null)).toBe('—')
  })
})

import { describe, expect, it } from 'vitest'
import { compareToAverage } from './compare'

describe('compareToAverage', () => {
  const me = { kind: 'me' } as const
  it('puts usage in words relative to the org average', () => {
    expect(compareToAverage(0, 100, me)).toBe('You: none used yet')
    expect(compareToAverage(30, 100, me)).toBe('You: under half the average')
    expect(compareToAverage(80, 100, me)).toBe('You: 80% of the average')
    expect(compareToAverage(102, 100, me)).toBe('You: about average')
    expect(compareToAverage(250, 100, { kind: 'member', login: 'bob' })).toBe('@bob: 2.5× the average')
    expect(compareToAverage(10, 0, me)).toBe('No org usage yet')
  })
})

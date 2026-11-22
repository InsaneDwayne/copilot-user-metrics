import { describe, expect, it } from 'vitest'
import { heatTint } from './heatTint'

describe('heatTint', () => {
  it('leaves zero untinted and gets stronger towards the maximum', () => {
    expect(heatTint(0, 10)).toBeUndefined()
    expect(heatTint(1, 10)).toBe('bg-heat-1')
    expect(heatTint(5, 10)).toBe('bg-heat-2')
    expect(heatTint(10, 10)).toBe('bg-heat-3')
  })
})

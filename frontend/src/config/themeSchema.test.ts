import { describe, expect, it } from 'vitest'
import { themeConfigSchema } from './themeSchema'

describe('themeConfigSchema', () => {
  it('fills both modes from an empty file', () => {
    const theme = themeConfigSchema.parse({})
    expect(theme.defaultMode).toBe('system')
    expect(theme.colors.dark).toEqual({ bg: '#161826', text: '#e9e9ed', tokens: {} })
    expect(theme.colors.light).toEqual({ bg: '#f4f5fa', text: '#1b1d2a', tokens: {} })
  })

  it('keeps the defaults for whatever a mode leaves out', () => {
    const theme = themeConfigSchema.parse({ colors: { light: { bg: '#ffffff' } } })
    expect(theme.colors.light).toEqual({ bg: '#ffffff', text: '#1b1d2a', tokens: {} })
  })

  it('accepts role overrides as colours or palette names, and nothing else', () => {
    const theme = themeConfigSchema.parse({
      colors: { tokens: { 'series-1': '#ff6600' }, light: { tokens: { 'fg-muted': 'neutral-300' } } },
    })
    expect(theme.colors.tokens).toEqual({ 'series-1': '#ff6600' })
    expect(theme.colors.light.tokens).toEqual({ 'fg-muted': 'neutral-300' })
    expect(themeConfigSchema.safeParse({ colors: { tokens: { 'not-a-role': '#ff6600' } } }).success).toBe(false)
    expect(themeConfigSchema.safeParse({ colors: { tokens: { line: 'red' } } }).success).toBe(false)
  })

  it('rejects an unknown mode', () => {
    expect(themeConfigSchema.safeParse({ defaultMode: 'sepia' }).success).toBe(false)
  })
})

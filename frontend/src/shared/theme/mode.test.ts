import { describe, expect, it } from 'vitest'
import { themeConfigSchema } from '@/config/themeSchema'
import { modeAccent, themeStylesheet, themeVariables } from './applyTheme'
import { nextPreference, resolveMode } from './mode'

describe('mode', () => {
  it('follows the OS only for the system preference', () => {
    expect(resolveMode('system', true)).toBe('dark')
    expect(resolveMode('system', false)).toBe('light')
    expect(resolveMode('light', true)).toBe('light')
    expect(resolveMode('dark', false)).toBe('dark')
  })

  it('cycles system → light → dark → system', () => {
    expect(nextPreference('system')).toBe('light')
    expect(nextPreference('light')).toBe('dark')
    expect(nextPreference('dark')).toBe('system')
  })
})

describe('themeVariables', () => {
  const theme = themeConfigSchema.parse({})

  it('uses each mode’s ground', () => {
    expect(themeVariables(theme, 'dark')['--color-canvas']).toBe('#161826')
    expect(themeVariables(theme, 'light')['--color-canvas']).toBe('#f4f5fa')
  })

  it('keeps the shared accent where it is readable and adjusts it where it is not', () => {
    expect(modeAccent(theme, 'dark')).toBe('#9184d9')
    expect(modeAccent(theme, 'light')).not.toBe('#9184d9')
  })

  it('uses an explicit per-mode accent exactly as given', () => {
    const custom = themeConfigSchema.parse({ colors: { light: { accent: '#b0a8ff' } } })
    expect(modeAccent(custom, 'light')).toBe('#b0a8ff')
  })

  it('applies shared role overrides, with per-mode ones winning', () => {
    const custom = themeConfigSchema.parse({
      colors: { tokens: { 'series-1': '#ff6600', line: 'neutral-700' }, dark: { tokens: { 'series-1': '#00aa55' } } },
    })
    expect(themeVariables(custom, 'light')['--color-series-1']).toBe('#ff6600')
    expect(themeVariables(custom, 'dark')['--color-series-1']).toBe('#00aa55')
    expect(themeVariables(custom, 'dark')['--color-line']).toBe('var(--color-neutral-700)')
  })

  it('writes one rule per mode, at :root specificity', () => {
    const css = themeStylesheet(theme)
    expect(css).toContain(":root:where([data-theme='dark']) {")
    expect(css).toContain(":root:where([data-theme='light']) {")
  })
})

import { describe, expect, it } from 'vitest'
import css from '@/shared/styles/index.css?raw'
import { ROLE_TOKENS, seriesBg, seriesFill, tokenValue } from './tokens'

// Every component and page: all sources outside the theme machinery (and its schema).
const sources = import.meta.glob<string>(
  ['../../**/*.{ts,tsx}', '!../../**/*.test.*', '!../../shared/theme/**', '!../../config/**'],
  { query: '?raw', import: 'default', eager: true },
)

describe('tokens', () => {
  it('lists exactly the role tokens the stylesheet defines', () => {
    const inCss = [...css.matchAll(/--color-([a-z0-9-]+):\s*var\(--color-(?:neutral|accent)\b/g)].map((m) => m[1])
    expect(new Set(inCss)).toEqual(new Set(ROLE_TOKENS))
  })

  // Themes restyle roles. A component that names a ramp step, or reaches past the
  // tokens with an arbitrary colour, can't be restyled from the theme.
  it('keeps components on role tokens', () => {
    expect(Object.keys(sources).length).toBeGreaterThan(50)
    const offenders = Object.entries(sources).flatMap(([file, source]) =>
      source
        .split('\n')
        .map((line, i) => ({ line, where: `${file.replace('../../', '')}:${i + 1}` }))
        .filter(({ line }) => /\b(?:neutral|accent)-[1-9]00\b|var\(--color-|#[0-9a-fA-F]{6}\b/.test(line))
        .map(({ where }) => where),
    )
    expect(offenders).toEqual([])
  })

  it('resolves palette names to variables and passes colours through', () => {
    expect(tokenValue('accent-300')).toBe('var(--color-accent-300)')
    expect(tokenValue('#ff6600')).toBe('#ff6600')
  })

  it('folds series past the last slot into it instead of reusing a hue', () => {
    expect(seriesBg(0)).toBe('bg-series-1')
    expect(seriesBg(7)).toBe('bg-series-8')
    expect(seriesBg(8)).toBe('bg-series-8')
    expect(seriesFill(12)).toBe('fill-series-8')
  })
})

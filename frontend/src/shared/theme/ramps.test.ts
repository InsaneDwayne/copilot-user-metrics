import { differenceEuclidean, wcagContrast } from 'culori'
import { describe, expect, it } from 'vitest'
import { accentRamp, deriveSurface, ensureContrast, neutralRamp } from './ramps'
import { STEPS } from './tokens'

const distance = differenceEuclidean('oklab')

// Hand-tuned ramps from the Nocturne stylesheet in the mockups.
const NOCTURNE_ACCENT = [
  '#f5f4ff',
  '#e7e5fe',
  '#d2cefd',
  '#b5abfc',
  '#968ae0',
  '#796cbf',
  '#5d5294',
  '#423a6a',
  '#2b2741',
]
const NOCTURNE_NEUTRAL = [
  '#f3f5fe',
  '#e4e7f5',
  '#cfd3e5',
  '#b2b6ca',
  '#9397ab',
  '#75798c',
  '#595d6c',
  '#3f424d',
  '#292b31',
]

describe('ramps', () => {
  it.each([
    ['accent', accentRamp('#9184d9'), NOCTURNE_ACCENT],
    ['neutral', neutralRamp('#161826'), NOCTURNE_NEUTRAL],
  ])('reproduces the default %s ramp from its base colour', (_, ramp, expected) => {
    STEPS.forEach((step, i) => expect(distance(ramp[step], expected[i])).toBeLessThan(0.01))
  })

  it('keeps every step a valid sRGB hex for a highly saturated corporate colour', () => {
    for (const mode of ['dark', 'light'] as const) {
      for (const hex of Object.values(accentRamp('#ff0000', mode))) expect(hex).toMatch(/^#[0-9a-f]{6}$/)
    }
  })

  it('mirrors the ramps in light mode, so each step keeps its contrast with the ground', () => {
    const dark = neutralRamp('#161826', 'dark')
    const light = neutralRamp('#f4f5fa', 'light')
    // Muted text (400), secondary text (500) and hairlines (800) are the roles components rely on.
    for (const step of [400, 500, 800] as const) {
      const darkRatio = wcagContrast(dark[step], '#161826')
      const lightRatio = wcagContrast(light[step], '#f4f5fa')
      expect(Math.abs(darkRatio - lightRatio) / darkRatio).toBeLessThan(0.1)
    }
    expect(light[100] < light[900]).toBe(true) // 100 is the darkest step on a light ground
  })
})

describe('deriveSurface', () => {
  it('lifts cards off a dark ground and towards white on a light one', () => {
    expect(wcagContrast(deriveSurface('#161826'), '#000')).toBeGreaterThan(wcagContrast('#161826', '#000'))
    expect(deriveSurface('#f4f5fa')).toBe('#ffffff')
  })

  it('shades cards on a ground that is already white', () => {
    expect(deriveSurface('#ffffff')).not.toBe('#ffffff')
  })
})

describe('ensureContrast', () => {
  it('leaves a colour that is already readable alone', () => {
    expect(ensureContrast('#9184d9', '#161826')).toBe('#9184d9')
  })

  it.each([
    ['light ground', '#9184d9', '#f4f5fa'],
    ['dark ground', '#3a2f80', '#161826'],
  ])('moves a colour until it reaches 4.5:1 on a %s', (_, fg, bg) => {
    const fixed = ensureContrast(fg, bg)
    expect(wcagContrast(fixed, bg)).toBeGreaterThanOrEqual(4.5)
    expect(wcagContrast(fixed, bg)).toBeLessThan(5.2) // just enough, not black or white
  })
})

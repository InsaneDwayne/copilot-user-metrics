/**
 * Expands the base colours into the design system's 100–900 tonal ramps.
 *
 * Generated in OKLCH on one shared lightness scale (measured from the Nocturne
 * ramps), so the same step of any ramp carries the same visual weight whatever
 * the corporate colours are. Chroma peaks at the base steps and tapers towards
 * the ends, then is clamped into the sRGB gamut.
 *
 * Steps are contrast roles, not absolute shades: 100 is furthest from the canvas,
 * 900 closest to it. Light mode mirrors the dark scale around the ground, so
 * `text-neutral-400` is muted text and `bg-accent-900` a faint tint in both modes,
 * at the same contrast, and components need no per-mode classes.
 */
import { clampChroma, formatHex, oklch, wcagContrast, type Oklch } from 'culori'
import type { ThemeMode } from '@/config/themeSchema'
import { STEPS } from './tokens'
const DARK_LIGHTNESS = [0.971, 0.93, 0.869, 0.779, 0.68, 0.579, 0.48, 0.381, 0.29]
// Mirrored around the grounds (L ≈ 0.2 dark, ≈ 0.98 light): 1.18 − L.
const LIGHTNESS: Record<ThemeMode, number[]> = {
  dark: DARK_LIGHTNESS,
  light: DARK_LIGHTNESS.map((l) => Math.round((1.18 - l) * 1000) / 1000),
}
const ACCENT_CHROMA = [0.12, 0.27, 0.52, 0.91, 1, 1, 0.83, 0.64, 0.38]
const NEUTRAL_CHROMA = [0.4, 0.63, 0.83, 0.97, 1, 0.97, 0.83, 0.63, 0.37]

export type Ramp = Record<(typeof STEPS)[number], string>

function toOklch(hex: string): Oklch {
  const color = oklch(hex)
  if (!color) throw new Error(`Not a colour: ${hex}`)
  return color
}

const toHex = (color: Oklch) => formatHex(clampChroma(color, 'oklch'))

function ramp(base: Oklch, peakChroma: number, profile: number[], mode: ThemeMode): Ramp {
  const entries = STEPS.map((step, i) => {
    const color: Oklch = { mode: 'oklch', l: LIGHTNESS[mode][i], c: peakChroma * profile[i], h: base.h ?? 0 }
    return [step, toHex(color)] as const
  })
  return Object.fromEntries(entries) as Ramp
}

export function accentRamp(accentHex: string, mode: ThemeMode = 'dark'): Ramp {
  const accent = toOklch(accentHex)
  return ramp(accent, accent.c, ACCENT_CHROMA, mode)
}

/** Neutrals take the background's hue, at a low chroma (blue-grey on the default theme). */
export function neutralRamp(bgHex: string, mode: ThemeMode = 'dark'): Ramp {
  const bg = toOklch(bgHex)
  return ramp(bg, Math.min(bg.c * 1.1, 0.06), NEUTRAL_CHROMA, mode)
}

/**
 * A card surface one small step off the ground: lighter on a dark ground; towards
 * white on a light one (a darker shade if the ground is already white).
 */
export function deriveSurface(bgHex: string): string {
  const bg = toOklch(bgHex)
  const c = bg.c * 0.86
  if (bg.l < 0.5) return toHex({ ...bg, l: bg.l + 0.054, c })
  return toHex({ ...bg, l: bg.l < 0.99 ? Math.min(1, bg.l + 0.03) : bg.l - 0.035, c })
}

/**
 * Moves `fgHex` away from the ground in OKLCH lightness (hue kept) until it reaches
 * `minRatio` WCAG contrast against `bgHex`. Colours that already pass come back unchanged.
 */
export function ensureContrast(fgHex: string, bgHex: string, minRatio = 4.5): string {
  if (wcagContrast(fgHex, bgHex) >= minRatio) return fgHex
  const fg = toOklch(fgHex)
  const direction = toOklch(bgHex).l < 0.5 ? 1 : -1
  for (let l = fg.l; l >= 0 && l <= 1; l += direction * 0.01) {
    const candidate = toHex({ ...fg, l })
    if (wcagContrast(candidate, bgHex) >= minRatio) return candidate
  }
  return direction > 0 ? '#ffffff' : '#000000'
}

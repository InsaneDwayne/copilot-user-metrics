/**
 * The colour tokens a theme can override, as named in shared/styles/index.css
 * (`--color-<name>`, Tailwind utilities `bg-<name>`, `text-<name>`, ...).
 * tokens.test.ts keeps ROLE_TOKENS in step with the stylesheet.
 *
 * Imported by the theme schema, which scripts/theme-schema.ts runs under plain Node:
 * keep this module free of imports.
 */
export const STEPS = [100, 200, 300, 400, 500, 600, 700, 800, 900] as const

/** Layer 3: what components use. Each defaults to a ramp step in index.css. */
export const ROLE_TOKENS = [
  'fg-soft',
  'fg-muted',
  'fg-subtle',
  'line',
  'line-strong',
  'well',
  'tint',
  'on-tint',
  'chip',
  'on-chip',
  'notice',
  'on-notice',
  'notice-line',
  'warning',
  'error',
  'meter',
  'meter-track',
  'series-1',
  'series-2',
  'series-3',
  'series-4',
  'series-5',
  'series-6',
  'series-7',
  'series-8',
  'chart-line',
  'chart-included',
  'chart-billed',
  'chart-projection',
  'chart-grid',
  'chart-axis',
  'chart-label',
  'chart-cursor',
  'heat-1',
  'heat-2',
  'heat-3',
] as const

/** Tokens a role override may point at instead of a hex colour: base colours and ramp steps. */
export const PALETTE_TOKENS = [
  'canvas',
  'surface',
  'fg',
  'accent',
  ...STEPS.map((s) => `accent-${s}` as const),
  ...STEPS.map((s) => `neutral-${s}` as const),
] as const

/** A token override value: `#rrggbb`, or the name of a palette token (e.g. `accent-300`). */
export const tokenValue = (value: string): string =>
  (PALETTE_TOKENS as readonly string[]).includes(value) ? `var(--color-${value})` : value

/** Utility classes for the categorical series, in order (literal, so Tailwind generates them). */
const SERIES_BG = [
  'bg-series-1',
  'bg-series-2',
  'bg-series-3',
  'bg-series-4',
  'bg-series-5',
  'bg-series-6',
  'bg-series-7',
  'bg-series-8',
]
/** The same series as SVG fills. */
const SERIES_FILL = [
  'fill-series-1',
  'fill-series-2',
  'fill-series-3',
  'fill-series-4',
  'fill-series-5',
  'fill-series-6',
  'fill-series-7',
  'fill-series-8',
]
/** Series past the last slot share it: that slot stands for "everything else", never a recycled hue. */
const slot = (index: number) => Math.min(index, SERIES_BG.length - 1)
export const SERIES_COUNT = SERIES_BG.length
export const seriesBg = (index: number) => SERIES_BG[slot(index)]
export const seriesFill = (index: number) => SERIES_FILL[slot(index)]

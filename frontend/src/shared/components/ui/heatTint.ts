/** The heat-map role tints, faint to strong. */
const TINTS = ['bg-heat-1', 'bg-heat-2', 'bg-heat-3'] as const

/** The tint for `value` on a 0…`max` scale; none for zero. */
export function heatTint(value: number, max: number): string | undefined {
  if (value <= 0 || max <= 0) return undefined
  return TINTS[Math.min(TINTS.length - 1, Math.floor((value / max) * TINTS.length))]
}

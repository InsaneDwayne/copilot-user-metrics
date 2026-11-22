import { DEFAULT_IDLE_DAYS, IDLE_THRESHOLDS, type IdleThreshold } from '@/features/admin/api/admin'

/** The `idle` URL param: one of the offered thresholds, else the default. */
export function parseIdleDays(value: string | null): IdleThreshold {
  return IDLE_THRESHOLDS.find((d) => String(d) === value) ?? DEFAULT_IDLE_DAYS
}

/** The URL value for a threshold: the default leaves the param out. */
export const idleDaysParam = (days: IdleThreshold) => (days === DEFAULT_IDLE_DAYS ? null : String(days))

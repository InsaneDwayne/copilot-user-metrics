import type { OrgSummary } from '@/features/org-summary/api/orgSummary'

/** The org's AI credits per seat in the period; null without seats. */
export const creditsPerSeat = (org: OrgSummary) => (org.seats > 0 ? org.totals.credits / org.seats : null)

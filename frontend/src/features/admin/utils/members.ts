import type { MemberUsage, Segment, SegmentCount } from '@/features/admin/api/admin'

/** The admin drill-down page for one member. */
export const memberPath = (login: string) => `/admin/members/${encodeURIComponent(login)}`

/** Share of a member's own budget used this month (may pass 1); null without a budget. */
export function budgetUsed(m: MemberUsage): number | null {
  const b = m.budget
  if (!b || b.amount_usd <= 0) return null
  return b.consumed_usd / b.amount_usd
}

/** The activity segments as the filter and the adoption page name them. */
export const SEGMENT_LABELS: Record<Segment, string> = {
  regular: 'Regular · 7+ days',
  occasional: 'Occasional · 1–6 days',
  none: 'No activity',
}

/** Most active first, for lists and filters. */
export const SEGMENT_ORDER: Segment[] = ['regular', 'occasional', 'none']

/** Members in segment `s`; 0 when it isn't listed. */
export const membersIn = (counts: SegmentCount[], s: Segment) => counts.find((c) => c.segment === s)?.members ?? 0

export const parseSegment = (value: string | null): Segment | null => SEGMENT_ORDER.find((s) => s === value) ?? null

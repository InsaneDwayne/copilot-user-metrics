import { z } from 'zod'
import { apiGet } from '@/shared/api/client'
import {
  budgetSchema,
  creditTotalsSchema,
  dailyCreditsSchema,
  periodSchema,
  projectionSchema,
  seatCostSchema,
} from '@/shared/api/schemas'
import type { DayRange } from '@/shared/utils/period'

const orgSummarySchema = z.object({
  period: periodSchema,
  seats: z.number(),
  active_seats: z.number(),
  totals: creditTotalsSchema,
  projection: projectionSchema.nullable(),
  daily: z.array(dailyCreditsSchema),
  budgets: z.array(budgetSchema),
  seat_cost: seatCostSchema.nullable(),
})

export type OrgSummary = z.infer<typeof orgSummarySchema>

/** Org totals, GitHub budgets and seat cost (admins and organization readers), never per person. */
export const fetchOrgSummary = (r: DayRange) => apiGet('/api/org/summary', orgSummarySchema, r)

/** Schemas shared by several features (mirrors of backend value objects). */
import { z } from 'zod'

export const isoDay = z.iso.date()

export const periodSchema = z.object({ start: isoDay, end: isoDay })

export const creditTotalsSchema = z.object({
  credits: z.number(),
  gross_usd: z.number(),
  included_usd: z.number(),
  billed_usd: z.number(),
})

export const dailyCreditsSchema = z.object({
  day: isoDay,
  credits: z.number(),
  gross_usd: z.number(),
  billed_usd: z.number(),
})

export const projectionSchema = z.object({
  elapsed_days: z.number(),
  total_days: z.number(),
  daily_average: z.number(),
  projected_credits: z.number(),
  projected_gross_usd: z.number(),
})

/** A GitHub spending budget (dollars, current month) as last synced. */
export const budgetSchema = z.object({
  id: z.string(),
  scope: z.string(),
  sku: z.string(),
  amount_usd: z.number(),
  consumed_usd: z.number(),
  prevent_further_usage: z.boolean(),
  expires_at: z.string().nullable(),
  synced_at: z.string(),
})

/** Copilot seat charges for one month, from GitHub's billing usage summary. */
export const seatCostSchema = z.object({
  month: isoDay,
  /**
   * Seat usage GitHub billed so far, in user-months (not a head count): seats are billed per
   * day, so 86 seats on day 13 of a 30-day month are ~37.3 user-months.
   */
  seats: z.number(),
  price_per_seat_usd: z.number(),
  gross_usd: z.number(),
  net_usd: z.number(),
})

/** One page of a server-side list (backend ``Page``). A page past the end is answered with the last page. */
export const pageSchema = <T extends z.ZodType>(item: T) =>
  z.object({
    items: z.array(item),
    total: z.number(),
    page: z.number(),
    size: z.number(),
    pages: z.number(),
  })

export type CreditTotals = z.infer<typeof creditTotalsSchema>
export type DailyCredits = z.infer<typeof dailyCreditsSchema>
export type Projection = z.infer<typeof projectionSchema>
export type Budget = z.infer<typeof budgetSchema>
export type SeatCost = z.infer<typeof seatCostSchema>

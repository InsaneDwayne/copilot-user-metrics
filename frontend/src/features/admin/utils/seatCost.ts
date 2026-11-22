import type { CreditTotals, SeatCost } from '@/shared/api/schemas'
import { cycleOf, todayUtc, type IsoDay } from '@/shared/utils/dates'
import { formatUsd } from '@/shared/utils/format'

interface SeatCostView {
  label: string
  value: string
  meta: string
}

/** Whether `cost` is for the month that is still running (so seats are a commitment, not billed yet). */
const isCurrentMonth = (cost: SeatCost, assignedSeats: number, today: IsoDay) =>
  cost.month === cycleOf(today).start && assignedSeats > 0

/**
 * What the seats cost for the month. For the current month that is the commitment: every
 * assigned seat at GitHub's price (GitHub's own figure is only billed-so-far, since seats are
 * billed per day). A closed month is what GitHub billed, which already reflects seats
 * added or removed during it.
 */
const seatCostUsd = (cost: SeatCost, assignedSeats: number, today: IsoDay = todayUtc()) =>
  isCurrentMonth(cost, assignedSeats, today) ? assignedSeats * cost.price_per_seat_usd : cost.net_usd

export function seatCostView(cost: SeatCost, assignedSeats: number, today: IsoDay = todayUtc()): SeatCostView {
  const price = formatUsd(cost.price_per_seat_usd)
  const value = formatUsd(seatCostUsd(cost, assignedSeats, today))
  if (isCurrentMonth(cost, assignedSeats, today))
    return { label: 'Seat cost', value, meta: `${assignedSeats} seats × ${price} this month` }
  return { label: 'Seat cost', value, meta: `Billed by GitHub · ${price} per seat` }
}

/**
 * The month's total Copilot cost: the seats plus the AI credits billed beyond the included
 * credits (the spend that counts against the organization budget).
 */
export function totalCostView(cost: SeatCost, assignedSeats: number, totals: CreditTotals, today: IsoDay = todayUtc()) {
  const seats = seatCostUsd(cost, assignedSeats, today)
  return {
    label: 'Total cost',
    value: formatUsd(seats + totals.billed_usd),
    meta: `${formatUsd(seats)} seats + ${formatUsd(totals.billed_usd)} billed credits`,
  }
}

/**
 * How much of the month's included AI credits is used. GitHub's API doesn't report the pool size,
 * so it is taken to be worth the seat cost, until GitHub bills credits beyond it: then the pool is
 * used up, and what it covered (``included_usd``) is its actual size.
 */
export function includedUsage(cost: SeatCost, assignedSeats: number, totals: CreditTotals, today: IsoDay = todayUtc()) {
  const used = totals.included_usd
  const exhausted = totals.billed_usd > 0 && used > 0
  const pool = exhausted ? used : seatCostUsd(cost, assignedSeats, today)
  return { pool, used, exhausted, ratio: exhausted ? 1 : pool > 0 ? Math.min(1, used / pool) : 0 }
}

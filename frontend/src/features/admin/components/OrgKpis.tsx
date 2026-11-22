import { KpiGrid } from '@/shared/components/ui/Kpi'
import { includedCoverage } from '@/shared/utils/budget'
import { formatCredits, formatDay, formatUsd } from '@/shared/utils/format'
import { creditsPerSeat, type OrgSummary } from '@/features/org-summary'
import { seatCostView, totalCostView } from '@/features/admin/utils/seatCost'

/** Org headline numbers — every figure as GitHub reports it. */
export function OrgKpis({ org }: { org: OrgSummary }) {
  const { totals, projection, period, seat_cost: seatCost } = org
  const perSeat = creditsPerSeat(org)
  return (
    <KpiGrid
      items={[
        { label: 'Seats', value: String(org.seats), meta: `${org.active_seats} active this cycle` },
        {
          label: 'AI credits used',
          value: formatCredits(totals.credits),
          meta: perSeat === null ? `${formatUsd(totals.gross_usd)} list value` : `${formatCredits(perSeat)} per seat`,
        },
        projection
          ? {
              label: `Projected by ${formatDay(period.end)}`,
              value: formatCredits(projection.projected_credits),
              meta: `≈ ${formatUsd(projection.projected_gross_usd)} list value at this pace`,
            }
          : { label: 'List value', value: formatUsd(totals.gross_usd), meta: 'Of the AI credits used' },
        {
          label: 'Billed',
          value: formatUsd(totals.billed_usd),
          meta: includedCoverage(totals),
        },
        seatCost
          ? seatCostView(seatCost, org.seats)
          : { label: 'Seat cost', value: '—', meta: 'Not listed in GitHub’s usage summary for this period' },
        seatCost
          ? totalCostView(seatCost, org.seats, totals)
          : { label: 'Total cost', value: '—', meta: 'Needs the seat cost, so only for a single month' },
      ]}
    />
  )
}

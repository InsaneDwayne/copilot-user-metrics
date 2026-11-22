import { KpiGrid, type KpiItem } from '@/shared/components/ui/Kpi'
import { includedCoverage } from '@/shared/utils/budget'
import { formatCredits, formatDay, formatUsd } from '@/shared/utils/format'
import type { UsageSubject, UsageSummary } from '@/features/usage/api/usage'
import { compareToAverage } from '@/features/usage/utils/compare'
import { usageStats } from '@/features/usage/utils/usageSeries'

interface UsageKpisProps {
  summary: UsageSummary
  subject: UsageSubject
  /** AI credits per seat across the org in the same period; null while unknown. */
  orgAverage: number | null
  /** Org owners also see what GitHub billed and what the included credits covered. */
  showBilling: boolean
}

/** Headline numbers for one person: how much, at what pace, how often, compared with the org. */
export function UsageKpis({ summary, subject, orgAverage, showBilling }: UsageKpisProps) {
  const { totals, projection, period } = summary
  const stats = usageStats(summary.daily)
  const items: KpiItem[] = [
    {
      label: 'AI credits used',
      value: formatCredits(totals.credits),
      meta: `≈ ${formatUsd(totals.gross_usd)} at list price`,
    },
    projection
      ? {
          label: `Projected by ${formatDay(period.end)}`,
          value: formatCredits(projection.projected_credits),
          meta: `At ${formatCredits(projection.daily_average)} a day so far`,
        }
      : {
          label: 'Average per active day',
          value: formatCredits(stats.averagePerActiveDay),
          meta: `Over ${stats.activeDays} day${stats.activeDays === 1 ? '' : 's'} with usage`,
        },
    {
      label: 'Days with usage',
      value: `${stats.activeDays} of ${stats.elapsedDays}`,
      meta: stats.peak
        ? `Peak ${formatCredits(stats.peak.credits)} on ${formatDay(stats.peak.day)}`
        : 'No usage yet in this period',
    },
  ]
  if (orgAverage !== null)
    items.push({
      label: 'Org average per seat',
      value: formatCredits(orgAverage),
      meta: compareToAverage(totals.credits, orgAverage, subject),
    })
  if (showBilling)
    items.push({
      label: 'Billed',
      value: formatUsd(totals.billed_usd),
      meta: includedCoverage(totals),
    })
  return <KpiGrid items={items} />
}

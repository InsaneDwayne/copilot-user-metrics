import { QueryState } from '@/shared/components/QueryState'
import type { ResolvedPeriod } from '@/shared/utils/period'
import { useAppConfig } from '@/features/app-config'
import { creditsPerSeat, useOrgSummary } from '@/features/org-summary'
import type { UsageSubject } from '@/features/usage/api/usage'
import { useUsageDaily, useUsageModelTokens, useUsageSummary } from '@/features/usage/hooks/useUsage'
import { BudgetCard } from './BudgetCard'
import { UsageExplorer } from '@/features/usage/components/explorer/UsageExplorer'
import { UsageKpis } from './UsageKpis'

interface UsageOverviewProps {
  subject: UsageSubject
  period: ResolvedPeriod
  /** Admins and organization readers (in the member drill-down) also see billing. */
  showBilling?: boolean
}

/** Everything about one person's AI credits — "My usage" and the admin drill-down. */
export function UsageOverview({ subject, period, showBilling = false }: UsageOverviewProps) {
  const summary = useUsageSummary(subject, period.range)
  const daily = useUsageDaily(subject, period.range)
  const tokens = useUsageModelTokens(subject, period.range)
  // Your own page shows only your own numbers. Org context (the per-seat average, org-wide
  // budgets) is for admins and organization readers looking at a member in the admin console.
  const orgContext = subject.kind === 'member'
  const org = useOrgSummary(period.range, { enabled: orgContext })
  const orgName = useAppConfig().data?.org
  const orgAverage = orgContext && org.data ? creditsPerSeat(org.data) : null
  const csvName = subject.kind === 'me' ? 'my-copilot-usage' : `copilot-usage-${subject.login}`
  return (
    <div className="flex flex-col gap-4">
      <QueryState query={summary} minHeight={104}>
        {(s) => (
          <>
            <UsageKpis summary={s} subject={subject} orgAverage={orgAverage} showBilling={showBilling} />
            {period.isCurrentCycle && orgName && (
              <BudgetCard summary={s} org={orgContext ? org.data : undefined} orgName={orgName} subject={subject} />
            )}
          </>
        )}
      </QueryState>
      <QueryState query={daily} minHeight={360}>
        {(items) => (
          <UsageExplorer
            items={items}
            range={period.range}
            showBilling={showBilling}
            csvName={csvName}
            tokens={tokens.data}
          />
        )}
      </QueryState>
    </div>
  )
}

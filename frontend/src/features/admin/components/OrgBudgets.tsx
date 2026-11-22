import { Link } from 'react-router'
import type { Budget } from '@/shared/api/schemas'
import { BudgetBar, BudgetMeter } from '@/shared/components/BudgetMeter'
import { Card, Note } from '@/shared/components/ui/Card'
import { budgetScopeLabel, isPerUserBudget } from '@/shared/utils/budget'
import { formatDate, formatPercent, formatUsd } from '@/shared/utils/format'
import type { OrgSummary } from '@/features/org-summary'
import { includedUsage } from '@/features/admin/utils/seatCost'

/**
 * The month's included AI credits (taken to be worth the seat cost) and the org-wide GitHub
 * budgets that cap spend beyond them. A default per-user budget caps each person separately, so
 * it is named here without a meter; its use is per member on the Members tab.
 */
export function OrgBudgets({ org, showBudgets }: { org: OrgSummary; showBudgets: boolean }) {
  const { seat_cost: seatCost } = org
  if (!seatCost && !showBudgets) return null
  const orgWide = org.budgets.filter((b) => !isPerUserBudget(b))
  const perUser = org.budgets.filter(isPerUserBudget)
  return (
    <Card
      title="Organization budgets"
      subtitle="Included AI credits from the seats, and the Copilot budgets set in GitHub billing for spend beyond them."
    >
      {seatCost && <IncludedMeter org={org} />}
      {showBudgets && orgWide.length === 0 && (
        <div className="text-xs text-fg-muted">
          No organization-wide Copilot budget is set in GitHub, so total AI credit spend beyond the included credits is
          not capped{perUser.length > 0 ? ", only each person's spend" : ''}.
        </div>
      )}
      {showBudgets && orgWide.map((b) => <BudgetMeter key={b.id} budget={b} />)}
      {showBudgets && perUser.map((b) => <PerUserBudget key={b.id} budget={b} />)}
      <Note>
        GitHub doesn&apos;t report the size of the included credit pool, so it is taken to be worth the seat cost until
        GitHub starts billing beyond it (then it is used up). Personal and default per-user budgets are tracked per
        member on the Members tab.
      </Note>
    </Card>
  )
}

/** A default budget GitHub applies to each user on their own: its size and behaviour, no org-wide meter. */
function PerUserBudget({ budget: b }: { budget: Budget }) {
  return (
    <div className="flex flex-col gap-1 text-xs">
      <div className="flex flex-wrap items-center justify-between gap-2.5">
        <span>{budgetScopeLabel(b.scope)}</span>
        <span className="text-fg-muted tabular-nums">{formatUsd(b.amount_usd)} per person</span>
      </div>
      <div className="text-fg-subtle">
        Applies to every member without a personal budget ·{' '}
        {b.prevent_further_usage ? 'usage stops when it is used up' : 'alerts only, usage continues past it'}
        {b.expires_at && ` · expires ${formatDate(b.expires_at)}`}
        {` · ${b.sku} · `}
        <Link className="text-accent hover:underline" to={{ pathname: '/admin/members' }}>
          Use per member
        </Link>
      </div>
    </div>
  )
}

/** Included AI credits used vs. a pool worth the month's seat cost. */
function IncludedMeter({ org }: { org: OrgSummary }) {
  if (!org.seat_cost) return null
  const { pool, used, ratio, exhausted } = includedUsage(org.seat_cost, org.seats, org.totals)
  const name = 'Included credits (seat cost)'
  return (
    <div className="flex flex-col gap-2">
      <div className="flex flex-wrap items-center justify-between gap-2.5 text-xs">
        <span>{name}</span>
        <span className="text-fg-muted tabular-nums">
          {exhausted ? (
            <>{formatUsd(used)} used · 100% · none left</>
          ) : (
            <>
              {formatUsd(used)} of {formatUsd(pool)} · {formatPercent(pool > 0 ? ratio : null)} used ·{' '}
              {formatUsd(Math.max(0, pool - used))} left
            </>
          )}
        </span>
      </div>
      <BudgetBar used={ratio} label={`${name} used`} />
      <div className="text-xs text-fg-subtle">
        {formatUsd(org.totals.billed_usd)} billed beyond the included credits, against the organization budget
      </div>
    </div>
  )
}

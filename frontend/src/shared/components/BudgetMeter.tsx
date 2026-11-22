import type { Budget } from '@/shared/api/schemas'
import { budgetLeft, budgetScopeLabel } from '@/shared/utils/budget'
import { formatDate, formatUsd } from '@/shared/utils/format'
import { ShareBar } from '@/shared/components/ui/ShareBar'

/** A GitHub budget: consumed vs. amount, and what happens at the limit. */
export function BudgetMeter({ budget, label }: { budget: Budget; label?: string }) {
  const ratio = budget.amount_usd > 0 ? budget.consumed_usd / budget.amount_usd : 0
  const name = label ?? budgetScopeLabel(budget.scope)
  return (
    <div className="flex flex-col gap-2">
      <div className="flex flex-wrap items-center justify-between gap-2.5 text-xs">
        <span>{name}</span>
        <span className="text-fg-muted tabular-nums">
          {formatUsd(budget.consumed_usd)} of {formatUsd(budget.amount_usd)} · {formatUsd(budgetLeft(budget))} left
        </span>
      </div>
      <BudgetBar used={ratio} label={`${name} consumed`} />
      <div className="text-xs text-fg-subtle">
        {budget.prevent_further_usage ? 'Usage stops when it is used up' : 'Alerts only — usage continues past it'}
        {budget.expires_at && ` · expires ${formatDate(budget.expires_at)}`}
        {` · ${budget.sku}`}
      </div>
    </div>
  )
}

/** A budget's consumption as a bar (0..1), in the billed colour from 90% up. */
export function BudgetBar({ used, label }: { used: number; label: string }) {
  return <ShareBar thick value={used} fill={used >= 0.9 ? 'bg-chart-billed' : undefined} label={label} />
}

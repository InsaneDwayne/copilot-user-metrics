import { BudgetMeter } from '@/shared/components/BudgetMeter'
import { Card } from '@/shared/components/ui/Card'
import { isPerUserBudget } from '@/shared/utils/budget'
import type { OrgSummary } from '@/features/org-summary'
import type { UsageSubject, UsageSummary } from '@/features/usage/api/usage'

interface BudgetCardProps {
  summary: UsageSummary
  org: OrgSummary | undefined
  orgName: string
  subject: UsageSubject
}

/** How the card names the person: as object ("you") and possessive ("your"). */
function names(subject: UsageSubject) {
  return subject.kind === 'me'
    ? { them: 'you', their: 'Your' }
    : { them: `@${subject.login}`, their: `@${subject.login}'s` }
}

/**
 * The GitHub budget that limits this person's Copilot spend this month: its amount, what they
 * have consumed and what is left. Org owners viewing a member also see the org-wide budgets.
 */
export function BudgetCard({ summary, org, orgName, subject }: BudgetCardProps) {
  const { them, their } = names(subject)
  const own = summary.budget
  // The org-wide budgets, unless the person's effective budget already is one of them. A default
  // per-user budget only has a meaningful meter as the person's own (``own``), never org-wide.
  const orgBudgets = (org?.budgets ?? []).filter((b) => b.id !== own?.id && !isPerUserBudget(b))
  if (!own && orgBudgets.length === 0)
    return (
      <Card title="Budget">
        <div className="text-xs text-fg-muted">
          No Copilot budget in GitHub applies to {them} this month, so AI credit spend isn&apos;t capped by a budget.
        </div>
      </Card>
    )
  return (
    <Card title="Budget">
      {own && (
        <BudgetMeter
          budget={own}
          label={
            own.scope === 'user'
              ? `${their} personal budget`
              : isPerUserBudget(own)
                ? `${their} budget: ${orgName} default per-user budget`
                : `Applies to ${them}: ${orgName} budget`
          }
        />
      )}
      {orgBudgets.map((b) => (
        <BudgetMeter key={b.id} budget={b} label={`${orgName} · organization budget (everyone)`} />
      ))}
    </Card>
  )
}

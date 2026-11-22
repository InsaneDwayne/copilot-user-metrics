import type { Budget, CreditTotals } from '@/shared/api/schemas'
import { formatPercent, formatUsd } from './format'

/**
 * Whether a budget caps each person separately: a personal budget (``user``) or a default that
 * GitHub applies to every user on their own (``multi_user_customer``). Its consumption only
 * means something for one person, so it never belongs on an org-wide meter.
 */
export const isPerUserBudget = (b: Pick<Budget, 'scope'>) => b.scope === 'user' || b.scope.includes('multi_user')

/** How GitHub's budget scopes read in the UI. */
export const budgetScopeLabel = (scope: string) =>
  scope === 'user'
    ? 'Personal budget'
    : scope === 'organization'
      ? 'Organization budget'
      : isPerUserBudget({ scope })
        ? 'Default per-user budget'
        : `Budget · ${scope}`

/** What is left of a budget this month (never negative). */
export const budgetLeft = (b: Budget) => Math.max(0, b.amount_usd - b.consumed_usd)

/** "$12.00 covered by included credits (40%)": the part of the list value GitHub didn't bill. */
export const includedCoverage = (t: CreditTotals) =>
  `${formatUsd(t.included_usd)} covered by included credits (${formatPercent(t.gross_usd ? t.included_usd / t.gross_usd : null)})`

import { describe, expect, it } from 'vitest'
import { budgetScopeLabel, isPerUserBudget } from './budget'

describe('isPerUserBudget', () => {
  it('treats personal and default per-user budgets as per person', () => {
    expect(isPerUserBudget({ scope: 'user' })).toBe(true)
    expect(isPerUserBudget({ scope: 'multi_user_customer' })).toBe(true)
    expect(isPerUserBudget({ scope: 'organization' })).toBe(false)
    expect(isPerUserBudget({ scope: 'enterprise' })).toBe(false)
  })

  it('labels the default per-user budget', () => {
    expect(budgetScopeLabel('multi_user_customer')).toBe('Default per-user budget')
  })
})

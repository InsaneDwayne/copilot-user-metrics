import { describe, expect, it } from 'vitest'
import type { MemberUsage } from '@/features/admin/api/admin'
import { budgetUsed } from './members'

const member = (login: string, teams: string[]): MemberUsage => ({
  user_id: 1,
  login,
  avatar_url: null,
  teams,
  credits: 0,
  gross_usd: 0,
  share: 0,
  top_model: null,
  last_activity_at: null,
  last_activity_editor: null,
  budget: null,
  active_days: 0,
  prompts: 0,
  acceptance_rate: null,
  segment: 'none',
  adoption_phase: null,
})

describe('members utils', () => {
  it("measures budget use against each member's own budget", () => {
    const withBudget = (login: string, credits: number, consumed: number, amount: number): MemberUsage => ({
      ...member(login, []),
      credits,
      budget: {
        id: login,
        scope: amount === 40 ? 'organization' : 'user',
        sku: 'ai_credits',
        amount_usd: amount,
        consumed_usd: consumed,
        prevent_further_usage: true,
        expires_at: null,
        synced_at: '2026-11-13T00:00:00Z',
      },
    })
    const team = [withBudget('a', 900, 30, 40), withBudget('b', 5000, 100, 400), member('c', [])]
    expect(budgetUsed(team[0])).toBe(0.75)
    expect(budgetUsed(team[1])).toBe(0.25)
    expect(budgetUsed(team[2])).toBeNull()
  })
})

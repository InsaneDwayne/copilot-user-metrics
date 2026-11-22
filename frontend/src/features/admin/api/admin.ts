import { z } from 'zod'
import { apiDownload, apiGet } from '@/shared/api/client'
import { budgetSchema, isoDay, pageSchema, periodSchema, seatCostSchema } from '@/shared/api/schemas'
import { pageParam } from '@/shared/utils/pagination'
import type { DayRange } from '@/shared/utils/period'
import {
  adoptionPhaseSchema,
  codeChangesSchema,
  dailyModelUsageSchema,
  languageModelSchema,
  modelFeatureSchema,
  modelTokensSchema,
  surfaceSchema,
} from '@/features/usage'

/** How often a seat holder used Copilot in the period: no day, 1–6 days, 7 or more. */
const segmentSchema = z.enum(['none', 'occasional', 'regular'])
const segmentCountSchema = z.object({ segment: segmentSchema, members: z.number() })

const memberUsageSchema = z.object({
  user_id: z.number(),
  login: z.string(),
  avatar_url: z.string().nullable(),
  teams: z.array(z.string()),
  credits: z.number(),
  gross_usd: z.number(),
  share: z.number(),
  top_model: z.string().nullable(),
  last_activity_at: z.string().nullable(),
  last_activity_editor: z.string().nullable(),
  budget: budgetSchema.nullable(),
  active_days: z.number(),
  prompts: z.number(),
  acceptance_rate: z.number().nullable(),
  segment: segmentSchema,
  adoption_phase: adoptionPhaseSchema.nullable(),
})

const teamUsageSchema = z.object({
  team: z.string(),
  seats: z.number(),
  active_7d: z.number(),
  credits: z.number(),
  gross_usd: z.number(),
  acceptance_rate: z.number().nullable(),
  top_model: z.string().nullable(),
})

const idleSeatSchema = z.object({
  login: z.string(),
  avatar_url: z.string().nullable(),
  teams: z.array(z.string()),
  assigned_at: z.string().nullable(),
  last_activity_at: z.string().nullable(),
  status: z.enum(['never_used', 'inactive']),
  inactive_days: z.number().nullable(),
  /** GitHub already removes the seat at the end of this cycle. */
  pending_cancellation_date: isoDay.nullable(),
})

const seatOverviewSchema = z.object({
  idle_after_days: z.number(),
  assigned: z.number(),
  active: z.number(),
  inactive: z.number(),
  never_used: z.number(),
  /** Assigned within the threshold and not used yet: too new to call idle. */
  recently_assigned: z.number(),
  pending_cancellation: z.number(),
  /** Idle seats not already being removed, and their monthly fee (null until GitHub lists the price). */
  reclaimable: z.number(),
  reclaimable_usd: z.number().nullable(),
  seat_cost: seatCostSchema.nullable(),
  /** Idle seats, reclaimable first (never used, then longest idle), pending cancellation last; one page. */
  idle: pageSchema(idleSeatSchema),
})

/** One page of members; `total` counts the filtered list, `members` everyone in the period. */
const memberPageSchema = pageSchema(memberUsageSchema).extend({
  members: z.number(),
  /** Every team among the period's members, for the team filter. */
  teams: z.array(z.string()),
  /** Members per segment after the team and login filters, before the segment filter. */
  segments: z.array(segmentCountSchema),
})

/** Who in the org uses Copilot, how often and for what. */
const orgAdoptionSchema = z.object({
  period: periodSchema,
  data_through: isoDay.nullable(),
  seats: z.number(),
  active_users: z.number(),
  average_daily_active: z.number().nullable(),
  prompts: z.number(),
  loc_suggested: z.number(),
  loc_added: z.number(),
  acceptance_rate: z.number().nullable(),
  daily: z.array(
    z.object({
      day: isoDay,
      active_users: z.number(),
      active_7d: z.number(),
      active_28d: z.number(),
      prompts: z.number(),
      acceptance_rate: z.number().nullable(),
      loc_added: z.number(),
    }),
  ),
  segments: z.array(segmentCountSchema),
  /** Lowest phase first; `phase: null` counts seat holders GitHub reported no phase for. */
  phases: z.array(z.object({ phase: adoptionPhaseSchema.nullable(), members: z.number() })),
  surfaces: z.array(z.object({ surface: surfaceSchema, users: z.number() })),
  features: z.array(z.object({ name: z.string(), users: z.number(), prompts: z.number() })),
  /** People who invoked each skill and how often, most people first. */
  skills: z.array(z.object({ name: z.string(), users: z.number(), invocations: z.number() })),
  languages: z.array(
    z.object({
      language: z.string(),
      users: z.number(),
      loc_added: z.number(),
      acceptance_rate: z.number().nullable(),
    }),
  ),
  ides: z.array(z.object({ ide: z.string(), users: z.number() })),
  code_changes: codeChangesSchema,
  model_features: z.array(modelFeatureSchema),
  language_models: z.array(languageModelSchema),
})

const namedCountSchema = z.object({ name: z.string(), count: z.number() })

/** GitHub's org-wide daily report over a period: pull requests, MCP servers, custom agents, coverage. */
const orgReportSchema = z.object({
  period: periodSchema,
  days_reported: z.number(),
  /** Null when no reported day had pull request numbers. */
  pull_requests: z
    .object({
      created: z.number(),
      created_by_copilot: z.number(),
      reviewed: z.number(),
      reviewed_by_copilot: z.number(),
      merged: z.number(),
      merged_created_by_copilot: z.number(),
      suggestions: z.number(),
      applied_suggestions: z.number(),
      copilot_suggestions: z.number(),
      copilot_applied_suggestions: z.number(),
      /** GitHub's daily medians, averaged weighted by the PRs merged each day. */
      minutes_to_merge: z.number().nullable(),
      minutes_to_merge_copilot: z.number().nullable(),
    })
    .nullable(),
  daily: z.array(
    z.object({
      day: isoDay,
      created: z.number(),
      created_by_copilot: z.number(),
      merged: z.number(),
      merged_created_by_copilot: z.number(),
      reviewed_by_copilot: z.number(),
    }),
  ),
  mcp_servers: z.array(namedCountSchema),
  custom_agents: z.array(namedCountSchema),
  /** As of the last reported day; null without any report. */
  coverage: z
    .object({
      day: isoDay,
      missing_telemetry_users: z.number().nullable(),
      below_minimum_users: z.number().nullable(),
      daily_active_users: z.number().nullable(),
      weekly_active_users: z.number().nullable(),
      monthly_active_users: z.number().nullable(),
    })
    .nullable(),
})

const memberProfileSchema = z.object({
  user_id: z.number(),
  login: z.string(),
  avatar_url: z.string().nullable(),
  assigned_at: z.string().nullable(),
  ended_at: z.string().nullable(),
  last_activity_at: z.string().nullable(),
  last_activity_editor: z.string().nullable(),
})

export type MemberUsage = z.infer<typeof memberUsageSchema>
export type TeamUsage = z.infer<typeof teamUsageSchema>
export type SeatOverview = z.infer<typeof seatOverviewSchema>
export type IdleSeat = z.infer<typeof idleSeatSchema>
export type MemberPage = z.infer<typeof memberPageSchema>
export type Segment = z.infer<typeof segmentSchema>
export type SegmentCount = z.infer<typeof segmentCountSchema>
export type OrgAdoption = z.infer<typeof orgAdoptionSchema>
export type OrgReport = z.infer<typeof orgReportSchema>

export type MemberSort = 'credits' | 'budget' | 'active_days'

/** Filters, order and page for `/api/admin/members`; defaults are left out of the request. */
export interface MemberParams {
  team?: string | null
  /** Part of the login, any case. */
  q?: string | null
  segment?: Segment | null
  sort?: MemberSort
  page?: number
  size?: number
}

const memberQuery = (r: DayRange, p: MemberParams) => ({
  ...r,
  team: p.team,
  q: p.q,
  segment: p.segment,
  sort: p.sort && p.sort !== 'credits' ? p.sort : null,
})

export const fetchMembers = (r: DayRange, p: MemberParams = {}) =>
  apiGet('/api/admin/members', memberPageSchema, {
    ...memberQuery(r, p),
    page: pageParam(p.page ?? 1),
    size: p.size ? String(p.size) : null,
  })
/** Every member matching the filters (not just the page), as CSV. */
export const downloadMembersCsv = (r: DayRange, p: MemberParams = {}) =>
  apiDownload('/api/admin/members.csv', memberQuery(r, p), `copilot-members-${r.from}_${r.to}.csv`)
/** The org's adoption, or one team's when `team` is given. */
export const fetchAdoption = (r: DayRange, team?: string) =>
  apiGet('/api/admin/adoption', orgAdoptionSchema, { ...r, team })
export const fetchOrgReport = (r: DayRange) => apiGet('/api/admin/org-report', orgReportSchema, r)
export const fetchTeams = (r: DayRange) => apiGet('/api/admin/teams', z.array(teamUsageSchema), r)
export const fetchOrgDaily = (r: DayRange) => apiGet('/api/admin/daily', z.array(dailyModelUsageSchema), r)
export const fetchOrgModelTokens = (r: DayRange) => apiGet('/api/admin/model-tokens', z.array(modelTokensSchema), r)
/** Days without activity after which a seat counts as idle; the API takes any 1–365. */
export const IDLE_THRESHOLDS = [7, 14, 30, 60] as const
export type IdleThreshold = (typeof IDLE_THRESHOLDS)[number]
export const DEFAULT_IDLE_DAYS: IdleThreshold = 7

const idleParam = (idleDays: number) => (idleDays !== DEFAULT_IDLE_DAYS ? String(idleDays) : null)

export const fetchSeats = (idleDays: number, page = 1, size?: number) =>
  apiGet('/api/admin/seats', seatOverviewSchema, {
    idle_days: idleParam(idleDays),
    page: pageParam(page),
    size: size ? String(size) : null,
  })
/** Every idle seat (not just the page), as CSV. */
export const downloadIdleSeatsCsv = (idleDays: number) =>
  apiDownload('/api/admin/seats/idle.csv', { idle_days: idleParam(idleDays) }, `copilot-idle-seats-${idleDays}d.csv`)
export const fetchMember = (login: string) =>
  apiGet(`/api/admin/members/${encodeURIComponent(login)}`, memberProfileSchema)

import { z } from 'zod'
import { apiGet } from '@/shared/api/client'
import {
  budgetSchema,
  creditTotalsSchema,
  dailyCreditsSchema,
  isoDay,
  periodSchema,
  projectionSchema,
} from '@/shared/api/schemas'
import type { DayRange } from '@/shared/utils/period'

/** Whose usage: the signed-in person, or a member an admin or organization reader opened. */
export type UsageSubject = { kind: 'me' } | { kind: 'member'; login: string }

export const subjectKey = (s: UsageSubject) => (s.kind === 'me' ? 'me' : `member:${s.login}`)
const base = (s: UsageSubject) => (s.kind === 'me' ? '/api/me' : `/api/admin/members/${encodeURIComponent(s.login)}`)

const usageSummarySchema = z.object({
  period: periodSchema,
  totals: creditTotalsSchema,
  projection: projectionSchema.nullable(),
  daily: z.array(dailyCreditsSchema),
  /** The GitHub budget that applies to this person (personal or org-wide); current cycle only. */
  budget: budgetSchema.nullable(),
})

export const dailyModelUsageSchema = z.object({
  day: isoDay,
  model: z.string(),
  credits: z.number(),
  gross_usd: z.number(),
  included_usd: z.number(),
  billed_usd: z.number(),
})

/** Model calls and tokens per model from GitHub's usage metrics (metrics model names, no cached tokens). */
export const modelTokensSchema = z.object({
  day: isoDay,
  model: z.string(),
  requests: z.number(),
  prompt_tokens: z.number(),
  output_tokens: z.number(),
})

export const surfaceSchema = z.enum(['chat', 'agent', 'cli', 'cloud_agent', 'code_review', 'app'])

/** GitHub's AI adoption phase: "No Cohort" (0), then "Phase 1" to "Phase 3"; higher is deeper use. */
export const adoptionPhaseSchema = z.object({
  number: z.number(),
  label: z.string(),
  version: z.string().nullable(),
})

/** Lines each feature suggested and changed; agent features changed code on their own. */
export const codeChangesSchema = z.object({
  by_feature: z.array(
    z.object({
      feature: z.string(),
      agent: z.boolean(),
      loc_suggested_add: z.number(),
      loc_suggested_delete: z.number(),
      loc_added: z.number(),
      loc_deleted: z.number(),
    }),
  ),
  loc_added: z.number(),
  loc_deleted: z.number(),
  agent_loc_changed: z.number(),
  /** Of all lines added and deleted; null without changes. */
  agent_share: z.number().nullable(),
})

/** The most used models' cells per feature, largest first. */
export const modelFeatureSchema = z.object({
  model: z.string(),
  feature: z.string(),
  prompts: z.number(),
  generations: z.number(),
  loc_changed: z.number(),
})

/** The most used languages × models, largest first. */
export const languageModelSchema = z.object({
  language: z.string(),
  model: z.string(),
  generations: z.number(),
  acceptances: z.number(),
  loc_changed: z.number(),
})

const activitySchema = z.object({
  period: periodSchema,
  data_through: isoDay.nullable(),
  active_days: z.number(),
  elapsed_days: z.number(),
  prompts: z.number(),
  generations: z.number(),
  acceptances: z.number(),
  loc_suggested: z.number(),
  loc_added: z.number(),
  acceptance_rate: z.number().nullable(),
  top_ide: z.string().nullable(),
  features: z.array(z.object({ name: z.string(), count: z.number() })),
  /** Invocations per skill, most used first. */
  skills: z.array(z.object({ name: z.string(), count: z.number() })),
  languages: z.array(z.object({ language: z.string(), loc_added: z.number(), acceptance_rate: z.number().nullable() })),
  surfaces: z.array(z.object({ surface: surfaceSchema, days: z.number() })),
  /** On the last day in the period that reports one. */
  adoption_phase: adoptionPhaseSchema.nullable(),
  code_changes: codeChangesSchema,
  model_features: z.array(modelFeatureSchema),
  language_models: z.array(languageModelSchema),
})

export type UsageSummary = z.infer<typeof usageSummarySchema>
export type DailyModelUsage = z.infer<typeof dailyModelUsageSchema>
export type ModelTokens = z.infer<typeof modelTokensSchema>
export type Activity = z.infer<typeof activitySchema>
export type Surface = z.infer<typeof surfaceSchema>
export type AdoptionPhase = z.infer<typeof adoptionPhaseSchema>
export type CodeChanges = z.infer<typeof codeChangesSchema>
export type ModelFeatureUse = z.infer<typeof modelFeatureSchema>
export type LanguageModelUse = z.infer<typeof languageModelSchema>

export const fetchSummary = (s: UsageSubject, r: DayRange) => apiGet(`${base(s)}/summary`, usageSummarySchema, r)
export const fetchDaily = (s: UsageSubject, r: DayRange) =>
  apiGet(`${base(s)}/daily`, z.array(dailyModelUsageSchema), r)
export const fetchModelTokens = (s: UsageSubject, r: DayRange) =>
  apiGet(`${base(s)}/model-tokens`, z.array(modelTokensSchema), r)
export const fetchActivity = (s: UsageSubject, r: DayRange) => apiGet(`${base(s)}/activity`, activitySchema, r)

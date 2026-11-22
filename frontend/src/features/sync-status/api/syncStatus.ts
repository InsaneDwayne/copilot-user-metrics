import { z } from 'zod'
import { apiGet, apiPost } from '@/shared/api/client'

const jobNameSchema = z.enum(['sync-seats', 'sync-credits', 'sync-metrics', 'sync-budgets', 'history'])

const jobStatusSchema = z.object({
  job: jobNameSchema,
  last_started_at: z.string().nullable(),
  last_status: z.enum(['running', 'succeeded', 'failed', 'aborted']).nullable(),
  last_error: z.string().nullable(),
  last_rows: z.number(),
  last_success_at: z.string().nullable(),
  failures_since_success: z.number(),
})

const syncStatusSchema = z.object({
  last_success_at: z.string().nullable(),
  stale: z.boolean(),
  jobs: z.array(jobStatusSchema),
})

export type JobName = z.infer<typeof jobNameSchema>
export type JobStatus = z.infer<typeof jobStatusSchema>

export const fetchSyncStatus = () => apiGet('/api/sync/status', syncStatusSchema)

// ---------------------------------------------------------------- run / stop (org owners)

const syncTargetSchema = z.enum(['credits', 'seats', 'budgets', 'metrics', 'history'])
const syncActionSchema = z.enum(['run', 'stop'])

const syncRequestSchema = z.object({
  id: z.number(),
  requested_at: z.string(),
  admin_login: z.string(),
  action: syncActionSchema,
  target: syncTargetSchema,
  handled_at: z.string().nullable(),
  outcome: z.string().nullable(),
})

const syncControlSchema = z.object({
  targets: z.array(z.object({ target: syncTargetSchema, queued: z.number(), running: z.number() })),
  requests: z.array(syncRequestSchema),
})

export type SyncTarget = z.infer<typeof syncTargetSchema>
export type SyncAction = z.infer<typeof syncActionSchema>
export type SyncRequest = z.infer<typeof syncRequestSchema>
export type SyncControl = z.infer<typeof syncControlSchema>

export const fetchSyncControl = () => apiGet('/api/admin/sync', syncControlSchema)
/** Accepted, not done: the worker applies it within seconds. */
export const requestSync = (target: SyncTarget, action: SyncAction) => apiPost(`/api/admin/sync/${target}/${action}`)

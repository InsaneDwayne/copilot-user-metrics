import type { JobName, SyncTarget } from '@/features/sync-status/api/syncStatus'

interface TargetInfo {
  name: string
  /** When it runs on its own. */
  schedule: string
  /** What a run does, in a few words. */
  does: string
  /** The run-log entry that tells its last run. */
  job: JobName
  /** What a run's count means; history runs count the per-month and per-day jobs they queued. */
  unit: string
  credential: string
  reads: string
}

/** The syncs an org owner can run or stop, in display order. */
export const TARGETS: Record<SyncTarget, TargetInfo> = {
  credits: {
    name: 'AI credits',
    schedule: 'Every 20 minutes',
    does: 'Recent days of AI credits per person and model',
    job: 'sync-credits',
    unit: 'rows',
    credential: 'App installation token\nAdministration: read',
    reads: 'GET /organizations/{org}/settings/\nbilling/ai_credit/usage\n?year&month&day&user={login}',
  },
  seats: {
    name: 'Seats',
    schedule: 'Hourly',
    does: 'Seat holders, last activity and seat cost',
    job: 'sync-seats',
    unit: 'rows',
    credential: 'App installation token\nGitHub Copilot Business: read\nAdministration: read',
    reads:
      'GET /orgs/{org}/copilot/billing\nGET /orgs/{org}/copilot/billing/seats\nGET /organizations/{org}/settings/\nbilling/usage/summary (seat cost)',
  },
  budgets: {
    name: 'Budgets',
    schedule: 'Hourly',
    does: 'Org and personal Copilot budgets',
    job: 'sync-budgets',
    unit: 'rows',
    credential: 'App installation token\nAdministration: read',
    reads: 'GET /organizations/{org}/settings/\nbilling/budgets[?user={login}]',
  },
  metrics: {
    name: 'Usage metrics',
    schedule: 'Daily',
    does: 'Activity: prompts, code, languages, editors, teams, pull requests',
    job: 'sync-metrics',
    unit: 'rows',
    credential: 'App installation token\nOrganization Copilot metrics: read',
    reads:
      'GET /orgs/{org}/copilot/metrics/\nreports/users-1-day?day=\nreports/user-teams-1-day?day=\nreports/organization-1-day?day=',
  },
  history: {
    name: 'History catch-up',
    schedule: 'When the worker starts',
    does: 'Every day GitHub still keeps that is missing here',
    job: 'history',
    unit: 'jobs queued',
    credential: 'App installation token',
    reads: 'All of the above, a month (credits) or a day (metrics) per job',
  },
}

export const TARGET_ORDER = Object.keys(TARGETS) as SyncTarget[]

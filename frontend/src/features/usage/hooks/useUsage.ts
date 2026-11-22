import { useQuery } from '@tanstack/react-query'
import type { DayRange } from '@/shared/utils/period'
import {
  fetchActivity,
  fetchDaily,
  fetchModelTokens,
  fetchSummary,
  subjectKey,
  type UsageSubject,
} from '@/features/usage/api/usage'

const key = (s: UsageSubject, what: string, r: DayRange) => ['usage', subjectKey(s), what, r.from, r.to]

export const useUsageSummary = (s: UsageSubject, r: DayRange) =>
  useQuery({ queryKey: key(s, 'summary', r), queryFn: () => fetchSummary(s, r) })

export const useUsageDaily = (s: UsageSubject, r: DayRange) =>
  useQuery({ queryKey: key(s, 'daily', r), queryFn: () => fetchDaily(s, r) })

export const useUsageModelTokens = (s: UsageSubject, r: DayRange) =>
  useQuery({ queryKey: key(s, 'model-tokens', r), queryFn: () => fetchModelTokens(s, r) })

export const useUsageActivity = (s: UsageSubject, r: DayRange) =>
  useQuery({ queryKey: key(s, 'activity', r), queryFn: () => fetchActivity(s, r) })

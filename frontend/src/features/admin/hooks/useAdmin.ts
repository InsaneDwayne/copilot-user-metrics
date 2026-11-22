import { keepPreviousData, useQuery } from '@tanstack/react-query'
import type { DayRange } from '@/shared/utils/period'
import {
  fetchAdoption,
  fetchMember,
  fetchMembers,
  fetchOrgDaily,
  fetchOrgModelTokens,
  fetchOrgReport,
  fetchSeats,
  fetchTeams,
  type MemberParams,
} from '@/features/admin/api/admin'

// Paged lists keep showing the previous page while the next one loads, instead of a placeholder.

export const useMembers = (r: DayRange, p: MemberParams = {}) =>
  useQuery({
    queryKey: ['admin', 'members', r.from, r.to, p],
    queryFn: () => fetchMembers(r, p),
    placeholderData: keepPreviousData,
  })
export const useTeams = (r: DayRange) =>
  useQuery({ queryKey: ['admin', 'teams', r.from, r.to], queryFn: () => fetchTeams(r) })
export const useOrgDaily = (r: DayRange) =>
  useQuery({ queryKey: ['admin', 'daily', r.from, r.to], queryFn: () => fetchOrgDaily(r) })
export const useOrgModelTokens = (r: DayRange) =>
  useQuery({ queryKey: ['admin', 'model-tokens', r.from, r.to], queryFn: () => fetchOrgModelTokens(r) })
export const useSeats = (idleDays: number, page = 1, size?: number) =>
  useQuery({
    queryKey: ['admin', 'seats', idleDays, page, size],
    queryFn: () => fetchSeats(idleDays, page, size),
    placeholderData: keepPreviousData,
  })
export const useMember = (login: string) =>
  useQuery({ queryKey: ['admin', 'member', login], queryFn: () => fetchMember(login) })
export const useAdoption = (r: DayRange, team?: string) =>
  useQuery({ queryKey: ['admin', 'adoption', r.from, r.to, team ?? null], queryFn: () => fetchAdoption(r, team) })
export const useOrgReport = (r: DayRange) =>
  useQuery({ queryKey: ['admin', 'org-report', r.from, r.to], queryFn: () => fetchOrgReport(r) })

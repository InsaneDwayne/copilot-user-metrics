import { useQuery } from '@tanstack/react-query'
import type { DayRange } from '@/shared/utils/period'
import { fetchOrgSummary } from '@/features/org-summary/api/orgSummary'

/** Org totals; `enabled: false` skips the request where a view doesn't need them. */
export function useOrgSummary(range: DayRange, { enabled = true }: { enabled?: boolean } = {}) {
  return useQuery({
    queryKey: ['org-summary', range.from, range.to],
    queryFn: () => fetchOrgSummary(range),
    enabled,
  })
}

/** Query-bound sections, shared by "My usage" and the admin member drill-down. */
import { QueryState } from '@/shared/components/QueryState'
import type { DayRange } from '@/shared/utils/period'
import type { UsageSubject } from '@/features/usage/api/usage'
import { useUsageActivity } from '@/features/usage/hooks/useUsage'
import { ActivityView } from './ActivityView'

export function ActivitySection({ subject, range }: { subject: UsageSubject; range: DayRange }) {
  return (
    <QueryState query={useUsageActivity(subject, range)} minHeight={400}>
      {(a) => <ActivityView activity={a} />}
    </QueryState>
  )
}

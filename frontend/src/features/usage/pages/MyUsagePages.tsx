import { PageHeader } from '@/shared/components/ui/PageHeader'
import { PeriodPicker } from '@/shared/components/PeriodPicker'
import { usePeriod } from '@/shared/hooks/usePeriod'
import { useAppConfig } from '@/features/app-config'
import { useSession } from '@/features/session'
import type { UsageSubject } from '@/features/usage/api/usage'
import { UsageOverview } from '@/features/usage/components/overview/UsageOverview'
import { ActivitySection } from '@/features/usage/components/activity/ActivitySection'

const ME: UsageSubject = { kind: 'me' }

function MyHeader({ title }: { title: string }) {
  const session = useSession().data
  const org = useAppConfig().data?.org
  return (
    <PageHeader
      title={title}
      subtitle={session && org ? `@${session.login} · Copilot Business seat in ${org}` : undefined}
      actions={<PeriodPicker />}
    />
  )
}

export function MyUsagePage() {
  const period = usePeriod()
  return (
    <>
      <MyHeader title="My usage" />
      <UsageOverview subject={ME} period={period} />
    </>
  )
}

export function MyActivityPage() {
  const { range } = usePeriod()
  return (
    <>
      <MyHeader title="Activity" />
      <ActivitySection subject={ME} range={range} />
    </>
  )
}

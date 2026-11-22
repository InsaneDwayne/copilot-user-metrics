import { ArrowLeftIcon, EyeIcon, UsersIcon } from '@phosphor-icons/react'
import { Link, useLocation, useParams, useSearchParams } from 'react-router'
import { Note } from '@/shared/components/ui/Card'
import { PageHeader } from '@/shared/components/ui/PageHeader'
import { PeriodPicker } from '@/shared/components/PeriodPicker'
import { QueryState } from '@/shared/components/QueryState'
import { Segmented } from '@/shared/components/ui/Segmented'
import { buttonClass } from '@/shared/components/ui/variants'
import { periodSearch, usePeriod } from '@/shared/hooks/usePeriod'
import { useUrlParam } from '@/shared/hooks/useUrlParam'
import { formatAgo, formatDate } from '@/shared/utils/format'
import { pageParam, pageSizeParam, parsePage, parsePageSize } from '@/shared/utils/pagination'
import { useAppConfig } from '@/features/app-config'
import { useOrgSummary } from '@/features/org-summary'
import { SyncJobsCard } from '@/features/sync-status'
import { ActivitySection, UsageExplorer, UsageOverview, type UsageSubject } from '@/features/usage'
import { AdoptionView } from '@/features/admin/components/adoption/AdoptionView'
import { OrgReportView } from '@/features/admin/components/adoption/OrgReportView'
import { MembersTable } from '@/features/admin/components/MembersTable'
import { OrgBudgets } from '@/features/admin/components/OrgBudgets'
import { OrgKpis } from '@/features/admin/components/OrgKpis'
import { SeatsView } from '@/features/admin/components/SeatsView'
import { TeamsTable } from '@/features/admin/components/TeamsTable'
import { TopConsumers } from '@/features/admin/components/TopConsumers'
import { idleDaysParam, parseIdleDays } from '@/features/admin/utils/seats'
import {
  useAdoption,
  useMember,
  useMembers,
  useOrgDaily,
  useOrgModelTokens,
  useOrgReport,
  useSeats,
  useTeams,
} from '@/features/admin/hooks/useAdmin'

const TOP_CONSUMERS = 5

export function AdminOverviewPage() {
  const period = usePeriod()
  const config = useAppConfig().data
  const org = useOrgSummary(period.range)
  const daily = useOrgDaily(period.range)
  const tokens = useOrgModelTokens(period.range)
  const members = useMembers(period.range, { size: TOP_CONSUMERS })
  const teams = useTeams(period.range)
  return (
    <>
      <PageHeader
        title="Organization usage"
        subtitle={config && org.data ? `${config.org} · Copilot Business · ${org.data.seats} seats` : config?.org}
        actions={<PeriodPicker />}
      />
      <div className="flex flex-col gap-4">
        <QueryState query={org} minHeight={104}>
          {(o) => (
            <>
              <OrgKpis org={o} />
              <OrgBudgets org={o} showBudgets={period.isCurrentCycle} />
            </>
          )}
        </QueryState>
        <QueryState query={daily} minHeight={360}>
          {(items) => (
            <UsageExplorer
              items={items}
              range={period.range}
              showBilling
              csvName="copilot-org-usage"
              tokens={tokens.data}
            />
          )}
        </QueryState>
        <QueryState query={members}>{(m) => <TopConsumers members={m} />}</QueryState>
        <QueryState query={teams}>{(t) => <TeamsTable teams={t} range={period.range} />}</QueryState>
      </div>
    </>
  )
}

export function AdoptionPage() {
  const period = usePeriod()
  const adoption = useAdoption(period.range)
  const report = useOrgReport(period.range)
  return (
    <>
      <PageHeader
        title="Adoption"
        subtitle="Who uses Copilot, how often and for what, from GitHub's daily usage metrics"
        actions={<PeriodPicker />}
      />
      <div className="flex flex-col gap-4">
        <QueryState query={adoption} minHeight={480}>
          {(a) => <AdoptionView adoption={a} />}
        </QueryState>
        <h3 className="mt-2 text-lead font-medium">Pull requests &amp; agents</h3>
        <QueryState query={report} minHeight={320}>
          {(r) => <OrgReportView report={r} />}
        </QueryState>
      </div>
    </>
  )
}

/** One team's adoption: its members' activity on the days GitHub listed them in the team. */
export function TeamPage() {
  const { team = '' } = useParams()
  const [params] = useSearchParams()
  const period = usePeriod()
  const adoption = useAdoption(period.range, team)
  return (
    <>
      <PageHeader
        title={team}
        subtitle="Team adoption, from GitHub's daily usage metrics and user-teams report"
        before={
          <Link
            className={buttonClass('ghost', 'sm', 'mb-1.5')}
            to={{ pathname: '/admin', search: periodSearch(params) }}
          >
            <ArrowLeftIcon />
            Organization usage
          </Link>
        }
        actions={
          <span className="flex flex-wrap items-center gap-2">
            <Link
              className={buttonClass('secondary', 'sm')}
              to={{ pathname: '/admin/members', search: periodSearch(params, { team }) }}
            >
              <UsersIcon aria-hidden />
              Members
            </Link>
            <PeriodPicker />
          </span>
        }
      />
      <div className="flex flex-col gap-4">
        <QueryState query={adoption} minHeight={480}>
          {(a) => <AdoptionView adoption={a} team={team} />}
        </QueryState>
        <Note>
          Activity counts for this team on the days GitHub listed a person in it, so moving between teams moves the
          activity with them. Seats and adoption phases are the team&apos;s current members. GitHub leaves out teams
          with fewer than 5 Copilot seats.
        </Note>
      </div>
    </>
  )
}

export function MembersPage() {
  const period = usePeriod()
  return (
    <>
      <PageHeader
        title="Members"
        subtitle="AI credits per seat in the selected period, and how much of their budget each has used this month"
        actions={<PeriodPicker />}
      />
      <MembersTable range={period.range} showBudgets={period.isCurrentCycle} />
    </>
  )
}

type Section = 'usage' | 'activity'

export function MemberDetailPage() {
  const { login = '' } = useParams()
  const { search } = useLocation()
  const period = usePeriod()
  const profile = useMember(login)
  const subject: UsageSubject = { kind: 'member', login }
  const [params, setParam] = useUrlParam()
  const section: Section = params.get('section') === 'activity' ? 'activity' : 'usage'
  const setSection = (next: Section) => setParam('section', next === 'usage' ? null : next)
  // Back to the list with its filters, but without this page's own section switch.
  const back = new URLSearchParams(search)
  back.delete('section')
  const p = profile.data
  return (
    <>
      <PageHeader
        title={`@${login}`}
        subtitle={
          p
            ? `Seat since ${formatDate(p.assigned_at)}${p.ended_at ? ` · ended ${formatDate(p.ended_at)}` : ''} · ` +
              `last active ${formatAgo(p.last_activity_at)}${p.last_activity_editor ? ` in ${p.last_activity_editor}` : ''}`
            : undefined
        }
        before={
          <Link
            className={buttonClass('ghost', 'sm', 'mb-1.5')}
            to={{ pathname: '/admin/members', search: back.toString() }}
          >
            <ArrowLeftIcon />
            All members
          </Link>
        }
        actions={<PeriodPicker />}
      />
      <QueryState query={profile}>
        {() => (
          <div className="flex flex-col gap-4">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <Segmented
                label="Section"
                value={section}
                onChange={setSection}
                options={[
                  { value: 'usage', label: 'AI credits' },
                  { value: 'activity', label: 'Activity' },
                ]}
              />
              <span className="flex items-center gap-2 text-xs text-fg-muted">
                <EyeIcon aria-hidden />
                Read-only.
              </span>
            </div>
            {section === 'usage' ? (
              <UsageOverview subject={subject} period={period} showBilling />
            ) : (
              <ActivitySection subject={subject} range={period.range} />
            )}
          </div>
        )}
      </QueryState>
    </>
  )
}

export function SeatsPage() {
  const [params, setParam] = useUrlParam()
  const idleDays = parseIdleDays(params.get('idle'))
  const seats = useSeats(idleDays, parsePage(params.get('page')), parsePageSize(params.get('size')))
  return (
    <>
      <PageHeader title="Seats" subtitle="Copilot Business seats, from the last seat sync" />
      <QueryState query={seats}>
        {(s) => (
          <SeatsView
            seats={s}
            idleDays={idleDays}
            onIdleDays={(d) => setParam('idle', idleDaysParam(d), ['page'])}
            stale={seats.isPlaceholderData}
            onPage={(n) => setParam('page', pageParam(n))}
            onSize={(n) => setParam('size', pageSizeParam(n), ['page'])}
          />
        )}
      </QueryState>
    </>
  )
}

export function SyncPage() {
  return (
    <>
      <PageHeader title="Sync" subtitle="Where the numbers on this dashboard come from, and running it on demand" />
      <SyncJobsCard />
    </>
  )
}

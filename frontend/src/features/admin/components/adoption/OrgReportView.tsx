import { Card, Note } from '@/shared/components/ui/Card'
import { KpiGrid, Tiles } from '@/shared/components/ui/Kpi'
import { formatCredits, formatDay, formatMinutes, formatPercent, share } from '@/shared/utils/format'
import type { OrgReport } from '@/features/admin/api/admin'
import { BarRow } from './BarRow'
import { PullRequestsChart } from './PullRequestsChart'

const count = (n: number | null) => (n === null ? '—' : formatCredits(n))

/** What GitHub's org-wide daily report adds: pull requests, MCP servers, custom agents and data coverage. */
export function OrgReportView({ report: r }: { report: OrgReport }) {
  if (r.days_reported === 0) {
    return (
      <Card title="No org report yet">
        <Note>
          GitHub&apos;s org-wide daily report hasn&apos;t been synced for this period yet. The usage metrics sync
          fetches it with the per-person reports; after an update, the worker&apos;s catch-up fills in the days GitHub
          still keeps.
        </Note>
      </Card>
    )
  }
  return (
    <div className="flex flex-col gap-4">
      {r.pull_requests ? (
        <PullRequests report={r} pr={r.pull_requests} />
      ) : (
        <Card title="Pull requests">
          <Note>GitHub reported no pull request numbers for this period.</Note>
        </Card>
      )}
      <div className="grid grid-cols-[repeat(auto-fit,minmax(min(100%,420px),1fr))] gap-4">
        <NamedUse
          title="MCP servers"
          subtitle="Interactions with each MCP server in the period."
          items={r.mcp_servers}
          empty="No MCP server use reported in this period."
        />
        <NamedUse
          title="Custom agents"
          subtitle="Interactions with each custom agent in the period."
          items={r.custom_agents}
          empty="No custom agent use reported in this period."
        />
        {r.coverage && <Coverage coverage={r.coverage} />}
      </div>
    </div>
  )
}

type PullRequestTotals = NonNullable<OrgReport['pull_requests']>

function PullRequests({ report: r, pr }: { report: OrgReport; pr: PullRequestTotals }) {
  return (
    <>
      <KpiGrid
        items={[
          {
            label: 'Pull requests by Copilot',
            value: `${formatCredits(pr.created_by_copilot)} of ${formatCredits(pr.created)}`,
            meta: `${formatPercent(share(pr.created_by_copilot, pr.created))} of the pull requests created`,
          },
          {
            label: 'Merged',
            value: formatCredits(pr.merged),
            meta: `${formatCredits(pr.merged_created_by_copilot)} of them created by Copilot`,
          },
          {
            label: 'Reviewed by Copilot',
            value: `${formatCredits(pr.reviewed_by_copilot)} of ${formatCredits(pr.reviewed)}`,
            meta: `${formatPercent(share(pr.reviewed_by_copilot, pr.reviewed))} of the reviewed pull requests`,
          },
          {
            label: 'Time to merge',
            value: formatMinutes(pr.minutes_to_merge),
            meta: `${formatMinutes(pr.minutes_to_merge_copilot)} for pull requests Copilot created`,
          },
          {
            label: 'Review suggestions applied',
            value: formatPercent(share(pr.applied_suggestions, pr.suggestions)),
            meta: `Copilot's: ${formatPercent(share(pr.copilot_applied_suggestions, pr.copilot_suggestions))} of ${formatCredits(pr.copilot_suggestions)}`,
          },
        ]}
      />
      <Card
        title="Pull requests created per day"
        subtitle="From GitHub's org-wide daily report; the part at the bottom of each bar is what Copilot created."
      >
        <PullRequestsChart daily={r.daily} />
        <Note>
          Time to merge averages GitHub&apos;s daily medians, weighted by how many pull requests merged each day; GitHub
          doesn&apos;t report single pull requests.
        </Note>
      </Card>
    </>
  )
}

function NamedUse({
  title,
  subtitle,
  items,
  empty,
}: {
  title: string
  subtitle: string
  items: OrgReport['mcp_servers']
  empty: string
}) {
  const max = Math.max(0, ...items.map((i) => i.count))
  return (
    <Card title={title} subtitle={subtitle}>
      {items.length === 0 && <div className="text-xs text-fg-muted">{empty}</div>}
      {items.map((i) => (
        <BarRow key={i.name} label={i.name} value={share(i.count, max) ?? 0} figure={formatCredits(i.count)} />
      ))}
    </Card>
  )
}

function Coverage({ coverage: c }: { coverage: NonNullable<OrgReport['coverage']> }) {
  return (
    <Card title="Data coverage" subtitle={`As GitHub reported it for ${formatDay(c.day)}.`}>
      <Tiles
        items={[
          { label: 'Without editor telemetry', value: count(c.missing_telemetry_users) },
          { label: 'Below the reporting minimum', value: count(c.below_minimum_users) },
        ]}
      />
      <Tiles
        items={[
          { label: 'Active that day', value: count(c.daily_active_users) },
          { label: 'In the last 7 days', value: count(c.weekly_active_users) },
          { label: 'In the last 28 days', value: count(c.monthly_active_users) },
        ]}
      />
      <Note>
        People without editor telemetry used Copilot in an editor that sent no usage data, so their editor and language
        numbers are missing on this page. The active counts are GitHub&apos;s own; the chart above counts them from the
        per-person rows, so small differences are expected.
      </Note>
    </Card>
  )
}

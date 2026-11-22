import { ArrowRightIcon } from '@phosphor-icons/react'
import { Link, useLocation } from 'react-router'
import { Card, Note } from '@/shared/components/ui/Card'
import { KpiGrid } from '@/shared/components/ui/Kpi'
import { EmptyRow, Table, Td, Th } from '@/shared/components/ui/Table'
import { buttonClass } from '@/shared/components/ui/variants'
import { formatCredits, formatDay, formatPercent, share } from '@/shared/utils/format'
import { CodeAndModelCards, PHASE_NOTE, SURFACE_LABELS, featureLabel, phaseLabel } from '@/features/usage'
import type { OrgAdoption, Segment } from '@/features/admin/api/admin'
import { SEGMENT_LABELS, SEGMENT_ORDER, membersIn } from '@/features/admin/utils/members'
import { ActiveUsersChart } from './ActiveUsersChart'
import { BarRow } from './BarRow'
import { SkillsCard } from './SkillsCard'

/** Who in the org (or one `team`) uses Copilot, how often and for what, for one period. */
export function AdoptionView({ adoption: a, team }: { adoption: OrgAdoption; team?: string }) {
  const regular = membersIn(a.segments, 'regular')
  if (a.data_through === null) {
    return (
      <Card title="No usage metrics yet">
        <Note>
          GitHub&apos;s daily Copilot usage metrics haven&apos;t been synced yet. Check the Sync page; the metrics job
          fills this page.
        </Note>
      </Card>
    )
  }
  return (
    <div className="flex flex-col gap-4">
      <KpiGrid
        items={[
          {
            label: 'Active people',
            value: `${formatCredits(a.active_users)} of ${formatCredits(a.seats)}`,
            meta: `${formatPercent(share(a.active_users, a.seats))} of seat holders used Copilot`,
          },
          {
            label: 'Regular users',
            value: formatCredits(regular),
            meta: `${formatPercent(share(regular, a.seats))} of seat holders, active 7+ days`,
          },
          {
            label: 'Average daily active',
            value: a.average_daily_active === null ? '—' : formatCredits(Math.round(a.average_daily_active)),
            meta: 'People active per day with data',
          },
          { label: 'Acceptance rate', value: formatPercent(a.acceptance_rate), meta: 'Accepted ÷ generated' },
          {
            label: 'Lines added',
            value: formatCredits(a.loc_added),
            meta: `${formatCredits(a.loc_suggested)} suggested · ${formatCredits(a.prompts)} prompts`,
          },
        ]}
      />
      <Card
        title="Active people per day"
        subtitle="Bars count the people active each day; the lines count everyone active on any of the last 7 or 28 days."
      >
        <ActiveUsersChart daily={a.daily} seats={a.seats} />
      </Card>
      <div className="grid grid-cols-[repeat(auto-fit,minmax(min(100%,420px),1fr))] gap-4">
        <SegmentsCard adoption={a} team={team} />
        <Card title="Adoption phases" subtitle="Seat holders by the phase GitHub gave them on their last reported day.">
          {a.phases.length === 0 && <div className="text-xs text-fg-muted">No seat holders in this period.</div>}
          {a.phases.map((p) => (
            <BarRow
              key={p.phase?.number ?? 'none'}
              label={phaseLabel(p.phase)}
              value={share(p.members, a.seats) ?? 0}
              figure={formatCredits(p.members)}
              fill={p.phase && p.phase.number > 0 ? undefined : 'bg-series-7'}
            />
          ))}
          <Note>{PHASE_NOTE}</Note>
        </Card>
        <Card title="Copilot surfaces" subtitle="People who used each surface at least once, of the active people.">
          {a.surfaces.map((s) => (
            <BarRow
              key={s.surface}
              label={SURFACE_LABELS[s.surface]}
              value={share(s.users, a.active_users) ?? 0}
              figure={formatCredits(s.users)}
            />
          ))}
        </Card>
        <Card title="Features" subtitle="People who used each feature, and the prompts they sent with it.">
          <Table>
            <thead>
              <tr>
                <Th>Feature</Th>
                <Th align="right">People</Th>
                <Th align="right">Prompts</Th>
              </tr>
            </thead>
            <tbody>
              {a.features.length === 0 && <EmptyRow colSpan={3}>No feature use in this period.</EmptyRow>}
              {a.features.map((f) => (
                <tr key={f.name}>
                  <Td>{featureLabel(f.name)}</Td>
                  <Td align="right" numeric>
                    {formatCredits(f.users)}
                  </Td>
                  <Td align="right" numeric tone="muted">
                    {formatCredits(f.prompts)}
                  </Td>
                </tr>
              ))}
            </tbody>
          </Table>
        </Card>
        <Card title="Languages" subtitle="The 12 languages most people wrote code in with Copilot.">
          <Table>
            <thead>
              <tr>
                <Th>Language</Th>
                <Th align="right">People</Th>
                <Th align="right">Lines added</Th>
                <Th align="right">Acceptance</Th>
              </tr>
            </thead>
            <tbody>
              {a.languages.length === 0 && <EmptyRow colSpan={4}>No code activity in this period.</EmptyRow>}
              {a.languages.map((l) => (
                <tr key={l.language}>
                  <Td>{l.language}</Td>
                  <Td align="right" numeric>
                    {formatCredits(l.users)}
                  </Td>
                  <Td align="right" numeric tone="muted">
                    {formatCredits(l.loc_added)}
                  </Td>
                  <Td align="right" numeric tone="muted">
                    {formatPercent(l.acceptance_rate)}
                  </Td>
                </tr>
              ))}
            </tbody>
          </Table>
        </Card>
        <Card title="Editors" subtitle="People who used Copilot in each editor, of the active people.">
          {a.ides.length === 0 && <div className="text-xs text-fg-muted">No editor activity in this period.</div>}
          {a.ides.map((i) => (
            <BarRow
              key={i.ide}
              label={i.ide}
              value={share(i.users, a.active_users) ?? 0}
              figure={formatCredits(i.users)}
            />
          ))}
        </Card>
      </div>
      <SkillsCard skills={a.skills} activeUsers={a.active_users} />
      <CodeAndModelCards
        codeChanges={a.code_changes}
        modelFeatures={a.model_features}
        languageModels={a.language_models}
      />
      <Note>
        From GitHub&apos;s daily Copilot usage metrics, which cover complete days only — currently through{' '}
        {formatDay(a.data_through)}. A person counts as active on a day with any prompt, generated code or Copilot
        surface used. Editor and language numbers need telemetry enabled in the editor.
      </Note>
    </div>
  )
}

/** How many seat holders used Copilot on no day, 1–6 days or 7+, each linking to those members. */
function SegmentsCard({ adoption: a, team }: { adoption: OrgAdoption; team?: string }) {
  const { search } = useLocation()
  const count = (s: Segment) => membersIn(a.segments, s)
  const membersLink = (s: Segment) => {
    const params = new URLSearchParams(search)
    params.set('segment', s)
    if (team) params.set('team', team)
    return { pathname: '/admin/members', search: params.toString() }
  }
  return (
    <Card title="How often seat holders use Copilot" subtitle="Days in the period with any Copilot activity.">
      {SEGMENT_ORDER.map((s) => (
        <BarRow
          key={s}
          label={SEGMENT_LABELS[s]}
          value={share(count(s), a.seats) ?? 0}
          figure={formatCredits(count(s))}
          fill={s === 'none' ? 'bg-series-7' : undefined}
          action={
            count(s) > 0 && (
              <Link
                className={buttonClass('ghost', 'sm')}
                to={membersLink(s)}
                aria-label={`${SEGMENT_LABELS[s]} members`}
              >
                <ArrowRightIcon />
              </Link>
            )
          }
        />
      ))}
      <Note>
        Seats with no activity still cost a seat fee; the Seats page lists who hasn&apos;t used theirs lately.
      </Note>
    </Card>
  )
}

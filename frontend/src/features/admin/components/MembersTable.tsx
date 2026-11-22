import { CaretRightIcon, MagnifyingGlassIcon, WarningCircleIcon } from '@phosphor-icons/react'
import { useState } from 'react'
import { useNavigate } from 'react-router'
import { Person } from '@/shared/components/ui/Avatar'
import { BudgetBar } from '@/shared/components/BudgetMeter'
import { DownloadButton } from '@/shared/components/DownloadButton'
import { QueryState } from '@/shared/components/QueryState'
import { Card, Note } from '@/shared/components/ui/Card'
import { Segmented } from '@/shared/components/ui/Segmented'
import { Tag } from '@/shared/components/ui/Tag'
import { Pagination } from '@/shared/components/ui/Pagination'
import { EmptyRow, Table, Td, Th } from '@/shared/components/ui/Table'
import { inputClass } from '@/shared/components/ui/variants'
import { useDebouncedValue } from '@/shared/hooks/useDebouncedValue'
import { useUrlParam } from '@/shared/hooks/useUrlParam'
import { budgetLeft } from '@/shared/utils/budget'
import { cn } from '@/shared/utils/cn'
import { formatAgo, formatCredits, formatPercent, formatUsd } from '@/shared/utils/format'
import { pageParam, pageSizeParam, parsePage, parsePageSize } from '@/shared/utils/pagination'
import type { DayRange } from '@/shared/utils/period'
import { phaseLabel } from '@/features/usage'
import { downloadMembersCsv, type MemberSort, type MemberUsage } from '@/features/admin/api/admin'
import { useMembers } from '@/features/admin/hooks/useAdmin'
import {
  SEGMENT_LABELS,
  SEGMENT_ORDER,
  budgetUsed,
  memberPath,
  membersIn,
  parseSegment,
} from '@/features/admin/utils/members'

const SORT_NOTES: Record<MemberSort, string> = {
  credits: 'most AI credits first',
  active_days: 'most active days first',
  budget: 'closest to their budget first',
}

/** A different filter, order or page size starts again on page 1. */
const RESET_PAGE = ['page']

interface MembersTableProps {
  range: DayRange
  /** GitHub budgets are this month's; for other periods the budget column says so instead. */
  showBudgets: boolean
}

/**
 * Members, filtered, ordered and paged by the API. Team, order and page live in the URL; the
 * login filter is typed here and sent once typing pauses.
 */
export function MembersTable({ range, showBudgets }: MembersTableProps) {
  const navigate = useNavigate()
  const [params, setParam] = useUrlParam()
  const [query, setQuery] = useState('')
  const login = useDebouncedValue(query.trim())
  const team = params.get('team') ?? 'all'
  const sortParam = params.get('sort')
  const sort: MemberSort =
    sortParam === 'active_days' ? sortParam : showBudgets && sortParam === 'budget' ? 'budget' : 'credits'
  const segment = parseSegment(params.get('segment'))
  const page = parsePage(params.get('page'))
  const size = parsePageSize(params.get('size'))
  const filters = { team: team === 'all' ? null : team, q: login || null, segment, sort }
  const members = useMembers(range, { ...filters, page, size })
  const setPage = (n: number) => setParam('page', pageParam(n))
  const setSize = (n: number) => setParam('size', pageSizeParam(n), RESET_PAGE)
  // Until the first page arrives, keep a team picked from a link selectable.
  const teams = members.data?.teams ?? (team === 'all' ? [] : [team])

  return (
    <Card
      title="Members with a Copilot seat"
      aside={
        <div className="flex flex-wrap items-center gap-2.5">
          <Segmented
            label="Sort by"
            size="sm"
            value={sort}
            onChange={(v) => setParam('sort', v === 'credits' ? null : v, RESET_PAGE)}
            options={[
              { value: 'credits', label: 'AI credits' },
              { value: 'active_days', label: 'Active days' },
              ...(showBudgets ? [{ value: 'budget' as const, label: 'Budget used' }] : []),
            ]}
          />
          <select
            className={cn(inputClass, 'w-48')}
            value={segment ?? 'all'}
            onChange={(e) => setParam('segment', e.target.value === 'all' ? null : e.target.value, RESET_PAGE)}
            aria-label="Activity"
          >
            <option value="all">Any activity</option>
            {SEGMENT_ORDER.map((s) => {
              const n = members.data && membersIn(members.data.segments, s)
              return (
                <option key={s} value={s}>
                  {SEGMENT_LABELS[s]}
                  {n === undefined ? '' : ` (${n})`}
                </option>
              )
            })}
          </select>
          <select
            className={cn(inputClass, 'w-42.5')}
            value={team}
            onChange={(e) => setParam('team', e.target.value === 'all' ? null : e.target.value, RESET_PAGE)}
            aria-label="Team"
          >
            <option value="all">All teams</option>
            {teams.map((t) => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </select>
          <div className="relative w-60 max-w-full">
            <MagnifyingGlassIcon className="absolute top-1/2 left-2.5 -translate-y-1/2 text-fg-subtle" />
            <input
              className={cn(inputClass, 'pl-8')}
              placeholder="Filter by login"
              value={query}
              onChange={(e) => {
                setQuery(e.target.value)
                if (page > 1) setPage(1)
              }}
              aria-label="Filter by login"
            />
          </div>
          <DownloadButton
            title="Download every member matching these filters, in this order, as CSV"
            disabled={members.data?.total === 0}
            onDownload={() => downloadMembersCsv(range, filters)}
          />
        </div>
      }
    >
      <QueryState query={members} minHeight={320}>
        {(p) => (
          <>
            <div className={cn('transition-opacity', members.isPlaceholderData && 'opacity-60')}>
              <Table minWidth={1080}>
                <thead>
                  <tr>
                    <Th>Member</Th>
                    <Th align="right">AI credits</Th>
                    <Th align="right">List value</Th>
                    <Th align="right">Share</Th>
                    <Th className="w-[24%] min-w-56">Budget (this month)</Th>
                    <Th align="right" title="Days in the period with any Copilot activity">
                      Active days
                    </Th>
                    <Th align="right">Acceptance</Th>
                    <Th>Phase</Th>
                    <Th>Top model</Th>
                    <Th>Last active</Th>
                    <Th />
                  </tr>
                </thead>
                <tbody>
                  {p.total === 0 && (
                    <EmptyRow colSpan={11}>
                      {p.members === 0 ? 'No seat holders in this period.' : 'No member matches this filter.'}
                    </EmptyRow>
                  )}
                  {p.items.map((m) => (
                    <tr
                      key={m.login}
                      className="cursor-pointer"
                      onClick={() => navigate({ pathname: memberPath(m.login), search: params.toString() })}
                    >
                      <Td>
                        <Person login={m.login} url={m.avatar_url} />
                      </Td>
                      <Td align="right" numeric>
                        {formatCredits(m.credits)}
                      </Td>
                      <Td align="right" numeric tone="muted">
                        {formatUsd(m.gross_usd)}
                      </Td>
                      <Td align="right" numeric tone="muted">
                        {formatPercent(m.share)}
                      </Td>
                      <Td>
                        {showBudgets ? <BudgetUse member={m} /> : <span className="text-xs text-fg-subtle">—</span>}
                      </Td>
                      <Td align="right" numeric tone={m.active_days ? 'default' : 'faint'}>
                        {m.active_days}
                      </Td>
                      <Td align="right" numeric tone="muted">
                        {formatPercent(m.acceptance_rate)}
                      </Td>
                      <Td>
                        {m.adoption_phase ? (
                          <Tag tone={m.adoption_phase.number > 0 ? 'accent' : 'neutral'} className="whitespace-nowrap">
                            {phaseLabel(m.adoption_phase)}
                          </Tag>
                        ) : (
                          <span className="text-xs text-fg-subtle">—</span>
                        )}
                      </Td>
                      <Td tone="meta">{m.top_model ?? '—'}</Td>
                      <Td tone="meta" title={m.last_activity_editor ?? undefined}>
                        {formatAgo(m.last_activity_at)}
                      </Td>
                      <Td align="right" tone="faint">
                        <CaretRightIcon />
                      </Td>
                    </tr>
                  ))}
                </tbody>
              </Table>
            </div>
            <Pagination page={p} onChange={setPage} onSizeChange={setSize} noun="members" />
            <Note>
              {p.total === p.members ? `${p.members} members · ` : `${p.total} of ${p.members} members match · `}
              {SORT_NOTES[sort]}. Active days count every day with a prompt, generated code or a Copilot surface used,
              from GitHub&apos;s daily metrics; phase is GitHub&apos;s AI adoption phase on the last reported day.{' '}
              {showBudgets
                ? 'Budget is this month’s spend against the GitHub budget that applies to each member: a personal one where set, otherwise the organization’s default per-member budget. Members at or over their limit are marked.'
                : 'Budgets are this month’s only; pick “This cycle” to see them.'}
            </Note>
          </>
        )}
      </QueryState>
    </Card>
  )
}

/**
 * The member's budget as on their own page: "$31.00 of $40.00 · $9.00 left" over a bar of
 * that budget, and whether it is personal or the org default. At or past the limit a
 * warning mark shows.
 */
function BudgetUse({ member: m }: { member: MemberUsage }) {
  const used = budgetUsed(m)
  const b = m.budget
  if (used === null || !b) return <span className="text-xs text-fg-subtle">No budget</span>
  const atLimit = used >= 1
  const kind = b.scope === 'user' ? 'personal' : 'default'
  const tip =
    `${formatUsd(b.consumed_usd)} of ${formatUsd(b.amount_usd)} (${formatPercent(used)}) · ${kind} budget · ` +
    (b.prevent_further_usage ? 'usage stops at the limit' : 'alerts only')
  return (
    <div className="flex flex-col gap-1.5 py-0.5" title={tip}>
      <div className="flex items-center justify-between gap-2 text-xs whitespace-nowrap tabular-nums">
        <span className={cn('inline-flex items-center gap-1', atLimit && 'font-medium text-warning')}>
          {atLimit && <WarningCircleIcon size={14} weight="fill" aria-label="At or over budget" />}
          {formatUsd(b.consumed_usd)}
          <span className="font-normal text-fg-muted">
            of {formatUsd(b.amount_usd)} · {formatUsd(budgetLeft(b))} left
          </span>
        </span>
        <span className={cn('text-2xs', kind === 'personal' ? 'font-medium text-accent' : 'text-fg-subtle')}>
          {kind}
        </span>
      </div>
      <BudgetBar used={Math.min(1, used)} label={`Budget used: ${tip}`} />
    </div>
  )
}

import { EyeIcon } from '@phosphor-icons/react'
import { DownloadButton } from '@/shared/components/DownloadButton'
import { Person } from '@/shared/components/ui/Avatar'
import { Card, Note } from '@/shared/components/ui/Card'
import { KpiGrid } from '@/shared/components/ui/Kpi'
import { Pagination } from '@/shared/components/ui/Pagination'
import { Segmented } from '@/shared/components/ui/Segmented'
import { EmptyRow, Table, Td, Th } from '@/shared/components/ui/Table'
import { Tag } from '@/shared/components/ui/Tag'
import { cn } from '@/shared/utils/cn'
import { formatDate, formatDay, formatPercent, formatUsd } from '@/shared/utils/format'
import {
  IDLE_THRESHOLDS,
  downloadIdleSeatsCsv,
  type IdleSeat,
  type IdleThreshold,
  type SeatOverview,
} from '@/features/admin/api/admin'

interface SeatsViewProps {
  seats: SeatOverview
  idleDays: IdleThreshold
  onIdleDays: (days: IdleThreshold) => void
  onPage: (page: number) => void
  onSize: (size: number) => void
  /** The previous page is shown while the next one loads. */
  stale?: boolean
}

export function SeatsView({ seats, idleDays, onIdleDays, onPage, onSize, stale }: SeatsViewProps) {
  const idle = seats.idle
  const price = seats.seat_cost?.price_per_seat_usd
  const days = seats.idle_after_days
  return (
    <div className="flex flex-col gap-4">
      <KpiGrid
        items={[
          {
            label: 'Assigned',
            value: String(seats.assigned),
            meta:
              price === undefined
                ? 'Seat charges not listed by GitHub yet'
                : `${formatUsd(seats.assigned * price)} a month (${seats.assigned} × ${formatUsd(price)})`,
          },
          {
            label: `Active · last ${days} days`,
            value: String(seats.active),
            meta: `${formatPercent(seats.assigned ? seats.active / seats.assigned : null)} of seats`,
          },
          {
            label: `Idle ${days}+ days`,
            value: String(seats.inactive + seats.never_used),
            meta: `${seats.never_used} never used · ${seats.inactive} quiet since`,
          },
          {
            label: 'Reclaimable a month',
            value: seats.reclaimable_usd === null ? '—' : formatUsd(seats.reclaimable_usd),
            meta:
              `${seats.reclaimable} idle ${seats.reclaimable === 1 ? 'seat' : 'seats'}` +
              (seats.pending_cancellation ? ` · ${seats.pending_cancellation} already being removed` : ''),
          },
        ]}
      />
      <Card
        title={`No activity in the last ${days} days`}
        subtitle="Seats that were used but have been quiet since, and seats assigned that long ago and never used. Each still costs a seat fee."
        aside={
          <div className="flex flex-wrap items-center gap-2.5">
            <Segmented
              label="Idle after"
              size="sm"
              value={String(idleDays)}
              onChange={(v) => onIdleDays(Number(v) as IdleThreshold)}
              options={IDLE_THRESHOLDS.map((d) => ({ value: String(d), label: `${d} days` }))}
            />
            <DownloadButton
              title={`Download every seat idle for ${days}+ days as CSV`}
              disabled={idle.total === 0}
              onDownload={() => downloadIdleSeatsCsv(idleDays)}
            />
          </div>
        }
      >
        <Table minWidth={720} className={cn('transition-opacity', stale && 'opacity-60')}>
          <thead>
            <tr>
              <Th>Member</Th>
              <Th>Team</Th>
              <Th>Seat assigned</Th>
              <Th>Last activity</Th>
              <Th>Status</Th>
            </tr>
          </thead>
          <tbody>
            {idle.total === 0 && <EmptyRow colSpan={5}>Every seat was used in the last {days} days.</EmptyRow>}
            {idle.items.map((s) => (
              <tr key={s.login}>
                <Td>
                  <Person login={s.login} url={s.avatar_url} />
                </Td>
                <Td tone="meta">{s.teams.join(', ') || '—'}</Td>
                <Td tone="meta">{formatDate(s.assigned_at)}</Td>
                <Td tone="meta">{s.last_activity_at ? formatDate(s.last_activity_at) : 'Never'}</Td>
                <Td>
                  <SeatStatusTags seat={s} />
                </Td>
              </tr>
            ))}
          </tbody>
        </Table>
        <Pagination page={idle} onChange={onPage} onSizeChange={onSize} noun="seats" />
        <Note>
          <span className="inline-flex items-center gap-1.5">
            <EyeIcon aria-hidden />
            Read-only: seats are removed in GitHub.
          </span>{' '}
          Seats GitHub is already removing are listed last and left out of the reclaimable cost.
          {seats.recently_assigned > 0 &&
            ` ${seats.recently_assigned} ${seats.recently_assigned === 1 ? 'seat was' : 'seats were'} assigned in the last ${days} days and ${seats.recently_assigned === 1 ? "isn't" : "aren't"} used yet; ${seats.recently_assigned === 1 ? "it isn't" : "they aren't"} counted as idle.`}
        </Note>
      </Card>
    </div>
  )
}

function SeatStatusTags({ seat: s }: { seat: IdleSeat }) {
  return (
    <span className="flex flex-wrap gap-1.5">
      {s.status === 'never_used' ? <Tag tone="outline">Never used</Tag> : <Tag>Inactive {s.inactive_days} days</Tag>}
      {s.pending_cancellation_date && <Tag tone="accent">Removed {formatDay(s.pending_cancellation_date)}</Tag>}
    </span>
  )
}

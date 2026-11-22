import { ArrowClockwiseIcon, CircleNotchIcon, StopIcon } from '@phosphor-icons/react'
import { useState } from 'react'
import { Card, Note } from '@/shared/components/ui/Card'
import { Tiles } from '@/shared/components/ui/Kpi'
import { QueryState } from '@/shared/components/QueryState'
import { Button } from '@/shared/components/ui/Button'
import { ConfirmDialog } from '@/shared/components/ui/Dialog'
import { Table, Td, Th } from '@/shared/components/ui/Table'
import { Tag } from '@/shared/components/ui/Tag'
import { formatAgo, formatDate } from '@/shared/utils/format'
import type { JobStatus, SyncAction, SyncControl, SyncRequest, SyncTarget } from '@/features/sync-status/api/syncStatus'
import { useRequestSync, useSyncControl } from '@/features/sync-status/hooks/useSyncControl'
import { useSyncStatus } from '@/features/sync-status/hooks/useSyncStatus'
import { TARGETS, TARGET_ORDER } from '@/features/sync-status/utils/jobs'

const code = 'font-mono text-xs leading-relaxed whitespace-pre-wrap'

/** Health, queue and run/stop controls for every sync, in one table (org owners). */
export function SyncJobsCard() {
  const status = useSyncStatus()
  const control = useSyncControl()
  return (
    <QueryState query={status}>
      {(s) => {
        const failing = s.jobs.filter((j) => j.last_status === 'failed')
        const lastError = failing[0]?.last_error
        const attention = s.stale || failing.length > 0
        const jobOf = new Map(s.jobs.map((j) => [j.job, j]))
        return (
          <Card
            title="Sync service"
            subtitle="Pulls usage from GitHub with a read-only GitHub App and stores it for this dashboard. Run a sync now, or stop one that is queued or running."
            aside={<Tag tone={attention ? 'outline' : 'neutral'}>{attention ? 'Needs attention' : 'Healthy'}</Tag>}
          >
            <Tiles
              items={[
                {
                  label: 'Last success (AI credits)',
                  value: s.last_success_at
                    ? `${formatDate(s.last_success_at)} · ${formatAgo(s.last_success_at)}`
                    : 'Never',
                },
                { label: 'Failing syncs', value: String(failing.length) },
                { label: 'Last error', value: lastError ? lastError.slice(0, 80) : '—' },
              ]}
            />
            <Table minWidth={760}>
              <thead>
                <tr>
                  <Th>Sync</Th>
                  <Th>Last run</Th>
                  <Th>Queue</Th>
                  <Th align="right">
                    <span className="sr-only">Actions</span>
                  </Th>
                </tr>
              </thead>
              <tbody>
                {TARGET_ORDER.map((target) => (
                  <TargetRow key={target} target={target} job={jobOf.get(TARGETS[target].job)} control={control.data} />
                ))}
              </tbody>
            </Table>
            {control.isError && (
              <div className="text-xs text-error">Couldn’t load the job queue: {control.error.message}</div>
            )}
            {control.data && <RecentRequests requests={control.data.requests} />}
            <details className="text-sm">
              <summary className="cursor-pointer text-fg-muted hover:text-fg">What each sync reads from GitHub</summary>
              <Table minWidth={640} className="mt-2">
                <thead>
                  <tr>
                    <Th>Sync</Th>
                    <Th>Credential</Th>
                    <Th>Reads</Th>
                  </tr>
                </thead>
                <tbody>
                  {TARGET_ORDER.map((t) => (
                    <tr key={t}>
                      <Td>{TARGETS[t].name}</Td>
                      <Td className={`${code} text-fg-soft`}>{TARGETS[t].credential}</Td>
                      <Td className={`${code} text-fg-muted`}>{TARGETS[t].reads}</Td>
                    </tr>
                  ))}
                </tbody>
              </Table>
            </details>
            <Note>
              The worker picks up a request within seconds. A run waits for the job in progress (one job at a time), and
              regular syncs go ahead of the history catch-up. Stopping cancels what is queued and interrupts what is
              running; the next scheduled run starts as usual. Activity metrics arrive once a day for complete days.
            </Note>
          </Card>
        )
      }}
    </QueryState>
  )
}

function TargetRow({
  target,
  job,
  control,
}: {
  target: SyncTarget
  job: JobStatus | undefined
  control: SyncControl | undefined
}) {
  const info = TARGETS[target]
  const queue = control?.targets.find((t) => t.target === target)
  const pending = control?.requests.filter((r) => r.target === target && r.handled_at === null) ?? []
  const request = useRequestSync()
  const busy = (queue?.running ?? 0) > 0 || (queue?.queued ?? 0) > 0
  // The action waiting for the admin's confirmation in the modal, if any.
  const [confirming, setConfirming] = useState<SyncAction | null>(null)
  const send = (action: SyncAction) => {
    request.mutate({ target, action }, { onSettled: () => setConfirming(null) })
  }
  const ask = (action: SyncAction) => (needsConfirmation(target, action) ? setConfirming(action) : send(action))
  const prompt = confirming ? confirmation(target, confirming, queue) : null
  const waiting = (action: SyncAction) =>
    pending.some((r) => r.action === action) || (request.isPending && request.variables?.action === action)
  return (
    <tr>
      <Td>
        <div>{info.name}</div>
        <div className="text-xs text-fg-muted">
          {info.schedule} · {info.does}
        </div>
      </Td>
      <Td tone="meta">
        {job ? (
          <span className="inline-flex flex-wrap items-center gap-2" title={job.last_error ?? undefined}>
            {formatAgo(job.last_started_at)} · {job.last_rows} {info.unit}
            <StatusTag job={job} />
          </span>
        ) : (
          '—'
        )}
      </Td>
      <Td tone="meta">
        {queue ? (
          queue.running > 0 ? (
            <span className="inline-flex items-center gap-1.5 text-fg">
              <CircleNotchIcon className="animate-spin" aria-hidden />
              Running{queue.queued > 0 ? ` · ${queue.queued} queued` : ''}
            </span>
          ) : queue.queued > 0 ? (
            `${queue.queued} queued`
          ) : (
            'Idle'
          )
        ) : (
          '—'
        )}
      </Td>
      <Td align="right">
        <span className="inline-flex gap-1.5">
          <Button size="sm" className="text-xs" disabled={!control || waiting('run')} onClick={() => ask('run')}>
            <ArrowClockwiseIcon aria-hidden />
            {waiting('run') ? 'Requested…' : 'Run now'}
          </Button>
          <Button
            size="sm"
            className="text-xs"
            disabled={!control || !busy || waiting('stop')}
            onClick={() => ask('stop')}
            title={busy ? undefined : 'Nothing queued or running'}
          >
            <StopIcon aria-hidden />
            {waiting('stop') ? 'Stopping…' : 'Stop'}
          </Button>
        </span>
        {request.isError && <div className="mt-1 text-xs text-error">{request.error.message}</div>}
        {prompt && confirming && (
          <ConfirmDialog
            open
            title={prompt.title}
            description={prompt.description}
            confirmLabel={prompt.confirm}
            busyLabel="Sending…"
            busy={request.isPending}
            onConfirm={() => send(confirming)}
            onCancel={() => setConfirming(null)}
          />
        )}
      </Td>
    </tr>
  )
}

/** Stopping always asks (it drops and interrupts work); running asks only for the long history load. */
const needsConfirmation = (target: SyncTarget, action: SyncAction) => action === 'stop' || target === 'history'

function confirmation(
  target: SyncTarget,
  action: SyncAction,
  queue: { queued: number; running: number } | undefined,
): { title: string; description: string; confirm: string } {
  const name = TARGETS[target].name
  if (action === 'run')
    return {
      title: `Run the ${name.toLowerCase()} now?`,
      description:
        'Queues every day GitHub still keeps that is missing here. On a first load this can be months of history; regular syncs keep running in between.',
      confirm: 'Start catch-up',
    }
  const parts = [
    queue?.running ? `interrupts the run in progress` : null,
    queue?.queued ? `drops ${queue.queued} queued job${queue.queued === 1 ? '' : 's'}` : null,
  ].filter(Boolean)
  return {
    title: `Stop ${name}?`,
    description:
      `This ${parts.join(' and ') || 'stops anything queued or running'}. ` +
      (target === 'history'
        ? 'Dropped days are picked up again on the next catch-up.'
        : 'The next scheduled run starts as usual.'),
    confirm: 'Stop sync',
  }
}

function StatusTag({ job }: { job: JobStatus }) {
  if (job.last_status === 'failed')
    return (
      <Tag tone="outline">
        Failing · {job.failures_since_success} run{job.failures_since_success === 1 ? '' : 's'}
      </Tag>
    )
  if (job.last_status === 'running') return <Tag tone="accent">Running</Tag>
  if (job.last_status === 'aborted') return <Tag>Stopped</Tag>
  return <Tag>OK</Tag>
}

/** Who asked for what, and what the worker made of it. */
function RecentRequests({ requests }: { requests: SyncRequest[] }) {
  if (requests.length === 0) return null
  return (
    <div className="flex flex-col gap-1.5">
      <div className="text-2xs tracking-[0.08em] text-fg/60 uppercase">Recent requests</div>
      <ul className="flex flex-col gap-1 text-xs">
        {requests.slice(0, 6).map((r) => (
          <li key={r.id} className="flex flex-wrap gap-x-2 text-fg-muted">
            <span className="text-fg">
              {r.action === 'run' ? 'Run' : 'Stop'} · {TARGETS[r.target].name}
            </span>
            <span>
              @{r.admin_login} · {formatAgo(r.requested_at)}
            </span>
            <span className={r.outcome?.startsWith('Failed') ? 'text-error' : undefined}>
              → {r.handled_at ? r.outcome : 'waiting for the worker…'}
            </span>
          </li>
        ))}
      </ul>
    </div>
  )
}

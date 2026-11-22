import { cn } from '@/shared/utils/cn'
import { formatAgo } from '@/shared/utils/format'
import { useSyncStatus } from '@/features/sync-status/hooks/useSyncStatus'

export function SyncIndicator() {
  const { data } = useSyncStatus()
  if (!data) return null
  return (
    <span
      className="flex items-center gap-1.5 text-xs text-fg-muted"
      title="Data comes from the sync service, not live from GitHub"
    >
      <span className={cn('size-1.75 rounded-full', data.stale ? 'bg-warning' : 'bg-fg-subtle')} />
      {data.last_success_at ? `Synced ${formatAgo(data.last_success_at)}` : 'Not synced yet'}
    </span>
  )
}

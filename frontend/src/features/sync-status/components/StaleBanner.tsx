import { ClockCountdownIcon } from '@phosphor-icons/react'
import { Link } from 'react-router'
import { Banner } from '@/shared/components/ui/Banner'
import { buttonClass } from '@/shared/components/ui/variants'
import { formatAgo } from '@/shared/utils/format'
import { useSyncStatus } from '@/features/sync-status/hooks/useSyncStatus'

export function StaleBanner({ showSyncLink }: { showSyncLink: boolean }) {
  const { data } = useSyncStatus()
  if (!data?.stale) return null
  return (
    <Banner>
      <ClockCountdownIcon size={18} className="text-warning" />
      <span className="min-w-55 flex-1">
        {data.last_success_at
          ? `Last successful sync was ${formatAgo(data.last_success_at)}. Numbers below may be behind GitHub.`
          : 'No successful sync yet. Numbers appear once the sync service has run.'}
      </span>
      {showSyncLink && (
        <Link className={buttonClass('primary', 'sm')} to="/admin/sync">
          View sync status
        </Link>
      )}
    </Banner>
  )
}

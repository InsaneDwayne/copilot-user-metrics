import { EyeIcon, ShieldCheckIcon, UserIcon } from '@phosphor-icons/react'
import { Link, Outlet, useLocation } from 'react-router'
import { Brand } from '@/shared/components/Brand'
import { Tabs, type TabItem } from '@/shared/components/Tabs'
import { ThemeToggle } from '@/shared/components/ThemeToggle'
import { Tag } from '@/shared/components/ui/Tag'
import { buttonClass } from '@/shared/components/ui/variants'
import { useAppConfig } from '@/features/app-config'
import { UserMenu, useSession } from '@/features/session'
import { StaleBanner, SyncIndicator } from '@/features/sync-status'

const ME_TABS: TabItem[] = [
  { to: '/me', label: 'Usage', end: true },
  { to: '/me/activity', label: 'Activity' },
]

const ADMIN_TABS: TabItem[] = [
  { to: '/admin', label: 'Overview', end: true },
  { to: '/admin/adoption', label: 'Adoption' },
  { to: '/admin/members', label: 'Members' },
  { to: '/admin/seats', label: 'Seats' },
]

/** Organization readers see the same console without the Sync page. */
const SYNC_TAB: TabItem = { to: '/admin/sync', label: 'Sync' }

export function AppLayout() {
  const { pathname } = useLocation()
  const session = useSession().data
  const org = useAppConfig().data?.org
  const inAdmin = pathname.startsWith('/admin')
  const access = session?.access
  const canManageSync = Boolean(access?.can_manage_sync)

  return (
    // Fluid up to one cap: the cards and charts inside reflow to the width; past ~1440px the
    // page stops growing, so rows and charts stay readable on wide monitors.
    <div className="mx-auto w-full max-w-page px-4 pb-16 sm:px-6 lg:px-8">
      <header className="flex min-h-15 flex-wrap items-center gap-x-3 gap-y-2 py-2">
        <Brand />
        {org && <Tag className="hidden sm:inline-flex">{org}</Tag>}
        {inAdmin && (
          <Tag tone="outline">
            {canManageSync ? <ShieldCheckIcon /> : <EyeIcon />}
            {canManageSync ? 'Admin' : 'Organization reader'}
          </Tag>
        )}
        <div className="ml-auto flex items-center gap-1.5 sm:gap-2.5">
          <span className="hidden md:flex">
            <SyncIndicator />
          </span>
          {!inAdmin && access?.can_view_admin && (
            <Link className={buttonClass('secondary')} to="/admin" aria-label="Admin console" title="Admin console">
              <ShieldCheckIcon />
              <span className="hidden sm:inline">Admin console</span>
            </Link>
          )}
          {inAdmin && access?.can_view_own_usage && (
            <Link className={buttonClass('secondary')} to="/me" aria-label="My usage" title="My usage">
              <UserIcon />
              <span className="hidden sm:inline">My usage</span>
            </Link>
          )}
          <ThemeToggle />
          <UserMenu />
        </div>
      </header>
      <Tabs items={inAdmin ? (canManageSync ? [...ADMIN_TABS, SYNC_TAB] : ADMIN_TABS) : ME_TABS} />
      <StaleBanner showSyncLink={canManageSync} />
      <Outlet />
    </div>
  )
}

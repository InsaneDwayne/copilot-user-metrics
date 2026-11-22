import { ArrowsLeftRightIcon, DotOutlineIcon, LockSimpleIcon } from '@phosphor-icons/react'
import { Navigate } from 'react-router'
import { Button } from '@/shared/components/ui/Button'
import { Surface } from '@/shared/components/ui/Surface'
import { useAppConfig } from '@/features/app-config'
import { CenteredLayout } from '@/features/session/components/CenteredLayout'
import { homePath } from '@/features/session/utils/homePath'
import { useSession } from '@/features/session/hooks/useSession'
import { useSignOut } from '@/features/session/hooks/useSignOut'

export function NoAccessPage() {
  const { data: session, isPending } = useSession()
  const org = useAppConfig().data?.org ?? 'the organization'
  const signOut = useSignOut()
  if (isPending) return null
  if (!session) return <Navigate to="/signin" replace />
  if (homePath(session) !== '/no-access') return <Navigate to={homePath(session)} replace />

  const outsider = session.role === 'outsider'
  const reasons = [
    'You’re signed in with a personal account, not your work account',
    !outsider && 'Your seat was assigned recently — it appears after the next sync (within the hour)',
    'You don’t have a seat — ask an org owner',
  ].filter(Boolean)
  return (
    <CenteredLayout className="max-w-135">
      <Surface className="gap-4.5 p-6 sm:p-8">
        <span className="grid size-10 place-items-center rounded-md text-xl text-fg-muted inset-ring inset-ring-line-strong">
          <LockSimpleIcon />
        </span>
        <h1 className="text-title text-pretty">No Copilot usage on record for @{session.login}</h1>
        <p className="text-pretty text-fg-muted">
          {outsider
            ? `You're signed in, but this account isn't an active member of ${org}.`
            : `You're signed in, but the last sync didn't find a Copilot seat in ${org} for this account.`}{' '}
          Usually this means one of:
        </p>
        <ul className="flex flex-col gap-2 text-base">
          {reasons.map((reason) => (
            <li key={String(reason)} className="flex items-center gap-2.5">
              <DotOutlineIcon className="flex-none text-accent" />
              {reason}
            </li>
          ))}
        </ul>
        <div className="flex flex-wrap items-center gap-2.5 pt-1.5">
          <Button variant="primary" onClick={() => signOut.mutate()}>
            <ArrowsLeftRightIcon />
            Use a different GitHub account
          </Button>
        </div>
      </Surface>
    </CenteredLayout>
  )
}

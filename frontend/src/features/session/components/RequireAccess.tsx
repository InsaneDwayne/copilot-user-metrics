import type { ReactNode } from 'react'
import { Navigate, useLocation } from 'react-router'
import { Placeholder } from '@/shared/components/ui/Placeholder'
import { useSession } from '@/features/session/hooks/useSession'
import type { Session } from '@/features/session/api/session'

/** own-usage: /me; admin: the admin console (admins and organization readers); sync: its Sync page (admins only). */
type Need = 'own-usage' | 'admin' | 'sync'

function allowed(session: Session, need: Need): boolean {
  if (need === 'sync') return session.access.can_manage_sync
  if (need === 'admin') return session.access.can_view_admin
  return session.access.can_view_own_usage || session.access.can_view_admin
}

/**
 * Route guard for the UI. It only decides what to *show* — the API enforces
 * the same rules (and Postgres row-level security backs the API).
 */
export function RequireAccess({ need, children }: { need: Need; children: ReactNode }) {
  const session = useSession()
  const location = useLocation()
  if (session.isPending) return <Placeholder>Loading…</Placeholder>
  if (session.isError) return <Placeholder error>Couldn’t reach the server: {session.error.message}</Placeholder>
  if (!session.data) return <Navigate to="/signin" replace state={{ from: location }} />
  if (!allowed(session.data, need)) return <Navigate to={need === 'own-usage' ? '/no-access' : '/'} replace />
  return <>{children}</>
}

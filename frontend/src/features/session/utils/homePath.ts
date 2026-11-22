import type { Session } from '@/features/session/api/session'

/** Where "/" should land for this person. */
export function homePath(session: Session | null): string {
  if (!session) return '/signin'
  if (session.access.can_view_own_usage) return '/me'
  if (session.access.can_view_admin) return '/admin'
  return '/no-access'
}

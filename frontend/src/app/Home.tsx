import { Navigate, useLocation } from 'react-router'
import { homePath, useSession } from '@/features/session'
import { Placeholder } from '@/shared/components/ui/Placeholder'

/** "/" — the OAuth callback lands here; send each person to what they may open. */
export function Home() {
  const session = useSession()
  const { search } = useLocation()
  if (session.isPending) return null
  if (session.isError) return <Placeholder error>Couldn’t reach the server: {session.error.message}</Placeholder>
  return <Navigate to={`${homePath(session.data)}${search}`} replace />
}

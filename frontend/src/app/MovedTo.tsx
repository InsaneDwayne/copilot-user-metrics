import { Navigate, useLocation } from 'react-router'

/** Pages that were folded into another keep working as links, period and all. */
export function MovedTo({ to }: { to: string }) {
  const { search } = useLocation()
  return <Navigate to={{ pathname: to, search }} replace />
}

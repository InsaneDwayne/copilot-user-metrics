import { useQuery } from '@tanstack/react-query'
import { sessionQueryKey } from '@/shared/api/queryClient'
import { fetchSession } from '@/features/session/api/session'

export function useSession() {
  return useQuery({ queryKey: sessionQueryKey, queryFn: fetchSession, staleTime: 5 * 60_000 })
}

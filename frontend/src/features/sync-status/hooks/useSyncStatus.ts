import { useQuery } from '@tanstack/react-query'
import { fetchSyncStatus } from '@/features/sync-status/api/syncStatus'

export const syncStatusKey = ['sync-status']

export function useSyncStatus() {
  return useQuery({ queryKey: syncStatusKey, queryFn: fetchSyncStatus, refetchInterval: 5 * 60_000 })
}

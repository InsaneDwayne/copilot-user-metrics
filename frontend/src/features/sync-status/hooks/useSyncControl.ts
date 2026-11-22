import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  fetchSyncControl,
  requestSync,
  type SyncAction,
  type SyncControl,
  type SyncTarget,
} from '@/features/sync-status/api/syncStatus'
import { syncStatusKey } from '@/features/sync-status/hooks/useSyncStatus'

const key = ['admin', 'sync-control']

/** Something is waiting for the worker or in progress: worth watching closely. */
const isBusy = (c: SyncControl | undefined) =>
  !!c && (c.requests.some((r) => r.handled_at === null) || c.targets.some((t) => t.running > 0 || t.queued > 0))

/** Queue state and recent requests; polls every few seconds while anything is in flight. */
export function useSyncControl() {
  return useQuery({
    queryKey: key,
    queryFn: fetchSyncControl,
    refetchInterval: (q) => (isBusy(q.state.data) ? 3_000 : 30_000),
  })
}

export function useRequestSync() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: ({ target, action }: { target: SyncTarget; action: SyncAction }) => requestSync(target, action),
    onSettled: async () => {
      await client.invalidateQueries({ queryKey: key })
      await client.invalidateQueries({ queryKey: syncStatusKey })
    },
  })
}

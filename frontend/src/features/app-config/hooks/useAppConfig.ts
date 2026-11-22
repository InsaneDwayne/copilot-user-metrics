import { useQuery } from '@tanstack/react-query'
import { fetchAppConfig } from '@/features/app-config/api/config'

/** Public, non-secret server settings (org name, session length). Fetched once. */
export function useAppConfig() {
  return useQuery({ queryKey: ['app-config'], queryFn: fetchAppConfig, staleTime: Infinity })
}

import { QueryCache, QueryClient } from '@tanstack/react-query'
import { ApiError, isUnauthorized } from './client'

export const sessionQueryKey = ['session'] as const

export function createQueryClient(): QueryClient {
  const client: QueryClient = new QueryClient({
    queryCache: new QueryCache({
      // An expired session anywhere sends the app back to sign-in.
      onError: (error) => {
        if (isUnauthorized(error)) client.setQueryData(sessionQueryKey, null)
      },
    }),
    defaultOptions: {
      queries: {
        staleTime: 60_000,
        refetchOnWindowFocus: false,
        // HTTP errors are answers, not glitches: only retry network failures.
        retry: (count, error) => !(error instanceof ApiError) && count < 2,
      },
    },
  })
  return client
}

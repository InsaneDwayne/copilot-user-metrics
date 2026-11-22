import type { UseQueryResult } from '@tanstack/react-query'
import type { ReactNode } from 'react'
import { Placeholder } from '@/shared/components/ui/Placeholder'

interface QueryStateProps<T> {
  query: UseQueryResult<T>
  children: (data: T) => ReactNode
  /** Height of the placeholder while loading, to avoid layout jumps. */
  minHeight?: number
}

/** Renders loading and error states uniformly; children only see loaded data. */
export function QueryState<T>({ query, children, minHeight = 120 }: QueryStateProps<T>) {
  if (query.isPending) return <Placeholder minHeight={minHeight}>Loading…</Placeholder>
  if (query.isError)
    return (
      <Placeholder error minHeight={minHeight}>
        Couldn’t load this: {query.error.message}
      </Placeholder>
    )
  return <>{children(query.data)}</>
}

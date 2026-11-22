import type { ReactNode } from 'react'
import { cn } from '@/shared/utils/cn'

/** Loading and error stand-ins that keep the space a section will take. */
export function Placeholder({
  error,
  minHeight = 120,
  children,
}: {
  error?: boolean
  minHeight?: number
  children: ReactNode
}) {
  return (
    <div
      className={cn('grid place-items-center text-sm', error ? 'text-error' : 'text-fg-subtle')}
      style={{ minHeight }}
    >
      {children}
    </div>
  )
}

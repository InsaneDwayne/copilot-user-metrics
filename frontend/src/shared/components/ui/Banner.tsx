import type { ReactNode } from 'react'
import { cn } from '@/shared/utils/cn'

export function Banner({
  role = 'status',
  className,
  children,
}: {
  role?: 'status' | 'alert'
  className?: string
  children: ReactNode
}) {
  return (
    <div
      role={role}
      className={cn(
        'mb-5 flex flex-wrap items-center gap-3 rounded-md bg-notice px-4 py-3 text-sm text-on-notice',
        'inset-ring inset-ring-notice-line',
        className,
      )}
    >
      {children}
    </div>
  )
}

import type { ReactNode } from 'react'
import { cn } from '@/shared/utils/cn'

/** The raised card box every panel is drawn on. */
export function Surface({
  as: As = 'div',
  className,
  children,
}: {
  as?: 'div' | 'section'
  className?: string
  children: ReactNode
}) {
  return (
    <As className={cn('flex flex-col gap-3.5 rounded-md bg-surface p-5 shadow-hairline', className)}>{children}</As>
  )
}

/** Small uppercase label above a value or a block. */
export function Kicker({ children }: { children: ReactNode }) {
  return <div className="text-micro tracking-widest text-accent uppercase">{children}</div>
}

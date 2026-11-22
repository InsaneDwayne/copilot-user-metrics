import type { ReactNode } from 'react'
import { cn } from '@/shared/utils/cn'

interface PickableRowProps {
  /** The chart series this row picks out; null for a row with nothing in the chart (not pickable). */
  pickKey: string | null
  focus: string | null
  onFocus: (key: string | null) => void
  children: ReactNode
}

/**
 * A models-table row that picks its model out in the chart above (click, Enter or Space;
 * again to let go). While another row is picked, it fades back.
 */
export function PickableRow({ pickKey, focus, onFocus, children }: PickableRowProps) {
  const on = pickKey !== null && focus === pickKey
  const pick = pickKey === null ? undefined : () => onFocus(on ? null : pickKey)
  return (
    <tr
      tabIndex={pick ? 0 : undefined}
      aria-selected={pick ? on : undefined}
      onClick={pick}
      onKeyDown={(e) => {
        if (!pick || (e.key !== 'Enter' && e.key !== ' ')) return
        e.preventDefault()
        pick()
      }}
      className={cn(
        pick &&
          'cursor-pointer outline-offset-[-2px] transition-opacity focus-visible:outline-2 focus-visible:outline-accent',
        on && 'bg-accent/8',
        focus && !on && 'opacity-45',
      )}
    >
      {children}
    </tr>
  )
}

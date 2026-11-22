import type { ReactNode } from 'react'

export function Legend({ children }: { children: ReactNode }) {
  return <div className="flex flex-wrap gap-4 text-xs text-fg-muted">{children}</div>
}

/** One legend entry: a key (swatch or line sample) and its label. */
export function LegendItem({ mark, children }: { mark: ReactNode; children: ReactNode }) {
  return (
    <span className="flex items-center gap-1.5">
      {mark}
      {children}
    </span>
  )
}

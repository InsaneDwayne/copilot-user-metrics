import type { ReactNode } from 'react'
import { Surface } from './Surface'

interface CardProps {
  title?: ReactNode
  subtitle?: ReactNode
  aside?: ReactNode
  children?: ReactNode
}

export function Card({ title, subtitle, aside, children }: CardProps) {
  return (
    <Surface as="section">
      {(title || aside) && (
        <div className="flex flex-wrap items-baseline justify-between gap-3">
          <div className="max-w-160">
            {title && <div className="text-lg leading-tight font-medium">{title}</div>}
            {subtitle && <Subtitle>{subtitle}</Subtitle>}
          </div>
          {aside}
        </div>
      )}
      {children}
    </Surface>
  )
}

export function Subtitle({ children }: { children: ReactNode }) {
  return <div className="mt-1 text-sm text-pretty text-fg-muted">{children}</div>
}

/** Fine print under a section. */
export function Note({ children }: { children: ReactNode }) {
  return <div className="text-xs text-pretty text-fg-subtle">{children}</div>
}

import type { ReactNode } from 'react'
import { tagClass, type Tone } from './variants'

export function Tag({
  tone = 'neutral',
  className,
  children,
}: {
  tone?: Tone
  className?: string
  children: ReactNode
}) {
  return <span className={tagClass(tone, className)}>{children}</span>
}

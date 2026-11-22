import type { ReactNode } from 'react'
import { Subtitle } from './Card'

interface PageHeaderProps {
  title: ReactNode
  subtitle?: ReactNode
  before?: ReactNode
  actions?: ReactNode
}

export function PageHeader({ title, subtitle, before, actions }: PageHeaderProps) {
  return (
    <div className="mb-5 flex flex-wrap items-end justify-between gap-4">
      <div>
        {before}
        <h2 className="text-2xl">{title}</h2>
        {subtitle && <Subtitle>{subtitle}</Subtitle>}
      </div>
      {actions}
    </div>
  )
}

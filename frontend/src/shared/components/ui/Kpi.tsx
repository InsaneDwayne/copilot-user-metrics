import type { ReactNode } from 'react'
import { Kicker, Surface } from './Surface'

export interface KpiItem {
  label: string
  value: ReactNode
  meta?: ReactNode
}

export function KpiGrid({ items }: { items: KpiItem[] }) {
  return (
    <div className="grid grid-cols-[repeat(auto-fit,minmax(min(100%,150px),1fr))] gap-3">
      {items.map((k) => (
        <Surface key={k.label} className="gap-1.5 p-4">
          <Kicker>{k.label}</Kicker>
          <div className="text-2xl font-medium tracking-[-0.02em] tabular-nums">{k.value}</div>
          {k.meta && <div className="flex items-center gap-1.5 text-2xs text-fg/50">{k.meta}</div>}
        </Surface>
      ))}
    </div>
  )
}

export function Tiles({ items }: { items: KpiItem[] }) {
  return (
    <div className="grid grid-cols-[repeat(auto-fit,minmax(150px,1fr))] gap-3">
      {items.map((t) => (
        <div key={t.label} className="flex flex-col gap-1 rounded-md p-3 inset-ring inset-ring-line">
          <span className="text-xs text-fg-muted">{t.label}</span>
          <span className="text-lead tabular-nums">{t.value}</span>
        </div>
      ))}
    </div>
  )
}

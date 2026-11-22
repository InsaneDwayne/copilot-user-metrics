import type { ReactNode } from 'react'
import { ShareBar } from '@/shared/components/ui/ShareBar'

/** One labelled share bar with its figure, and an optional action at the end. */
export function BarRow({
  label,
  value,
  figure,
  fill,
  action,
}: {
  label: string
  /** 0..1 of the bar's width. */
  value: number
  figure: string
  fill?: string
  action?: ReactNode
}) {
  return (
    <div className="grid grid-cols-[150px_minmax(0,1fr)_56px_32px] items-center gap-3 text-sm">
      <span className="truncate" title={label}>
        {label}
      </span>
      <ShareBar value={value} fill={fill} label={`${label}: ${figure}`} />
      <span className="text-right text-fg-muted tabular-nums">{figure}</span>
      <span className="flex justify-end">{action}</span>
    </div>
  )
}

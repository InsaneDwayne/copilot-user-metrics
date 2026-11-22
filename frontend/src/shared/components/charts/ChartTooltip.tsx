import type { ReactNode } from 'react'

interface ChartTooltipProps {
  /** Anchor in the chart box, in px. */
  x: number
  y: number
  /** Width of the chart box; in its right 40% the tooltip flips to the left of the anchor. */
  boxWidth: number
  title: ReactNode
  children: ReactNode
}

/** The hover/focus readout. Purely visual - the chart's live region announces the same values. */
export function ChartTooltip({ x, y, boxWidth, title, children }: ChartTooltipProps) {
  const flip = x > boxWidth * 0.6
  return (
    <div
      aria-hidden
      className="pointer-events-none absolute z-10 flex min-w-40 flex-col gap-1.5 rounded-md bg-surface px-3 py-2 text-xs whitespace-nowrap shadow-raised"
      style={{ left: x, top: y, transform: flip ? 'translateX(calc(-100% - 14px))' : 'translateX(14px)' }}
    >
      <div className="text-fg-muted">{title}</div>
      {children}
    </div>
  )
}

/** One value in the tooltip: a line key, the value (strong), then what it is. */
export function TooltipRow({ mark, value, label }: { mark?: ReactNode; value: ReactNode; label: ReactNode }) {
  return (
    <div className="flex items-center gap-2">
      {mark ?? <span className="w-3" />}
      <span className="font-medium text-fg tabular-nums">{value}</span>
      <span className="text-fg-muted">{label}</span>
    </div>
  )
}

/** A short stroke in the series colour (a line key, not a box). */
export function LineKey({ className, dashed }: { className: string; dashed?: boolean }) {
  return <span className={`w-3 flex-none ${dashed ? 'border-t-2 border-dashed' : 'h-0.5'} ${className}`} />
}

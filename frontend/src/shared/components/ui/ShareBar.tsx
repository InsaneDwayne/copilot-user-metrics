import { cn } from '@/shared/utils/cn'

interface ShareBarProps {
  /** 0..1 of the track */
  value: number
  /** Background class for the fill, e.g. `bg-series-2`; `bg-meter` by default. */
  fill?: string
  thick?: boolean
  label?: string
}

const pct = (ratio: number) => `${Math.max(0, Math.min(1, ratio)) * 100}%`

export function ShareBar({ value, fill, thick, label }: ShareBarProps) {
  return (
    <div
      className={cn('relative rounded-full bg-meter-track', thick ? 'h-2.5 inset-ring inset-ring-line' : 'h-1.5')}
      role="meter"
      aria-label={label}
      aria-valuemin={0}
      aria-valuemax={1}
      aria-valuenow={value}
    >
      <div className={cn('absolute inset-y-0 left-0 rounded-[inherit] bg-meter', fill)} style={{ width: pct(value) }} />
    </div>
  )
}

/** A bar with its figure on the right, as in the member and model tables. */
export function LabelledBar({
  value,
  figure,
  fill,
  label,
  figureWidth = 56,
}: {
  value: number
  figure: string
  fill?: string
  label?: string
  figureWidth?: number
}) {
  return (
    <div className="flex items-center gap-2.5">
      <div className="flex-1">
        <ShareBar value={value} fill={fill} label={label} />
      </div>
      <span className="text-right text-xs tabular-nums" style={{ width: figureWidth }}>
        {figure}
      </span>
    </div>
  )
}

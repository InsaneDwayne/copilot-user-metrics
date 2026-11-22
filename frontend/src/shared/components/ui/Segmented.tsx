import { useId, type ReactNode } from 'react'
import { cn } from '@/shared/utils/cn'

interface SegmentedProps<T extends string> {
  label: string
  value: T
  options: { value: T; label: ReactNode }[]
  onChange: (value: T) => void
  size?: 'sm' | 'md'
}

/**
 * A small radio group drawn as a track of pills (period picker, chart/table switch).
 * Each option is rounded on its own, so the selected one's accent ring is whole at
 * every corner instead of being clipped by the track's rounded edge.
 *
 * Each instance gets its own radio-group name: radios that share a name form one group across
 * the whole page, so two controls with the same label would uncheck each other.
 */
export function Segmented<T extends string>({ label, value, options, onChange, size = 'md' }: SegmentedProps<T>) {
  const name = useId()
  return (
    <div
      className="inline-flex gap-0.5 rounded-md border border-divider bg-surface p-0.5"
      role="radiogroup"
      aria-label={label}
    >
      {options.map((o) => (
        <label
          key={o.value}
          className={cn(
            'inline-flex cursor-pointer items-center gap-1.5 rounded-[6px] text-fg-muted transition-colors',
            size === 'sm' ? 'px-2.5 py-0.75 text-xs' : 'px-3 py-1.25 text-sm',
            'has-checked:bg-accent/12 has-checked:text-accent has-checked:inset-ring has-checked:inset-ring-accent',
            'not-has-checked:hover:bg-fg/7 not-has-checked:hover:text-fg',
            'has-focus-visible:outline-2 has-focus-visible:outline-offset-1 has-focus-visible:outline-accent',
          )}
        >
          <input
            type="radio"
            name={name}
            className="sr-only"
            checked={value === o.value}
            onChange={() => onChange(o.value)}
          />
          {o.label}
        </label>
      ))}
    </div>
  )
}

import { usePeriod } from '@/shared/hooks/usePeriod'
import { cn } from '@/shared/utils/cn'
import type { PeriodPreset } from '@/shared/utils/period'
import { Segmented } from '@/shared/components/ui/Segmented'
import { inputClass } from '@/shared/components/ui/variants'

const OPTIONS: { value: PeriodPreset; label: string }[] = [
  { value: 'cycle', label: 'This cycle' },
  { value: 'last', label: 'Last cycle' },
  { value: 'custom', label: 'Custom' },
]

const dateInput = cn(inputClass, 'min-h-8 w-37.5 text-sm')

export function PeriodPicker() {
  const period = usePeriod()
  return (
    <div className="flex flex-col items-end gap-2">
      <Segmented label="Period" value={period.preset} options={OPTIONS} onChange={period.setPreset} />
      {period.preset === 'custom' && (
        <div className="flex items-center gap-2.5 text-xs text-fg-muted">
          <input
            className={dateInput}
            type="date"
            aria-label="From"
            value={period.range.from}
            max={period.range.to}
            onChange={(e) => period.setCustom({ from: e.target.value })}
          />
          <span>to</span>
          <input
            className={dateInput}
            type="date"
            aria-label="To"
            value={period.range.to}
            min={period.range.from}
            onChange={(e) => period.setCustom({ to: e.target.value })}
          />
        </div>
      )}
      <div className="text-xs text-fg-subtle">{period.label}</div>
    </div>
  )
}

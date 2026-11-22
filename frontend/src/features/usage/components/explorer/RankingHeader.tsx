import { Button } from '@/shared/components/ui/Button'

interface RankingHeaderProps {
  hint: string
  focus: string | null
  onFocus: (key: string | null) => void
}

/** Heading of a models ranking under the usage chart, with "Show all" while a model is picked. */
export function RankingHeader({ hint, focus, onFocus }: RankingHeaderProps) {
  return (
    <div className="flex min-h-7 flex-wrap items-center justify-between gap-2">
      <div>
        <span className="text-md font-medium">Models this period</span>
        <span className="ml-2 text-xs text-fg-muted">{hint}</span>
      </div>
      {focus && (
        <Button variant="ghost" size="sm" className="text-xs" onClick={() => onFocus(null)}>
          Show all
        </Button>
      )}
    </div>
  )
}

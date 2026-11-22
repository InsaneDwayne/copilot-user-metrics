import { CaretLeftIcon, CaretRightIcon } from '@phosphor-icons/react'
import { cn } from '@/shared/utils/cn'
import { PAGE_SIZES, pageRange, type PageInfo } from '@/shared/utils/pagination'
import { Button } from './Button'
import { inputClass } from './variants'

interface PaginationProps {
  page: PageInfo
  onChange: (page: number) => void
  /** Offers the rows-per-page choices when given. */
  onSizeChange?: (size: number) => void
  /** What the rows are, for "1–25 of 312 members". */
  noun?: string
}

/**
 * Previous / next and rows per page under a server-paged table. Renders nothing while the
 * list fits on the smallest page, so short lists stay uncluttered.
 */
export function Pagination({ page: p, onChange, onSizeChange, noun }: PaginationProps) {
  if (p.total <= PAGE_SIZES[0]) return null
  const { from, to } = pageRange(p)
  return (
    <nav aria-label="Pagination" className="flex flex-wrap items-center justify-between gap-2 text-xs text-fg-muted">
      <span className="tabular-nums">
        {from}–{to} of {p.total}
        {noun && ` ${noun}`}
      </span>
      <div className="flex flex-wrap items-center gap-1.5">
        {onSizeChange && (
          <label className="mr-2 flex items-center gap-1.5">
            Rows per page
            <select
              className={cn(inputClass, 'min-h-0 w-auto py-1 text-xs')}
              value={p.size}
              onChange={(e) => onSizeChange(Number(e.target.value))}
            >
              {PAGE_SIZES.map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
          </label>
        )}
        <Button size="sm" disabled={p.page <= 1} onClick={() => onChange(p.page - 1)} aria-label="Previous page">
          <CaretLeftIcon />
          Previous
        </Button>
        <span className="px-1.5 tabular-nums" aria-current="page">
          Page {p.page} of {p.pages}
        </span>
        <Button size="sm" disabled={p.page >= p.pages} onClick={() => onChange(p.page + 1)} aria-label="Next page">
          Next
          <CaretRightIcon />
        </Button>
      </div>
    </nav>
  )
}

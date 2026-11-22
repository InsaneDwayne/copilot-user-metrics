import { NavLink, useSearchParams } from 'react-router'
import { periodSearch } from '@/shared/hooks/usePeriod'
import { cn } from '@/shared/utils/cn'

export interface TabItem {
  to: string
  label: string
  end?: boolean
}

/**
 * Route tabs that keep the selected period when switching. Everything else in the URL (a
 * table's team filter, order or page, a chart's view) belongs to the page it was set on.
 */
export function Tabs({ items }: { items: TabItem[] }) {
  const [params] = useSearchParams()
  const search = periodSearch(params)
  return (
    <nav className="mb-7 flex gap-6 overflow-x-auto rule-fade-end" aria-label="Sections">
      {items.map((t) => (
        <NavLink
          key={t.to}
          to={{ pathname: t.to, search }}
          end={t.end}
          className={({ isActive }) =>
            cn(
              'border-b-2 py-2.5 text-base whitespace-nowrap no-underline hover:text-fg',
              isActive ? 'border-accent text-fg' : 'border-transparent text-fg-muted',
            )
          }
        >
          {t.label}
        </NavLink>
      ))}
    </nav>
  )
}

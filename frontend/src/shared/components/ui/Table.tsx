/**
 * Data tables. Row rules fade out at both ends (rule-fade utilities, see
 * shared/styles/index.css); body rows tint on hover.
 */
import type { ReactNode, TdHTMLAttributes, ThHTMLAttributes } from 'react'
import { cn } from '@/shared/utils/cn'

interface TableProps {
  /** Below this width the table scrolls horizontally instead of squeezing. */
  minWidth?: number
  className?: string
  children: ReactNode
}

export function Table({ minWidth, className, children }: TableProps) {
  const table = (
    <table
      className={cn(
        'w-full border-collapse text-base',
        '[&_tbody_tr]:rule-fade-faint [&_tbody_tr:hover]:bg-fg/4 [&_thead_tr]:rule-fade',
        className,
      )}
      style={minWidth ? { minWidth } : undefined}
    >
      {children}
    </table>
  )
  return minWidth ? <div className="overflow-x-auto">{table}</div> : table
}

type Align = 'left' | 'right'

export function Th({
  align = 'left',
  className,
  ...props
}: ThHTMLAttributes<HTMLTableCellElement> & { align?: Align }) {
  return (
    <th
      className={cn(
        'p-1.5 text-2xs font-normal tracking-[0.08em] text-fg/60 uppercase',
        align === 'right' ? 'text-right' : 'text-left',
        className,
      )}
      {...props}
    />
  )
}

interface TdProps extends TdHTMLAttributes<HTMLTableCellElement> {
  align?: Align
  /** Tabular figures, for columns of numbers. */
  numeric?: boolean
  /** muted: secondary text; faint: tertiary text; small muted text is the default for metadata columns. */
  tone?: 'default' | 'muted' | 'faint' | 'meta'
}

const TD_TONES = {
  default: '',
  muted: 'text-fg-muted',
  faint: 'text-fg-subtle',
  meta: 'text-xs text-fg-muted',
}

export function Td({ align = 'left', numeric, tone = 'default', className, ...props }: TdProps) {
  return (
    <td
      className={cn('p-1.5', align === 'right' && 'text-right', numeric && 'tabular-nums', TD_TONES[tone], className)}
      {...props}
    />
  )
}

export function EmptyRow({ colSpan, children }: { colSpan: number; children: ReactNode }) {
  return (
    <tr>
      <Td colSpan={colSpan} tone="muted">
        {children}
      </Td>
    </tr>
  )
}

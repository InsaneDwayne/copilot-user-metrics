import { cumsum } from 'd3-array'
import { useState } from 'react'
import { Button } from '@/shared/components/ui/Button'
import { Swatch } from '@/shared/components/ui/Swatch'
import { EmptyRow, Table, Td, Th } from '@/shared/components/ui/Table'
import { seriesBg } from '@/shared/theme/tokens'
import { formatUsd } from '@/shared/utils/format'
import type { Measure } from '@/shared/utils/measures'
import { bucketLabel } from '@/features/usage/utils/bucketLabels'
import type { Bucket, Granularity, ModelSeries } from '@/features/usage/utils/usageSeries'

const PAGE = 31

interface UsageTableProps {
  buckets: Bucket[]
  granularity: Granularity
  series: ModelSeries[]
  /** Picking a model's header shows it alone; picking it again shows every model. */
  focus: string | null
  onFocus: (key: string | null) => void
  showBilling: boolean
  /** What the cells count. */
  measure: Measure
}

/** The chart as numbers: one row per day, week or month (newest first), one column per model. */
export function UsageTable({ buckets, granularity, series, focus, onFocus, showBilling, measure }: UsageTableProps) {
  const [shown, setShown] = useState(PAGE)
  const known = buckets.filter((b) => b.known)
  const runningTotals = cumsum(known, (b) => b.credits)
  const rows = known.map((b, i) => ({ bucket: b, running: runningTotals[i] })).reverse()
  const total = {
    credits: runningTotals.at(-1) ?? 0,
    gross: known.reduce((sum, b) => sum + b.gross_usd, 0),
    billed: known.reduce((sum, b) => sum + b.billed_usd, 0),
  }
  const cols = 3 + series.length + (showBilling ? 2 : 0)
  return (
    <div className="flex flex-col gap-2">
      <Table minWidth={360 + series.length * 110 + (showBilling ? 200 : 0)}>
        <thead>
          <tr>
            <Th>{granularity === 'day' ? 'Date' : granularity === 'week' ? 'Week' : 'Month'}</Th>
            <Th align="right">{measure.title}</Th>
            <Th align="right">Running total</Th>
            {series.map((s) => (
              <Th key={s.key} align="right" className="normal-case">
                <button
                  type="button"
                  aria-pressed={focus === s.key}
                  title={focus === s.key ? 'Show every model' : `Show ${s.label} alone`}
                  onClick={() => onFocus(focus === s.key ? null : s.key)}
                  className="-mx-1 inline-flex max-w-36 items-center gap-1.5 rounded-sm px-1 py-0.5 hover:bg-fg/7 hover:text-fg"
                >
                  <Swatch className={seriesBg(s.index)} />
                  <span className="truncate">{s.label}</span>
                </button>
              </Th>
            ))}
            {showBilling && (
              <>
                <Th align="right">List value</Th>
                <Th align="right">Billed</Th>
              </>
            )}
          </tr>
        </thead>
        <tbody>
          {rows.length === 0 && <EmptyRow colSpan={cols}>No usage in this period.</EmptyRow>}
          {rows.slice(0, shown).map(({ bucket: b, running }) => {
            const bySeries = new Map(b.segments.map((s) => [s.key, s.credits]))
            return (
              <tr key={b.start}>
                <Td tone="meta" className="whitespace-nowrap">
                  {bucketLabel(b, granularity)}
                </Td>
                <Td align="right" numeric>
                  {measure.format(b.credits)}
                </Td>
                <Td align="right" numeric tone="muted">
                  {measure.format(running)}
                </Td>
                {series.map((s) => (
                  <Td key={s.key} align="right" numeric tone={bySeries.has(s.key) ? 'default' : 'faint'}>
                    {bySeries.has(s.key) ? measure.format(bySeries.get(s.key) ?? 0) : '—'}
                  </Td>
                ))}
                {showBilling && (
                  <>
                    <Td align="right" numeric tone="muted">
                      {formatUsd(b.gross_usd)}
                    </Td>
                    <Td align="right" numeric tone={b.billed_usd > 0 ? 'default' : 'faint'}>
                      {formatUsd(b.billed_usd)}
                    </Td>
                  </>
                )}
              </tr>
            )
          })}
        </tbody>
        {rows.length > 0 && (
          <tfoot>
            <tr className="font-medium">
              <Td>Total</Td>
              <Td align="right" numeric>
                {measure.format(total.credits)}
              </Td>
              <Td />
              {series.map((s) => (
                <Td key={s.key} align="right" numeric>
                  {measure.format(s.credits)}
                </Td>
              ))}
              {showBilling && (
                <>
                  <Td align="right" numeric>
                    {formatUsd(total.gross)}
                  </Td>
                  <Td align="right" numeric>
                    {formatUsd(total.billed)}
                  </Td>
                </>
              )}
            </tr>
          </tfoot>
        )}
      </Table>
      {shown < rows.length && (
        <div className="text-xs text-fg-subtle">
          Showing {shown} of {rows.length} rows ·{' '}
          <Button variant="ghost" size="sm" className="text-xs" onClick={() => setShown(shown + PAGE)}>
            Show more
          </Button>
        </div>
      )}
    </div>
  )
}

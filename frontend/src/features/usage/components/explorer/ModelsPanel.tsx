import { LabelledBar } from '@/shared/components/ui/ShareBar'
import { Swatch } from '@/shared/components/ui/Swatch'
import { Table, Td, Th } from '@/shared/components/ui/Table'
import { seriesBg } from '@/shared/theme/tokens'
import { formatCredits, formatPercent, formatUsd } from '@/shared/utils/format'
import type { ModelRank, ModelSeries } from '@/features/usage/utils/usageSeries'
import { PickableRow } from './PickableRow'
import { RankingHeader } from './RankingHeader'

interface ModelsPanelProps {
  ranking: ModelRank[]
  series: ModelSeries[]
  /** The chart series picked out (a model's own, or "Other"). */
  focus: string | null
  onFocus: (key: string | null) => void
  /** Admins and organization readers also see what GitHub billed per model. */
  showBilling: boolean
}

/**
 * The period's models ranked by AI credits, every model on its own row. The swatch ties
 * each row to its colour in the chart; picking a row picks its model out in the chart.
 */
export function ModelsPanel({ ranking, series, focus, onFocus, showBilling }: ModelsPanelProps) {
  if (ranking.length === 0) return null
  const indexOf = new Map(series.map((s) => [s.key, s.index]))
  return (
    <div className="flex flex-col gap-2 border-t border-line pt-4">
      <RankingHeader
        hint="Ranked by AI credits · pick a row to highlight it · 1 credit = $0.01 list value"
        focus={focus}
        onFocus={onFocus}
      />
      {/* On phones only rank, model, credits and share fit; the money and days columns join from sm up. */}
      <Table>
        <thead>
          <tr>
            <Th className="w-8">#</Th>
            <Th>Model</Th>
            <Th align="right">AI credits</Th>
            <Th className="w-[28%] min-w-24">Share</Th>
            <Th align="right" className="hidden sm:table-cell">
              List value
            </Th>
            {showBilling && (
              <Th align="right" className="hidden sm:table-cell">
                Billed
              </Th>
            )}
            <Th align="right" className="hidden sm:table-cell">
              Days used
            </Th>
          </tr>
        </thead>
        <tbody>
          {ranking.map((m, i) => {
            const color = seriesBg(indexOf.get(m.seriesKey) ?? 0)
            return (
              <PickableRow key={m.model} pickKey={m.seriesKey} focus={focus} onFocus={onFocus}>
                <Td tone="faint" numeric>
                  {i + 1}
                </Td>
                <Td>
                  <span className="inline-flex min-w-0 items-center gap-2.5">
                    <Swatch className={color} />
                    <span className="break-words">{m.model}</span>
                  </span>
                </Td>
                <Td align="right" numeric>
                  {formatCredits(m.credits)}
                </Td>
                <Td>
                  <LabelledBar value={m.share} fill={color} figure={formatPercent(m.share)} figureWidth={36} />
                </Td>
                <Td align="right" numeric tone="muted" className="hidden sm:table-cell">
                  {formatUsd(m.gross_usd)}
                </Td>
                {showBilling && (
                  <Td
                    align="right"
                    numeric
                    tone={m.billed_usd > 0 ? 'default' : 'faint'}
                    className="hidden sm:table-cell"
                  >
                    {formatUsd(m.billed_usd)}
                  </Td>
                )}
                <Td align="right" numeric tone="muted" className="hidden sm:table-cell">
                  {m.days}
                </Td>
              </PickableRow>
            )
          })}
        </tbody>
      </Table>
    </div>
  )
}

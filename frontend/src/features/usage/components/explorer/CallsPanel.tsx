import { LabelledBar } from '@/shared/components/ui/ShareBar'
import { Swatch } from '@/shared/components/ui/Swatch'
import { Table, Td, Th } from '@/shared/components/ui/Table'
import { seriesBg } from '@/shared/theme/tokens'
import { formatCompact, formatPercent } from '@/shared/utils/format'
import { totalTokens, type CallsMetric, type CallsRank, type ModelSeries } from '@/features/usage/utils/usageSeries'
import { PickableRow } from './PickableRow'
import { RankingHeader } from './RankingHeader'

interface CallsPanelProps {
  ranking: CallsRank[]
  series: ModelSeries[]
  metric: CallsMetric
  focus: string | null
  onFocus: (key: string | null) => void
}

const integer = new Intl.NumberFormat()

/**
 * The period's models ranked by tokens or requests (GitHub's usage metrics), every model on
 * its own row: how much a model was used, whatever it costs. A row picks its model out in the chart.
 */
export function CallsPanel({ ranking, series, metric, focus, onFocus }: CallsPanelProps) {
  if (ranking.length === 0) return null
  const indexOf = new Map(series.map((s) => [s.key, s.index]))
  const byTokens = metric === 'tokens'
  const tokensCell = (m: CallsRank) => (
    <span title={`${integer.format(m.prompt_tokens)} prompt · ${integer.format(m.output_tokens)} output tokens`}>
      {formatCompact(totalTokens(m))}
    </span>
  )
  return (
    <div className="flex flex-col gap-2 border-t border-line pt-4">
      <RankingHeader
        hint={`Ranked by ${metric} · pick a row to highlight it · prompt and output tokens, no cached tokens`}
        focus={focus}
        onFocus={onFocus}
      />
      {/* On phones only rank, model, the ranked figure and share fit; the rest joins from sm up. */}
      <Table>
        <thead>
          <tr>
            <Th className="w-8">#</Th>
            <Th>Model</Th>
            <Th align="right">{byTokens ? 'Tokens' : 'Requests'}</Th>
            <Th className="w-[28%] min-w-24">Share</Th>
            <Th align="right" className="hidden sm:table-cell">
              {byTokens ? 'Requests' : 'Tokens'}
            </Th>
            <Th align="right" className="hidden sm:table-cell">
              Tokens per request
            </Th>
            <Th align="right" className="hidden sm:table-cell">
              Days used
            </Th>
          </tr>
        </thead>
        <tbody>
          {ranking.map((m, i) => {
            const color = seriesBg(indexOf.get(m.seriesKey) ?? 0)
            const requests = integer.format(m.requests)
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
                  {byTokens ? tokensCell(m) : requests}
                </Td>
                <Td>
                  <LabelledBar value={m.share} fill={color} figure={formatPercent(m.share)} figureWidth={36} />
                </Td>
                <Td align="right" numeric tone="muted" className="hidden sm:table-cell">
                  {byTokens ? requests : tokensCell(m)}
                </Td>
                <Td align="right" numeric tone="muted" className="hidden sm:table-cell">
                  {m.requests ? formatCompact(totalTokens(m) / m.requests) : '—'}
                </Td>
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

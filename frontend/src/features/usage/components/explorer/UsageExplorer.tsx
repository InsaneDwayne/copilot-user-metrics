import { ChartBarIcon, DownloadSimpleIcon, TableIcon } from '@phosphor-icons/react'
import { useMemo, useState } from 'react'
import { CumulativeChart } from '@/shared/components/charts/CumulativeChart'
import { Card } from '@/shared/components/ui/Card'
import { Button } from '@/shared/components/ui/Button'
import { Segmented } from '@/shared/components/ui/Segmented'
import { useUrlParam } from '@/shared/hooks/useUrlParam'
import { saveFile } from '@/shared/utils/csv'
import { todayUtc } from '@/shared/utils/dates'
import { CREDITS, REQUESTS, TOKENS, type Measure } from '@/shared/utils/measures'
import type { DayRange } from '@/shared/utils/period'
import type { DailyModelUsage, ModelTokens } from '@/features/usage/api/usage'
import {
  alignedSeries,
  buckets,
  callsItems,
  callsRanking,
  defaultGranularity,
  itemsOf,
  modelRanking,
  modelSeries,
  runningTotal,
  spansMonths,
  toCallsCsv,
  toCsv,
  type CallsMetric,
  type Granularity,
} from '@/features/usage/utils/usageSeries'
import { CallsPanel } from './CallsPanel'
import { ModelsPanel } from './ModelsPanel'
import { StackedBarsChart } from './StackedBarsChart'
import { UsageTable } from './UsageTable'

/** How the period is cut: per day, week or month, or one running total. */
type Aggregation = Granularity | 'total'
type View = 'chart' | 'table'
/** What the explorer counts: AI credits (billing) or model calls (usage metrics). */
type Metric = 'credits' | CallsMetric

const MEASURES: Record<Metric, Measure> = { credits: CREDITS, tokens: TOKENS, requests: REQUESTS }

const title = (m: Measure, agg: Aggregation) =>
  agg === 'total' ? `${m.title}, running total` : `${m.title} per ${agg}`

interface UsageExplorerProps {
  items: DailyModelUsage[]
  range: DayRange
  /** Org owners also see list value vs. billed (tooltips, models, table, CSV). */
  showBilling: boolean
  /** Base name for the CSV download, e.g. "my-copilot-usage". */
  csvName: string
  /** Requests and tokens per day and model from the usage metrics; the measure switch appears once loaded. */
  tokens?: ModelTokens[]
}

/**
 * The one place to read usage over time: when credits went (or how much each model was
 * used, in tokens or requests), and on which models. Measure, aggregation and chart/table
 * live in the URL, so a shared link opens the same view.
 */
export function UsageExplorer({ items: creditItems, range, showBilling, csvName, tokens }: UsageExplorerProps) {
  const [params, setParam] = useUrlParam()

  const months = spansMonths(range)
  const fallback = defaultGranularity(range)
  const rawAgg = params.get('agg')
  const agg: Aggregation =
    rawAgg === 'day' || rawAgg === 'week' || rawAgg === 'total' || (rawAgg === 'month' && months) ? rawAgg : fallback
  const view: View = params.get('view') === 'table' ? 'table' : 'chart'
  const granularity: Granularity = agg === 'total' ? 'day' : agg
  const rawMetric = params.get('metric')
  const metric: Metric = tokens && (rawMetric === 'tokens' || rawMetric === 'requests') ? rawMetric : 'credits'
  const credits = metric === 'credits'
  const measure = MEASURES[metric]
  // Projections and money only make sense for spend.
  const billing = showBilling && credits
  const project = credits

  const [focus, setFocus] = useState<string | null>(null)
  const today = todayUtc()
  // The credit series set every model's colour; tokens and requests keep them (alignedSeries).
  const palette = useMemo(() => modelSeries(creditItems), [creditItems])
  const creditRanking = useMemo(() => modelRanking(creditItems, palette), [creditItems, palette])
  const billingNames = useMemo(() => creditRanking.map((r) => r.model), [creditRanking])
  const items = useMemo(
    () => (credits ? creditItems : callsItems(tokens ?? [], metric, billingNames)),
    [credits, creditItems, tokens, metric, billingNames],
  )
  const series = useMemo(() => (credits ? palette : alignedSeries(items, palette)), [credits, items, palette])
  const callsRank = useMemo(
    () => (credits ? [] : callsRanking(tokens ?? [], metric, billingNames, series)),
    [credits, tokens, metric, billingNames, series],
  )
  const focused = focus && series.some((s) => s.key === focus) ? focus : null
  const focusedItems = useMemo(() => itemsOf(items, series, focused), [items, series, focused])

  // The chart keeps every model stacked (the focus only fades the others); the table and
  // the running total show just the focused model.
  const chartBuckets = useMemo(
    () => buckets(items, range, series, granularity, today, { project }),
    [items, range, series, granularity, today, project],
  )
  const tableSeries = useMemo(() => (focused ? series.filter((s) => s.key === focused) : series), [series, focused])
  const tableBuckets = useMemo(
    () => buckets(focusedItems, range, tableSeries, granularity, today, { project }),
    [focusedItems, range, tableSeries, granularity, today, project],
  )
  const total = useMemo(
    () => runningTotal(focusedItems, range, today, { project }),
    [focusedItems, range, today, project],
  )

  const aggOptions: { value: Aggregation; label: string }[] = [
    { value: 'day', label: 'Daily' },
    { value: 'week', label: 'Weekly' },
    ...(months ? [{ value: 'month' as const, label: 'Monthly' }] : []),
    { value: 'total', label: 'Cumulative' },
  ]
  const source = credits ? '' : ' From GitHub’s usage metrics: complete days only.'
  const empty = credits
    ? 'No AI credits used in this period.'
    : 'No model calls in GitHub’s usage metrics for this period yet.'
  const csv = () =>
    credits
      ? saveFile(`${csvName}-${range.from}_${range.to}.csv`, toCsv(creditItems, showBilling))
      : saveFile(`${csvName}-model-calls-${range.from}_${range.to}.csv`, toCallsCsv(tokens ?? []))

  return (
    <Card
      title={title(measure, agg)}
      subtitle={
        focused ? (
          <>
            Showing {series.find((s) => s.key === focused)?.label} only.{' '}
            <Button variant="ghost" size="sm" className="text-sm" onClick={() => setFocus(null)}>
              Show all models
            </Button>
          </>
        ) : view === 'table' ? (
          `One column per model. Pick a model’s column header to see it alone.${source}`
        ) : agg === 'total' ? (
          `Running total${project ? ', with a projection to the end of the period' : ''}. Pick a model below to see its total alone.${source}`
        ) : (
          `Split by model. Pick a model in the table below to highlight it.${source}`
        )
      }
      aside={
        <div className="flex flex-wrap items-center gap-2">
          {tokens && (
            <Segmented
              label="Measure"
              size="sm"
              value={metric}
              options={[
                { value: 'credits', label: 'AI credits' },
                { value: 'tokens', label: 'Tokens' },
                { value: 'requests', label: 'Requests' },
              ]}
              onChange={(v) => setParam('metric', v === 'credits' ? null : v)}
            />
          )}
          <Segmented
            label="Aggregation"
            size="sm"
            value={agg}
            options={aggOptions}
            onChange={(v) => setParam('agg', v === fallback ? null : v)}
          />
          <Segmented
            label="Show as"
            size="sm"
            value={view}
            onChange={(v) => setParam('view', v === 'chart' ? null : v)}
            options={[
              {
                value: 'chart',
                label: (
                  <>
                    <ChartBarIcon aria-hidden />
                    Chart
                  </>
                ),
              },
              {
                value: 'table',
                label: (
                  <>
                    <TableIcon aria-hidden />
                    Table
                  </>
                ),
              },
            ]}
          />
          <Button
            variant="secondary"
            size="sm"
            className="text-xs"
            disabled={items.length === 0}
            title={
              credits
                ? 'Download every day and model in this period as CSV'
                : 'Download every day and model’s requests and tokens in this period as CSV'
            }
            onClick={csv}
          >
            <DownloadSimpleIcon aria-hidden />
            CSV
          </Button>
        </div>
      }
    >
      {view === 'table' ? (
        // The table has a column per model, so it takes the full width and its headers pick models.
        <UsageTable
          key={`${metric}-${granularity}-${focused ?? 'all'}`}
          buckets={tableBuckets}
          granularity={granularity}
          series={tableSeries}
          focus={focused}
          onFocus={setFocus}
          showBilling={billing}
          measure={measure}
        />
      ) : (
        // Chart first; the ranked models table below doubles as its legend and filter.
        <div className="min-w-0">
          {items.length === 0 ? (
            <div className="grid min-h-60 place-items-center text-sm text-fg-muted">{empty}</div>
          ) : agg === 'total' ? (
            <CumulativeChart
              daily={total.daily}
              period={{ start: range.from, end: range.to }}
              projection={total.projection}
              measure={measure}
            />
          ) : (
            <StackedBarsChart
              buckets={chartBuckets}
              granularity={granularity}
              series={series}
              focus={focused}
              showBilling={billing}
              measure={measure}
            />
          )}
        </div>
      )}
      {credits ? (
        <ModelsPanel
          ranking={creditRanking}
          series={series}
          focus={focused}
          onFocus={setFocus}
          showBilling={showBilling}
        />
      ) : (
        <CallsPanel ranking={callsRank} series={series} metric={metric} focus={focused} onFocus={setFocus} />
      )}
    </Card>
  )
}

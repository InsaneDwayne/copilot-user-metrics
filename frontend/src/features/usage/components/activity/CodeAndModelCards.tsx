import { useState } from 'react'
import { Card, Note } from '@/shared/components/ui/Card'
import { HeatTable } from '@/shared/components/ui/HeatTable'
import { Tiles } from '@/shared/components/ui/Kpi'
import { Segmented } from '@/shared/components/ui/Segmented'
import { EmptyRow, Table, Td, Th } from '@/shared/components/ui/Table'
import { Tag } from '@/shared/components/ui/Tag'
import { formatCredits, formatPercent } from '@/shared/utils/format'
import type { CodeChanges, LanguageModelUse, ModelFeatureUse } from '@/features/usage/api/usage'
import { featureLabel } from '@/features/usage/utils/labels'

interface CodeAndModelCardsProps {
  codeChanges: CodeChanges
  modelFeatures: ModelFeatureUse[]
  languageModels: LanguageModelUse[]
}

/** Agent vs. person-guided code changes, and which models are used for what. */
export function CodeAndModelCards({ codeChanges, modelFeatures, languageModels }: CodeAndModelCardsProps) {
  return (
    <>
      <CodeChangesCard changes={codeChanges} />
      <div className="grid grid-cols-[repeat(auto-fit,minmax(min(100%,560px),1fr))] gap-4">
        <MatrixCard
          title="Models by feature"
          subtitle="Which models people use for which kind of work, for the most used models."
          empty="No model use by feature in this period."
          cells={modelFeatures}
          measures={MODEL_MEASURES}
          row={(c) => c.model}
          col={(c) => c.feature}
          rowHeader="Model"
          colLabel={featureLabel}
        />
        <MatrixCard
          title="Languages by model"
          subtitle="Which models write code in which languages, for the most used of both."
          empty="No code by language and model in this period."
          cells={languageModels}
          measures={LANGUAGE_MEASURES}
          row={(c) => c.language}
          col={(c) => c.model}
          rowHeader="Language"
        />
      </div>
    </>
  )
}

function CodeChangesCard({ changes: c }: { changes: CodeChanges }) {
  const changed = c.loc_added + c.loc_deleted
  return (
    <Card
      title="Code changes by mode"
      subtitle="Lines added and deleted with Copilot, split into what agents changed on their own and what people accepted or applied."
    >
      <Tiles
        items={[
          { label: 'Changed by agents', value: formatPercent(c.agent_share) },
          { label: 'Lines by agents', value: formatCredits(c.agent_loc_changed) },
          { label: 'Lines guided by people', value: formatCredits(changed - c.agent_loc_changed) },
          { label: 'Added · deleted', value: `${formatCredits(c.loc_added)} · ${formatCredits(c.loc_deleted)}` },
        ]}
      />
      <Table minWidth={620}>
        <thead>
          <tr>
            <Th>Mode</Th>
            <Th align="right">Suggested</Th>
            <Th align="right">Added</Th>
            <Th align="right">Deleted</Th>
            <Th align="right">Share of changes</Th>
          </tr>
        </thead>
        <tbody>
          {c.by_feature.length === 0 && <EmptyRow colSpan={5}>No code changes in this period.</EmptyRow>}
          {c.by_feature.map((f) => (
            <tr key={f.feature}>
              <Td>
                <span className="inline-flex items-center gap-2">
                  {featureLabel(f.feature)}
                  {f.agent && <Tag tone="accent">Agent</Tag>}
                </span>
              </Td>
              <Td align="right" numeric tone="muted">
                {formatCredits(f.loc_suggested_add + f.loc_suggested_delete)}
              </Td>
              <Td align="right" numeric>
                {formatCredits(f.loc_added)}
              </Td>
              <Td align="right" numeric>
                {formatCredits(f.loc_deleted)}
              </Td>
              <Td align="right" numeric tone="muted">
                {formatPercent(changed ? (f.loc_added + f.loc_deleted) / changed : null)}
              </Td>
            </tr>
          ))}
        </tbody>
      </Table>
      <Note>
        Agent edits are the lines agent and edit modes wrote into files themselves; the other modes count lines people
        accepted or applied. Suggested lines were offered but not necessarily kept.
      </Note>
    </Card>
  )
}

type ModelMeasure = 'prompts' | 'generations' | 'loc_changed'
const MODEL_MEASURES: { value: ModelMeasure; label: string }[] = [
  { value: 'prompts', label: 'Prompts' },
  { value: 'generations', label: 'Code generations' },
  { value: 'loc_changed', label: 'Lines changed' },
]

type LanguageMeasure = 'generations' | 'loc_changed'
const LANGUAGE_MEASURES: { value: LanguageMeasure; label: string }[] = [
  { value: 'generations', label: 'Code generations' },
  { value: 'loc_changed', label: 'Lines changed' },
]

/** Distinct keys in order of their summed weight, largest first. */
function ranked<T>(cells: T[], key: (c: T) => string, weight: (c: T) => number): string[] {
  const totals = new Map<string, number>()
  for (const c of cells) totals.set(key(c), (totals.get(key(c)) ?? 0) + weight(c))
  return [...totals.entries()].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0])).map(([k]) => k)
}

interface MatrixCardProps<T, M extends string> {
  title: string
  subtitle: string
  empty: string
  cells: T[]
  measures: { value: M; label: string }[]
  row: (c: T) => string
  col: (c: T) => string
  rowHeader: string
  colLabel?: (col: string) => string
}

/** A heat table of `cells` (rows × columns), switchable between `measures`. */
function MatrixCard<T extends Record<M, number>, M extends string>({
  title,
  subtitle,
  empty,
  cells,
  measures,
  row,
  col,
  rowHeader,
  colLabel,
}: MatrixCardProps<T, M>) {
  const [measure, setMeasure] = useState<M>(measures[0].value)
  const weight = (c: T) => c[measure]
  const shown = cells.filter((c) => weight(c) > 0)
  const value = new Map(shown.map((c) => [`${row(c)}\u0000${col(c)}`, weight(c)]))
  return (
    <Card
      title={title}
      subtitle={subtitle}
      aside={
        <Segmented label={`${title}: measure`} size="sm" value={measure} onChange={setMeasure} options={measures} />
      }
    >
      {shown.length === 0 ? (
        <div className="text-xs text-fg-muted">{empty}</div>
      ) : (
        <HeatTable
          rows={ranked(shown, row, weight)}
          cols={ranked(shown, col, weight)}
          value={(r, c) => value.get(`${r}\u0000${c}`) ?? 0}
          rowHeader={rowHeader}
          colLabel={colLabel}
          format={formatCredits}
        />
      )}
    </Card>
  )
}

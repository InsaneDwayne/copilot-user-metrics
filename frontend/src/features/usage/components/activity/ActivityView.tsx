import { Card, Note } from '@/shared/components/ui/Card'
import { KpiGrid, Tiles } from '@/shared/components/ui/Kpi'
import { ShareBar } from '@/shared/components/ui/ShareBar'
import { EmptyRow, Table, Td, Th } from '@/shared/components/ui/Table'
import { formatCredits, formatDay, formatPercent } from '@/shared/utils/format'
import type { Activity } from '@/features/usage/api/usage'
import {
  PHASE_NOTE,
  SKILLS_NOTE,
  SURFACE_LABELS,
  featureLabel,
  phaseLabel,
  skillLabel,
} from '@/features/usage/utils/labels'
import { CodeAndModelCards } from './CodeAndModelCards'

export function ActivityView({ activity }: { activity: Activity }) {
  const maxFeature = Math.max(1, ...activity.features.map((f) => f.count))
  const maxSkill = Math.max(1, ...activity.skills.map((s) => s.count))
  return (
    <div className="flex flex-col gap-4">
      <KpiGrid
        items={[
          {
            label: 'Active days',
            value: `${activity.active_days} of ${activity.elapsed_days}`,
            meta: activity.top_ide ? `Top editor ${activity.top_ide}` : 'No editor activity',
          },
          { label: 'Prompts sent', value: formatCredits(activity.prompts), meta: 'Explicit prompts to Copilot' },
          {
            label: 'Lines added',
            value: formatCredits(activity.loc_added),
            meta: `${formatCredits(activity.loc_suggested)} suggested`,
          },
          { label: 'Acceptance rate', value: formatPercent(activity.acceptance_rate), meta: 'Accepted ÷ generated' },
          {
            label: 'Adoption phase',
            value: phaseLabel(activity.adoption_phase),
            meta: activity.adoption_phase ? 'As GitHub classifies it' : 'GitHub reported none in this period',
          },
        ]}
      />
      <div className="grid grid-cols-[repeat(auto-fit,minmax(min(100%,420px),1fr))] gap-4">
        <Card title="Prompts by chat mode" subtitle="From the per-feature breakdown in GitHub's daily metrics.">
          {activity.features.length === 0 && <div className="text-xs text-fg-muted">No prompts in this period.</div>}
          {activity.features.map((f) => (
            <div key={f.name} className="grid grid-cols-[120px_minmax(0,1fr)_56px] items-center gap-3 text-sm">
              <span>{featureLabel(f.name)}</span>
              <ShareBar value={f.count / maxFeature} />
              <span className="text-right text-fg-muted tabular-nums">{formatCredits(f.count)}</span>
            </div>
          ))}
        </Card>
        <Card title="Skills" subtitle="How often each skill was invoked in the period.">
          {activity.skills.length === 0 && (
            <div className="text-xs text-fg-muted">No skills invoked in this period.</div>
          )}
          {activity.skills.map((s) => (
            <div key={s.name} className="grid grid-cols-[120px_minmax(0,1fr)_56px] items-center gap-3 text-sm">
              <span className="truncate" title={skillLabel(s.name)}>
                {skillLabel(s.name)}
              </span>
              <ShareBar value={s.count / maxSkill} label={`${skillLabel(s.name)}: ${formatCredits(s.count)}`} />
              <span className="text-right text-fg-muted tabular-nums">{formatCredits(s.count)}</span>
            </div>
          ))}
          {activity.skills.length > 0 && <Note>{SKILLS_NOTE}</Note>}
        </Card>
        <Card title="Languages">
          <Table>
            <thead>
              <tr>
                <Th>Language</Th>
                <Th align="right">Lines added</Th>
                <Th align="right">Acceptance</Th>
              </tr>
            </thead>
            <tbody>
              {activity.languages.length === 0 && <EmptyRow colSpan={3}>No code activity in this period.</EmptyRow>}
              {activity.languages.map((l) => (
                <tr key={l.language}>
                  <Td>{l.language}</Td>
                  <Td align="right" numeric>
                    {formatCredits(l.loc_added)}
                  </Td>
                  <Td align="right" numeric tone="muted">
                    {formatPercent(l.acceptance_rate)}
                  </Td>
                </tr>
              ))}
            </tbody>
          </Table>
        </Card>
      </div>
      <CodeAndModelCards
        codeChanges={activity.code_changes}
        modelFeatures={activity.model_features}
        languageModels={activity.language_models}
      />
      <Card title="Days used, by surface">
        <Tiles
          items={activity.surfaces.map((s) => ({
            label: SURFACE_LABELS[s.surface],
            value: `${s.days} day${s.days === 1 ? '' : 's'}`,
          }))}
        />
      </Card>
      <Note>
        Activity comes from GitHub's daily Copilot usage metrics and covers complete days only
        {activity.data_through ? ` — currently through ${formatDay(activity.data_through)}` : ''}. IDE numbers need
        telemetry enabled in the editor. Code completions don't use AI credits. {PHASE_NOTE}
      </Note>
    </div>
  )
}

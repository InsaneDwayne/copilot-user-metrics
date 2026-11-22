import type { AdoptionPhase, Surface } from '@/features/usage/api/usage'

const FEATURES: Record<string, string> = {
  chat_panel_agent_mode: 'Agent mode',
  chat_panel_ask_mode: 'Ask mode',
  chat_panel_edit_mode: 'Edit mode',
  chat_panel_plan_mode: 'Plan mode',
  chat_panel_custom_mode: 'Custom mode',
  chat_panel_unknown_mode: 'Chat (other)',
  chat_inline: 'Inline chat',
  code_completion: 'Code completion',
  agent_edit: 'Agent edits',
  copilot_cli: 'Copilot CLI',
}

/** GitHub's feature keys as people say them; unknown keys are humanised. */
export function featureLabel(feature: string): string {
  return FEATURES[feature] ?? feature.replace(/_/g, ' ').replace(/^\w/, (c) => c.toUpperCase())
}

export const SURFACE_LABELS: Record<Surface, string> = {
  chat: 'Chat',
  agent: 'Agent mode',
  cli: 'Copilot CLI',
  cloud_agent: 'Cloud agent',
  app: 'Copilot app',
  code_review: 'Code review',
}

/** GitHub's own label ("Phase 2", "No Cohort"); "Not reported" when it gave none. */
export const phaseLabel = (p: AdoptionPhase | null) => p?.label ?? 'Not reported'

/** GitHub's skill name; it groups the ones it doesn't list by name under "other". */
export const skillLabel = (skill: string) => (skill === 'other' ? 'Other skills' : skill)

export const SKILLS_NOTE =
  'Skill invocations from GitHub’s daily metrics. GitHub lists a limited number of skills by name and counts ' +
  'the rest as “Other skills”.'

export const PHASE_NOTE =
  'GitHub assigns each person an AI adoption phase every day: “No Cohort” by default, then Phase 1 to 3 for ' +
  'deeper use. It doesn’t publish the thresholds behind them.'

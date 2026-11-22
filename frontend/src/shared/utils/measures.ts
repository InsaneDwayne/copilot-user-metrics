import { formatCompact, formatCredits } from './format'

/** What a usage chart or table counts. */
export interface Measure {
  /** Heading form, e.g. "AI credits" or "Tokens". */
  title: string
  /** In-sentence plural noun, e.g. "AI credits" or "tokens". */
  label: string
  format: (n: number) => string
  /** Text for a bar or day with nothing in it. */
  none: string
}

export const CREDITS: Measure = {
  title: 'AI credits',
  label: 'AI credits',
  format: formatCredits,
  none: 'No AI credits used',
}
export const TOKENS: Measure = { title: 'Tokens', label: 'tokens', format: formatCompact, none: 'No model calls' }
export const REQUESTS: Measure = { title: 'Requests', label: 'requests', format: formatCredits, none: 'No model calls' }

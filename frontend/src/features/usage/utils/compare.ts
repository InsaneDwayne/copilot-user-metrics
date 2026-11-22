import type { UsageSubject } from '@/features/usage/api/usage'

/** "You: 1.4× the average", "@bob: below half the average". */
export function compareToAverage(credits: number, average: number, subject: UsageSubject): string {
  const who = subject.kind === 'me' ? 'You' : `@${subject.login}`
  if (average <= 0) return 'No org usage yet'
  const ratio = credits / average
  if (ratio === 0) return `${who}: none used yet`
  if (ratio < 0.5) return `${who}: under half the average`
  if (ratio < 0.95) return `${who}: ${Math.round(ratio * 100)}% of the average`
  if (ratio <= 1.05) return `${who}: about average`
  return `${who}: ${ratio.toFixed(1)}× the average`
}

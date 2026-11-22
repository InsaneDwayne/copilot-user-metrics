import { LabelledBar } from '@/shared/components/ui/ShareBar'
import { formatCredits, share } from '@/shared/utils/format'

export function CreditsBar({ credits, maxCredits }: { credits: number; maxCredits: number }) {
  return (
    <LabelledBar
      value={share(credits, maxCredits) ?? 0}
      figure={formatCredits(credits)}
      label="AI credits relative to the top consumer"
    />
  )
}

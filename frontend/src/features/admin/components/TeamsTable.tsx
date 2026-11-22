import { useNavigate, useSearchParams } from 'react-router'
import { DownloadButton } from '@/shared/components/DownloadButton'
import { Card } from '@/shared/components/ui/Card'
import { periodSearch } from '@/shared/hooks/usePeriod'
import { EmptyRow, Table, Td, Th } from '@/shared/components/ui/Table'
import { saveFile, toCsvText } from '@/shared/utils/csv'
import { formatPercent, formatUsd } from '@/shared/utils/format'
import type { DayRange } from '@/shared/utils/period'
import type { TeamUsage } from '@/features/admin/api/admin'
import { CreditsBar } from './CreditsBar'

const toTeamsCsv = (teams: TeamUsage[]) =>
  toCsvText(
    ['team', 'seats', 'active_7d', 'ai_credits', 'list_value_usd', 'acceptance_rate', 'top_model'],
    teams.map((t) => [t.team, t.seats, t.active_7d, t.credits, t.gross_usd, t.acceptance_rate, t.top_model]),
  )

export function TeamsTable({ teams, range }: { teams: TeamUsage[]; range: DayRange }) {
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const max = Math.max(0, ...teams.map((t) => t.credits))
  return (
    <Card
      title="By team"
      subtitle="From GitHub's daily user-teams report, which leaves out teams with fewer than 5 Copilot seats. A member in several teams counts in each."
      aside={
        <DownloadButton
          title="Download every team in this period as CSV"
          disabled={teams.length === 0}
          onDownload={() => saveFile(`copilot-teams-${range.from}_${range.to}.csv`, toTeamsCsv(teams))}
        />
      }
    >
      <Table minWidth={680}>
        <thead>
          <tr>
            <Th>Team</Th>
            <Th align="right">Seats</Th>
            <Th align="right">Active · 7 d</Th>
            <Th className="w-[26%]">AI credits</Th>
            <Th align="right">Value</Th>
            <Th align="right">Acceptance</Th>
            <Th>Top model</Th>
          </tr>
        </thead>
        <tbody>
          {teams.length === 0 && (
            <EmptyRow colSpan={7}>No team data yet — it arrives with the daily metrics sync.</EmptyRow>
          )}
          {teams.map((t) => (
            <tr
              key={t.team}
              className="cursor-pointer"
              onClick={() =>
                navigate({ pathname: `/admin/teams/${encodeURIComponent(t.team)}`, search: periodSearch(params) })
              }
            >
              <Td>{t.team}</Td>
              <Td align="right" numeric>
                {t.seats}
              </Td>
              <Td align="right" numeric tone="muted">
                {t.active_7d}
              </Td>
              <Td>
                <CreditsBar credits={t.credits} maxCredits={max} />
              </Td>
              <Td align="right" numeric>
                {formatUsd(t.gross_usd)}
              </Td>
              <Td align="right" numeric tone="muted">
                {formatPercent(t.acceptance_rate)}
              </Td>
              <Td tone="meta">{t.top_model ?? '—'}</Td>
            </tr>
          ))}
        </tbody>
      </Table>
    </Card>
  )
}

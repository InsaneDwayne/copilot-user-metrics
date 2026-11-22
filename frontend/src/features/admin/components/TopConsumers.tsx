import { ArrowRightIcon } from '@phosphor-icons/react'
import { Link, useNavigate } from 'react-router'
import { Person } from '@/shared/components/ui/Avatar'
import { Card } from '@/shared/components/ui/Card'
import { Table, Td } from '@/shared/components/ui/Table'
import { buttonClass } from '@/shared/components/ui/variants'
import { formatUsd } from '@/shared/utils/format'
import type { MemberPage } from '@/features/admin/api/admin'
import { memberPath } from '@/features/admin/utils/members'
import { CreditsBar } from './CreditsBar'

/** The first page of members by AI credits; ask the API for just the rows shown. */
export function TopConsumers({ members }: { members: MemberPage }) {
  const navigate = useNavigate()
  const top = members.items
  const max = top[0]?.credits ?? 0
  return (
    <Card
      title="Top consumers"
      aside={
        <Link className={buttonClass('ghost', 'sm')} to="/admin/members">
          All {members.members} members
          <ArrowRightIcon />
        </Link>
      }
    >
      <Table>
        <tbody>
          {top.map((m) => (
            <tr key={m.login} className="cursor-pointer" onClick={() => navigate(memberPath(m.login))}>
              <Td className="w-[30%]">
                <Person login={m.login} url={m.avatar_url} />
              </Td>
              <Td>
                <CreditsBar credits={m.credits} maxCredits={max} />
              </Td>
              <Td align="right" numeric tone="muted" className="w-22.5">
                {formatUsd(m.gross_usd)}
              </Td>
            </tr>
          ))}
        </tbody>
      </Table>
    </Card>
  )
}

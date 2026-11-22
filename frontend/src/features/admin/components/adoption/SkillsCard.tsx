import { ArrowRightIcon, MagnifyingGlassIcon } from '@phosphor-icons/react'
import { useMemo, useState } from 'react'
import { Button } from '@/shared/components/ui/Button'
import { Card, Note } from '@/shared/components/ui/Card'
import { Dialog } from '@/shared/components/ui/Dialog'
import { Segmented } from '@/shared/components/ui/Segmented'
import { ShareBar } from '@/shared/components/ui/ShareBar'
import { EmptyRow, Table, Td, Th } from '@/shared/components/ui/Table'
import { inputClass } from '@/shared/components/ui/variants'
import { cn } from '@/shared/utils/cn'
import { formatCredits, formatPercent, share } from '@/shared/utils/format'
import { SKILLS_NOTE, skillLabel } from '@/features/usage'
import type { OrgAdoption } from '@/features/admin/api/admin'

type Skill = OrgAdoption['skills'][number]
type SortBy = 'users' | 'invocations'

/** How many skills the card lists; the rest are a click away in the full list. */
const TOP = 10

const plural = (n: number, one: string, many: string) => `${formatCredits(n)} ${n === 1 ? one : many}`

/**
 * The most used skills at a glance, the full list on demand. A long tail of skills would
 * otherwise push the rest of the page down, so the card stays the same size whatever the count.
 */
export function SkillsCard({ skills, activeUsers }: { skills: Skill[]; activeUsers: number }) {
  const [open, setOpen] = useState(false)
  const top = skills.slice(0, TOP)
  const invocations = skills.reduce((sum, s) => sum + s.invocations, 0)
  return (
    <Card
      title="Skills"
      subtitle={
        skills.length > 0
          ? `${plural(skills.length, 'skill', 'skills')} invoked ${plural(invocations, 'time', 'times')} in the period. Bars show the share of active people who used each.`
          : 'Which skills people invoke, and how many of them.'
      }
      aside={
        skills.length > TOP && (
          <Button variant="ghost" size="sm" onClick={() => setOpen(true)}>
            Show all {skills.length}
            <ArrowRightIcon />
          </Button>
        )
      }
    >
      {skills.length === 0 ? (
        <div className="text-xs text-fg-muted">No skills invoked in this period.</div>
      ) : (
        // Columns, not a grid, so the ranking reads down: 1–5 on the left, 6–10 on the right.
        <ol className="gap-x-10 lg:columns-2">
          {top.map((s, i) => (
            <SkillRow key={s.name} rank={i + 1} skill={s} activeUsers={activeUsers} />
          ))}
        </ol>
      )}
      {skills.length > 0 && (
        <Note>
          {skills.length > TOP && `The ${TOP} skills most people used. `}
          {SKILLS_NOTE}
        </Note>
      )}
      <AllSkillsDialog open={open} onClose={() => setOpen(false)} skills={skills} activeUsers={activeUsers} />
    </Card>
  )
}

function SkillRow({ rank, skill: s, activeUsers }: { rank: number; skill: Skill; activeUsers: number }) {
  const label = skillLabel(s.name)
  return (
    // Fixed figure columns keep every bar the same length, in both columns.
    <li className="grid break-inside-avoid grid-cols-[1.25rem_minmax(0,10rem)_minmax(3rem,1fr)_6rem_4.5rem] items-center gap-3 py-1.25 text-sm">
      <span className="text-right text-xs text-fg-subtle tabular-nums">{rank}</span>
      <span className="truncate" title={label}>
        {label}
      </span>
      <ShareBar value={share(s.users, activeUsers) ?? 0} label={`${label}: ${plural(s.users, 'person', 'people')}`} />
      <span className="text-right whitespace-nowrap tabular-nums">{plural(s.users, 'person', 'people')}</span>
      <span className="text-right text-xs whitespace-nowrap text-fg-muted tabular-nums">
        {plural(s.invocations, 'use', 'uses')}
      </span>
    </li>
  )
}

function AllSkillsDialog({
  open,
  onClose,
  skills,
  activeUsers,
}: {
  open: boolean
  onClose: () => void
  skills: Skill[]
  activeUsers: number
}) {
  const [query, setQuery] = useState('')
  const [sortBy, setSortBy] = useState<SortBy>('users')
  const shown = useMemo(() => {
    const q = query.trim().toLowerCase()
    const matching = q ? skills.filter((s) => skillLabel(s.name).toLowerCase().includes(q)) : skills
    const other: SortBy = sortBy === 'users' ? 'invocations' : 'users'
    return [...matching].sort((a, b) => b[sortBy] - a[sortBy] || b[other] - a[other] || a.name.localeCompare(b.name))
  }, [skills, query, sortBy])
  const close = () => {
    setQuery('')
    onClose()
  }
  return (
    <Dialog
      open={open}
      onClose={close}
      className="max-w-2xl"
      title="All skills"
      description={`${plural(skills.length, 'skill', 'skills')} invoked in the period, by the people who used them.`}
    >
      <div className="flex flex-wrap items-center gap-2">
        <label className="relative min-w-48 flex-1">
          <span className="sr-only">Search skills</span>
          <MagnifyingGlassIcon className="pointer-events-none absolute top-1/2 left-2.5 -translate-y-1/2 text-fg-subtle" />
          <input
            data-autofocus
            type="search"
            className={cn(inputClass, 'pl-8')}
            placeholder="Search skills"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        </label>
        <Segmented
          label="Sort skills by"
          size="sm"
          value={sortBy}
          onChange={setSortBy}
          options={[
            { value: 'users', label: 'People' },
            { value: 'invocations', label: 'Uses' },
          ]}
        />
      </div>
      <div className="max-h-[min(60vh,32rem)] overflow-y-auto">
        <Table>
          <thead className="sticky top-0 z-10 bg-surface">
            <tr>
              <Th>Skill</Th>
              <Th align="right">People</Th>
              <Th align="right">Of active</Th>
              <Th align="right">Uses</Th>
              <Th align="right">Per person</Th>
            </tr>
          </thead>
          <tbody>
            {shown.length === 0 && <EmptyRow colSpan={5}>No skill matches “{query.trim()}”.</EmptyRow>}
            {shown.map((s) => (
              <tr key={s.name}>
                <Td className="max-w-56 truncate" title={skillLabel(s.name)}>
                  {skillLabel(s.name)}
                </Td>
                <Td align="right" numeric>
                  {formatCredits(s.users)}
                </Td>
                <Td align="right" numeric tone="muted">
                  {formatPercent(share(s.users, activeUsers))}
                </Td>
                <Td align="right" numeric>
                  {formatCredits(s.invocations)}
                </Td>
                <Td align="right" numeric tone="muted">
                  {s.users ? (s.invocations / s.users).toFixed(1) : '—'}
                </Td>
              </tr>
            ))}
          </tbody>
        </Table>
      </div>
      {query.trim() && shown.length > 0 && (
        <Note>
          Showing {formatCredits(shown.length)} of {formatCredits(skills.length)}.
        </Note>
      )}
    </Dialog>
  )
}

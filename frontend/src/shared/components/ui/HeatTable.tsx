import { heatTint } from './heatTint'
import { Table, Td, Th } from './Table'

interface HeatTableProps {
  rows: string[]
  cols: string[]
  value: (row: string, col: string) => number
  rowHeader: string
  rowLabel?: (row: string) => string
  colLabel?: (col: string) => string
  format: (n: number) => string
}

/**
 * A rows × columns table whose cells are tinted by their value (one hue, light to strong).
 * Every cell also prints its number, so the colour is never the only cue.
 */
export function HeatTable({ rows, cols, value, rowHeader, rowLabel, colLabel, format }: HeatTableProps) {
  const max = Math.max(0, ...rows.flatMap((r) => cols.map((c) => value(r, c))))
  return (
    <Table minWidth={160 + cols.length * 96}>
      <thead>
        <tr>
          <Th>{rowHeader}</Th>
          {cols.map((c) => (
            <Th key={c} align="right">
              {colLabel ? colLabel(c) : c}
            </Th>
          ))}
        </tr>
      </thead>
      <tbody>
        {rows.map((r) => (
          <tr key={r}>
            <Td>{rowLabel ? rowLabel(r) : r}</Td>
            {cols.map((c) => {
              const v = value(r, c)
              return (
                <Td key={c} align="right" numeric tone={v ? undefined : 'muted'} className={heatTint(v, max)}>
                  {v ? format(v) : '—'}
                </Td>
              )
            })}
          </tr>
        ))}
      </tbody>
    </Table>
  )
}

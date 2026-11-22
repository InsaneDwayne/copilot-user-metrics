/**
 * CSV for spreadsheets. Text a spreadsheet would read as a formula (`=`, `+`, `-`, `@`, tab or
 * carriage return first) gets a leading apostrophe, so a name can't run anything when the file
 * is opened (CSV injection). Numbers stay numbers, negative ones included.
 */
export type CsvValue = string | number | null | undefined

const FORMULA_START = /^[=+\-@\t\r]/

export function csvCell(v: CsvValue): string {
  if (v === null || v === undefined) return ''
  if (typeof v === 'number') return String(v)
  const s = FORMULA_START.test(v) ? `'${v}` : v
  return /[",\n\r]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s
}

export function toCsvText(header: string[], rows: CsvValue[][]): string {
  return [header, ...rows].map((r) => r.map(csvCell).join(',')).join('\n') + '\n'
}

/** Saves `data` as a file through a temporary link. */
export function saveFile(filename: string, data: Blob | string) {
  const blob = typeof data === 'string' ? new Blob([data], { type: 'text/csv;charset=utf-8' }) : data
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

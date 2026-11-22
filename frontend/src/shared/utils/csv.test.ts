import { describe, expect, it } from 'vitest'
import { csvCell, toCsvText } from './csv'

describe('csv', () => {
  it('defuses formulas and quotes awkward text', () => {
    expect(csvCell('=HYPERLINK("x")')).toBe(`"'=HYPERLINK(""x"")"`)
    expect(csvCell('@bob')).toBe("'@bob")
    expect(csvCell('-team')).toBe("'-team")
    expect(csvCell('a, b')).toBe('"a, b"')
    expect(csvCell(-3)).toBe('-3')
    expect(csvCell(null)).toBe('')
  })

  it('writes a header and one line per row', () => {
    expect(
      toCsvText(
        ['team', 'seats'],
        [
          ['core', 4],
          ['+ops', 2],
        ],
      ),
    ).toBe("team,seats\ncore,4\n'+ops,2\n")
  })
})

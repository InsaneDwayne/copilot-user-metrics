import { describe, expect, it } from 'vitest'
import { pageParam, pageRange, pageSizeParam, parsePage, parsePageSize } from './pagination'

describe('pageRange', () => {
  it('gives the rows a page covers, with a short last page', () => {
    expect(pageRange({ page: 2, pages: 3, size: 3, total: 7 })).toEqual({ from: 4, to: 6 })
    expect(pageRange({ page: 3, pages: 3, size: 3, total: 7 })).toEqual({ from: 7, to: 7 })
  })

  it('is empty when there are no rows', () => {
    expect(pageRange({ page: 1, pages: 1, size: 25, total: 0 })).toEqual({ from: 0, to: 0 })
  })
})

describe('page params', () => {
  it('reads positive integers and falls back to page 1', () => {
    expect(parsePage('3')).toBe(3)
    for (const v of [null, '', '0', '-2', '1.5', 'abc']) expect(parsePage(v)).toBe(1)
  })

  it('leaves page 1 out of the URL', () => {
    expect(pageParam(1)).toBeNull()
    expect(pageParam(4)).toBe('4')
  })
})

describe('page size params', () => {
  it('accepts only the offered sizes', () => {
    expect(parsePageSize('50')).toBe(50)
    expect(parsePageSize('100')).toBe(100)
    for (const v of [null, '', '30', '1000', 'abc']) expect(parsePageSize(v)).toBe(25)
  })

  it('leaves the default size out of the URL', () => {
    expect(pageSizeParam(25)).toBeNull()
    expect(pageSizeParam(100)).toBe('100')
  })
})

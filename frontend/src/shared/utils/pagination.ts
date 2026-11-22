/** Where a page sits in its list, without its rows (the fields of the API's ``Page``). */
export type PageInfo = { page: number; pages: number; size: number; total: number }

/** Rows-per-page choices; the first is the default (the backend's too) and the last its maximum. */
export const PAGE_SIZES = [25, 50, 100] as const
export type PageSize = (typeof PAGE_SIZES)[number]
const DEFAULT_PAGE_SIZE: PageSize = PAGE_SIZES[0]

/** Reads a page size from a URL param; anything but one of the choices is the default. */
export function parsePageSize(value: string | null): PageSize {
  return PAGE_SIZES.find((s) => String(s) === value) ?? DEFAULT_PAGE_SIZE
}

/** The URL value for a page size: the default leaves the param out. */
export const pageSizeParam = (size: number) => (size === DEFAULT_PAGE_SIZE ? null : String(size))

/** Reads a 1-based page number from a URL param; anything that is not a positive integer is page 1. */
export function parsePage(value: string | null): number {
  const n = Number(value)
  return Number.isInteger(n) && n > 0 ? n : 1
}

/** The URL value for a page: page 1 is the default and leaves the param out. */
export const pageParam = (page: number) => (page > 1 ? String(page) : null)

/** 1-based positions of the first and last row on the page, for "26–50 of 312"; both 0 when empty. */
export function pageRange({ page, size, total }: PageInfo): { from: number; to: number } {
  if (total === 0) return { from: 0, to: 0 }
  const start = (page - 1) * size
  return { from: start + 1, to: Math.min(start + size, total) }
}

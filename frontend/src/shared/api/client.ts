/**
 * Thin fetch wrapper. Every response is validated with a zod schema — the
 * frontend counterpart of the backend's pydantic models — so a contract drift
 * shows up as one clear error instead of `undefined` deep in a component.
 * The session is an http-only cookie; no token ever reaches JavaScript.
 */
import { z } from 'zod'
import { env } from '@/config/env'
import { saveFile } from '@/shared/utils/csv'

/** The backend's single error shape (see ``shared/error_handlers.py``). */
const errorBodySchema = z.object({ code: z.string(), detail: z.string() })

export class ApiError extends Error {
  readonly status: number
  /** Stable machine-readable name, e.g. ``session_expired`` or ``member_not_found``. */
  readonly code: string

  constructor(status: number, message: string, code = 'http_error') {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
  }
}

export type QueryParams = Record<string, string | null | undefined>

function url(path: string, params?: QueryParams): string {
  const query = new URLSearchParams()
  for (const [key, value] of Object.entries(params ?? {})) if (value) query.set(key, value)
  const qs = query.toString()
  return `${env.VITE_API_BASE_URL}${path}${qs ? `?${qs}` : ''}`
}

async function failure(response: Response): Promise<ApiError> {
  try {
    const body = errorBodySchema.safeParse(await response.json())
    if (body.success) return new ApiError(response.status, body.data.detail, body.data.code)
  } catch {
    // not JSON (e.g. a proxy error page) — fall back to the status text
  }
  return new ApiError(response.status, response.statusText)
}

export async function apiGet<S extends z.ZodType>(path: string, schema: S, params?: QueryParams): Promise<z.output<S>> {
  const response = await fetch(url(path, params), {
    credentials: 'same-origin',
    headers: { Accept: 'application/json' },
  })
  if (!response.ok) throw await failure(response)
  return schema.parse(await response.json())
}

export async function apiPost(path: string): Promise<void> {
  const response = await fetch(url(path), { method: 'POST', credentials: 'same-origin' })
  if (!response.ok) throw await failure(response)
}

/**
 * Downloads a file the API builds (e.g. a CSV export) and saves it under the name the API
 * gives, so errors surface as an ``ApiError`` instead of a page of JSON.
 */
export async function apiDownload(path: string, params: QueryParams, fallbackName: string): Promise<void> {
  const response = await fetch(url(path, params), { credentials: 'same-origin' })
  if (!response.ok) throw await failure(response)
  const name = /filename="([^"]+)"/.exec(response.headers.get('Content-Disposition') ?? '')?.[1]
  saveFile(name ?? fallbackName, await response.blob())
}

/** Full-page navigations (OAuth redirects) go through the same base URL. */
export const apiHref = (path: string) => url(path)

export const isUnauthorized = (error: unknown) => error instanceof ApiError && error.status === 401

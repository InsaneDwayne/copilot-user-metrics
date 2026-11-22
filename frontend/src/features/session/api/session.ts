import { z } from 'zod'
import { apiGet, apiHref, apiPost, isUnauthorized } from '@/shared/api/client'

/** admin: org data and the Sync page; org_reader (organization reader): org data, read only; member: own usage only. */
const roleSchema = z.enum(['admin', 'org_reader', 'member', 'outsider'])

const sessionSchema = z.object({
  login: z.string(),
  user_id: z.number(),
  name: z.string().nullable(),
  avatar_url: z.string().nullable(),
  role: roleSchema,
  has_seat: z.boolean(),
  access: z.object({
    can_view_own_usage: z.boolean(),
    /** The admin console (admins and organization readers). */
    can_view_admin: z.boolean(),
    /** The admin console's Sync page (admins only). */
    can_manage_sync: z.boolean(),
  }),
})

export type Session = z.infer<typeof sessionSchema>

/** The signed-in person, or `null` when signed out. */
export async function fetchSession(): Promise<Session | null> {
  try {
    return await apiGet('/api/session', sessionSchema)
  } catch (error) {
    if (isUnauthorized(error)) return null
    throw error
  }
}

export const signOut = () => apiPost('/auth/logout')

/** Starts GitHub sign-in: a full-page redirect to the backend, which redirects to GitHub. */
export const signInHref = () => apiHref('/auth/github')

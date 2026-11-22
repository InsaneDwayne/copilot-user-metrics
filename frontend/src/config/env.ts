/** Build-time environment (`VITE_*`), validated once. */
import { z } from 'zod'

const envSchema = z.object({
  /** Where the API lives. Empty = same origin (the Vite dev proxy or FastAPI serving the build). */
  VITE_API_BASE_URL: z.string().default(''),
})

export const env = envSchema.parse(import.meta.env)

import { z } from 'zod'
import { apiGet } from '@/shared/api/client'

const appConfigSchema = z.object({
  org: z.string(),
  session_max_age_hours: z.number(),
})

export const fetchAppConfig = () => apiGet('/api/config', appConfigSchema)

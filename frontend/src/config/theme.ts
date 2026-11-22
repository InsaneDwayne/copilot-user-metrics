/**
 * Corporate theming, loaded at runtime from `/theme/theme.json` (frontend/public/theme/,
 * baked into the image; a deployment can mount its own folder over /app/static/theme).
 * The folder is self-contained: paths in theme.json (logo, favicon, stylesheets) resolve
 * relative to it. Validated at start-up; an accent plus a ground per mode (light and dark)
 * expand into the full token set (see shared/theme/ramps.ts). A missing or invalid file
 * falls back to the defaults.
 */
import { themeConfigSchema, type ThemeConfig } from './themeSchema'

const THEME_URL = '/theme/theme.json'

export const defaultTheme: ThemeConfig = themeConfigSchema.parse({})

/** Parses a theme file's contents, or returns the defaults (and logs why) if it isn't valid. */
function parseTheme(raw: unknown): ThemeConfig {
  const result = themeConfigSchema.safeParse(raw)
  if (result.success) return result.data
  console.error(`Invalid ${THEME_URL}, using the default theme:`, result.error.issues)
  return defaultTheme
}

const ASSET_FIELDS = ['logoUrl', 'logoUrlDark', 'faviconUrl', 'fontStylesheetUrl', 'stylesheetUrl'] as const

/** Resolves the theme's paths against the theme file, so `logo.svg` means the file next to theme.json. */
export function resolveAssets(theme: ThemeConfig, themeFileUrl: string): ThemeConfig {
  const resolved = { ...theme }
  for (const field of ASSET_FIELDS) {
    const value = theme[field]
    if (value) resolved[field] = new URL(value, themeFileUrl).href
  }
  return resolved
}

async function loadTheme(): Promise<ThemeConfig> {
  try {
    // `no-cache` revalidates, so an edited theme shows up on the next reload.
    const response = await fetch(THEME_URL, { cache: 'no-cache' })
    if (!response.ok) throw new Error(`HTTP ${response.status}`)
    return resolveAssets(parseTheme(await response.json()), new URL(THEME_URL, window.location.href).href)
  } catch (error) {
    console.warn(`Could not load ${THEME_URL}, using the default theme:`, error)
    return defaultTheme
  }
}

export const themeConfig: ThemeConfig = await loadTheme()

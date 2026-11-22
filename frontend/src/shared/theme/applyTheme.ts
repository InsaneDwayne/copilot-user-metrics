import { THEME_MODES, type ThemeConfig, type ThemeMode } from '@/config/themeSchema'
import { accentRamp, deriveSurface, ensureContrast, neutralRamp, type Ramp } from './ramps'
import { STEPS, tokenValue } from './tokens'

/** The accent a mode actually uses: its own if set, else the shared one made readable on its ground. */
export function modeAccent(theme: ThemeConfig, mode: ThemeMode): string {
  const palette = theme.colors[mode]
  return palette.accent ?? ensureContrast(theme.colors.accent, palette.bg)
}

/**
 * CSS custom properties for one mode of a theme: base colours, ramps and role overrides.
 * The names are the Tailwind theme variables in shared/styles/index.css, so every utility
 * picks the theme up. Roles that aren't overridden keep their stylesheet default.
 */
export function themeVariables(theme: ThemeConfig, mode: ThemeMode): Record<string, string> {
  const { bg, text, surface, tokens } = theme.colors[mode]
  const accent = modeAccent(theme, mode)
  const vars: Record<string, string> = {
    '--color-canvas': bg,
    '--color-surface': surface ?? deriveSurface(bg),
    '--color-fg': text,
    '--color-accent': accent,
    '--font-sans': `"${theme.font}", system-ui, sans-serif`,
  }
  const addRamp = (name: string, ramp: Ramp) => {
    for (const step of STEPS) vars[`--color-${name}-${step}`] = ramp[step]
  }
  addRamp('accent', accentRamp(accent, mode))
  addRamp('neutral', neutralRamp(bg, mode))
  for (const [name, value] of Object.entries({ ...theme.colors.tokens, ...tokens })) {
    if (value) vars[`--color-${name}`] = tokenValue(value)
  }
  return vars
}

/**
 * The theme as a stylesheet, one rule per mode. `:where()` keeps the specificity at
 * `:root`, so the theme's own stylesheet (loaded after) can override any token with a
 * plain `:root { ... }` rule. Unlayered, it beats the Tailwind defaults in @layer theme.
 */
export function themeStylesheet(theme: ThemeConfig): string {
  return THEME_MODES.map((mode) => {
    const body = Object.entries(themeVariables(theme, mode))
      .map(([name, value]) => `  ${name}: ${value};`)
      .join('\n')
    return `:root:where([data-theme='${mode}']) {\n${body}\n}`
  }).join('\n')
}

function addLink(doc: Document, rel: string, href: string) {
  const link = doc.createElement('link')
  link.rel = rel
  link.href = href
  doc.head.append(link)
}

/** Applies the theme once, at start-up, for both modes. Switching mode is then just `data-theme`. */
export function applyTheme(theme: ThemeConfig, doc: Document = document): void {
  doc.title = theme.appName
  if (theme.faviconUrl) {
    // Replace the built-in icon (index.html) rather than adding a second one.
    for (const icon of doc.querySelectorAll('link[rel~="icon"]')) icon.remove()
    addLink(doc, 'icon', theme.faviconUrl)
  }
  if (theme.fontStylesheetUrl) addLink(doc, 'stylesheet', theme.fontStylesheetUrl)
  const style = doc.createElement('style')
  style.id = 'theme'
  style.textContent = themeStylesheet(theme)
  doc.head.append(style)
  // Last, so the theme's own CSS wins over everything above.
  if (theme.stylesheetUrl) addLink(doc, 'stylesheet', theme.stylesheetUrl)
}

/** Switches the document to a mode. `data-theme` selects the mode's tokens, `color-scheme` and shadows. */
export function applyMode(mode: ThemeMode, doc: Document = document): void {
  doc.documentElement.dataset.theme = mode
}

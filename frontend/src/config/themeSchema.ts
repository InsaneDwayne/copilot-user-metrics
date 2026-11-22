/**
 * Shape of `theme/theme.json` (corporate theming as code). The defaults match the Nocturne mockups.
 * The descriptions end up in theme.schema.json, i.e. in the editor of whoever brands a deployment.
 */
import { z } from 'zod'
// Relative, not `@/`: scripts/theme-schema.ts runs this file with plain node, which doesn't know the alias.
import { PALETTE_TOKENS, ROLE_TOKENS } from '../shared/theme/tokens.ts'

const hexColor = z.string().regex(/^#[0-9a-fA-F]{6}$/, 'expected a #rrggbb colour')
/** A file in the theme folder (`logo.svg`), a site path (`/theme/logo.svg`) or a full URL. */
const assetPath = z.string().min(1)

export const THEME_MODES = ['light', 'dark'] as const
export type ThemeMode = (typeof THEME_MODES)[number]
/** What the user (or the theme's `defaultMode`) asks for, in the header toggle's cycle order; `system` follows the OS setting. */
export const MODE_PREFERENCES = ['system', ...THEME_MODES] as const
export type ModePreference = (typeof MODE_PREFERENCES)[number]

// `id`s make the JSON schema define these once ($defs) instead of once per token.
const tokenValue = z.union([hexColor, z.enum(PALETTE_TOKENS)]).meta({
  id: 'tokenValue',
  description: 'A #rrggbb colour, or a palette token such as `accent-300`.',
})

const tokenOverrides = z
  .partialRecord(z.enum(ROLE_TOKENS), tokenValue)
  .default({})
  .describe(
    'Restyle individual roles (muted text, lines, tags, chart series, ...). A value is a #rrggbb colour ' +
      'or a palette token such as `accent-300` (ramp steps keep their contrast role in both modes).',
  )

/** One mode's ground. Every ramp and surface is derived from these. */
const palette = (defaults: { bg: string; text: string }) =>
  z.object({
    bg: hexColor.default(defaults.bg),
    text: hexColor.default(defaults.text),
    surface: hexColor.optional().describe('Card surface. Derived from `bg` when omitted.'),
    accent: hexColor
      .optional()
      .describe(
        "This mode's accent, used exactly as given. When omitted, `colors.accent` is used, " +
          'darkened or lightened just enough to stay readable on `bg` (4.5:1 contrast).',
      ),
    tokens: tokenOverrides.describe('Role overrides for this mode only; they win over `colors.tokens`.'),
  })

const colorsSchema = z.object({
  accent: hexColor.default('#9184d9').describe('The brand colour, shared by both modes.'),
  tokens: tokenOverrides,
  dark: palette({ bg: '#161826', text: '#e9e9ed' }).prefault({}),
  light: palette({ bg: '#f4f5fa', text: '#1b1d2a' }).prefault({}),
})

export const themeConfigSchema = z.object({
  appName: z.string().min(1).default('Copilot Usage').describe('Shown in the header and the browser tab.'),
  showAppName: z
    .boolean()
    .default(true)
    .describe('Show `appName` next to the logo. Turn off when the logo already contains the name.'),
  logoUrl: assetPath
    .nullable()
    .default(null)
    .describe('Logo for the header, e.g. `logo.svg` in the theme folder. Shown as is, at the header height.'),
  logoUrlDark: assetPath.nullable().default(null).describe('Logo for dark mode, when it differs from `logoUrl`.'),
  faviconUrl: assetPath
    .nullable()
    .default(null)
    .describe('Browser-tab icon, e.g. `favicon.svg`. Keeps the built-in icon when null.'),
  font: z.string().min(1).default('Inter').describe('Font family for all text.'),
  fontStylesheetUrl: assetPath
    .nullable()
    .default(null)
    .describe('Stylesheet that loads `font`: a web-font URL, or e.g. `fonts.css` with @font-face rules.'),
  stylesheetUrl: assetPath
    .nullable()
    .default(null)
    .describe(
      'Extra stylesheet loaded after the theme, e.g. `theme.css`, for anything theme.json does not cover. ' +
        'Override tokens there as `--color-<name>` (`:root[data-theme="light"]` for one mode).',
    ),
  defaultMode: z
    .enum(MODE_PREFERENCES)
    .default('system')
    .describe('The mode users see until they pick one with the header toggle. `system` follows the OS setting.'),
  colors: colorsSchema.prefault({}),
})

export type ThemeConfig = z.infer<typeof themeConfigSchema>

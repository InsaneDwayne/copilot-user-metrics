import { describe, expect, it } from 'vitest'
import { defaultTheme, resolveAssets } from './theme'

describe('resolveAssets', () => {
  const base = 'https://usage.example.com/theme/theme.json'

  it('resolves paths against the theme folder and leaves full URLs alone', () => {
    const theme = resolveAssets(
      {
        ...defaultTheme,
        logoUrl: 'logo.svg',
        faviconUrl: '/theme/favicon.svg',
        stylesheetUrl: 'css/theme.css',
        fontStylesheetUrl: 'https://fonts.example.com/inter.css',
      },
      base,
    )
    expect(theme.logoUrl).toBe('https://usage.example.com/theme/logo.svg')
    expect(theme.faviconUrl).toBe('https://usage.example.com/theme/favicon.svg')
    expect(theme.stylesheetUrl).toBe('https://usage.example.com/theme/css/theme.css')
    expect(theme.fontStylesheetUrl).toBe('https://fonts.example.com/inter.css')
    expect(theme.logoUrlDark).toBeNull()
  })
})

import { DesktopIcon, type Icon, MoonIcon, SunIcon } from '@phosphor-icons/react'
import type { ModePreference } from '@/config/themeSchema'
import { nextPreference, setModePreference, useThemeMode } from '@/shared/theme/mode'
import { Button } from '@/shared/components/ui/Button'

const OPTIONS: Record<ModePreference, { label: string; Icon: Icon }> = {
  system: { label: 'System', Icon: DesktopIcon },
  light: { label: 'Light', Icon: SunIcon },
  dark: { label: 'Dark', Icon: MoonIcon },
}

/** Cycles system → light → dark. The icon shows the current choice. */
export function ThemeToggle() {
  const { preference } = useThemeMode()
  const next = nextPreference(preference)
  const { label, Icon } = OPTIONS[preference]
  const title = `Theme: ${label} (switch to ${OPTIONS[next].label.toLowerCase()})`
  return (
    <Button variant="ghost" size="icon" title={title} aria-label={title} onClick={() => setModePreference(next)}>
      <Icon size={18} />
    </Button>
  )
}

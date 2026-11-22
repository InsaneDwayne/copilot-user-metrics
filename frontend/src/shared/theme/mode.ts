/**
 * Light / dark mode. The user's choice (`system`, `light` or `dark`) is kept in
 * localStorage, synced across tabs, and falls back to the theme's `defaultMode`.
 * index.html reads the same key before the first paint, so keep STORAGE_KEY in step.
 */
import { useSyncExternalStore } from 'react'
import { MODE_PREFERENCES, type ModePreference, type ThemeConfig, type ThemeMode } from '@/config/themeSchema'
import { applyMode } from './applyTheme'

const STORAGE_KEY = 'theme-mode'

export const resolveMode = (preference: ModePreference, systemPrefersDark: boolean): ThemeMode =>
  preference === 'system' ? (systemPrefersDark ? 'dark' : 'light') : preference

/** The toggle's cycle: system → light → dark → system. */
export const nextPreference = (preference: ModePreference): ModePreference =>
  MODE_PREFERENCES[(MODE_PREFERENCES.indexOf(preference) + 1) % MODE_PREFERENCES.length]

export interface ModeState {
  preference: ModePreference
  mode: ThemeMode
}

let defaultMode: ModePreference = 'system'
let state: ModeState = { preference: 'system', mode: 'dark' }
const listeners = new Set<() => void>()
const darkQuery = () => window.matchMedia('(prefers-color-scheme: dark)')

function readStored(): ModePreference | null {
  try {
    const value = localStorage.getItem(STORAGE_KEY)
    return MODE_PREFERENCES.includes(value as ModePreference) ? (value as ModePreference) : null
  } catch {
    return null // storage blocked (privacy mode, sandboxed frame)
  }
}

function update(preference: ModePreference): void {
  const mode = resolveMode(preference, darkQuery().matches)
  if (mode !== state.mode) applyMode(mode)
  state = { preference, mode }
  for (const listener of listeners) listener()
}

/** Resolves and applies the starting mode, then follows OS and other-tab changes. Call once, before rendering. */
export function initThemeMode(config: ThemeConfig): void {
  defaultMode = config.defaultMode
  const preference = readStored() ?? defaultMode
  state = { preference, mode: resolveMode(preference, darkQuery().matches) }
  applyMode(state.mode)
  darkQuery().addEventListener('change', () => state.preference === 'system' && update('system'))
  window.addEventListener('storage', (event) => {
    if (event.key === STORAGE_KEY) update(readStored() ?? defaultMode)
  })
}

export function setModePreference(preference: ModePreference): void {
  try {
    localStorage.setItem(STORAGE_KEY, preference)
  } catch {
    // Not persisted; still applies for this page view.
  }
  update(preference)
}

function subscribe(listener: () => void) {
  listeners.add(listener)
  return () => listeners.delete(listener)
}

export function useThemeMode(): ModeState {
  return useSyncExternalStore(subscribe, () => state)
}

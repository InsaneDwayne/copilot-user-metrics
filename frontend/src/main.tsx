import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { App } from '@/app/App'
import { themeConfig } from '@/config/theme'
import '@/shared/styles/index.css'
import { applyTheme } from '@/shared/theme/applyTheme'
import { initThemeMode } from '@/shared/theme/mode'

applyTheme(themeConfig)
initThemeMode(themeConfig)

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)

import { useState, type KeyboardEvent } from 'react'
import { clampIndex } from './chartMath'

/**
 * The data index the reader is inspecting, driven by pointer and keyboard alike:
 * focus the chart, then ←/→ step through it, Home/End jump to the ends, Esc clears.
 */
export function useChartCursor(count: number, startIndex: number) {
  const [active, setActive] = useState<number | null>(null)
  const clamp = (i: number) => clampIndex(i, count)

  const onKeyDown = (e: KeyboardEvent) => {
    const step = e.key === 'ArrowLeft' ? -1 : e.key === 'ArrowRight' ? 1 : 0
    if (step) setActive((a) => clamp((a ?? startIndex) + (e.shiftKey ? step * 7 : step)))
    else if (e.key === 'Home') setActive(0)
    else if (e.key === 'End') setActive(count - 1)
    else if (e.key === 'Escape') setActive(null)
    else return
    e.preventDefault()
  }

  return {
    active: active === null ? null : clamp(active),
    setActive: (i: number | null) => setActive(i === null ? null : clamp(i)),
    focusProps: {
      tabIndex: 0,
      onKeyDown,
      onFocus: () => setActive((a) => a ?? clamp(startIndex)),
      onBlur: () => setActive(null),
    },
  }
}

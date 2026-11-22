import { useLayoutEffect, useRef, useState } from 'react'

/** Width of the chart's box in CSS pixels, kept current as the layout changes. */
export function useChartWidth<T extends HTMLElement>() {
  const ref = useRef<T>(null)
  const [width, setWidth] = useState(0)
  useLayoutEffect(() => {
    const el = ref.current
    if (!el) return
    setWidth(el.clientWidth)
    if (typeof ResizeObserver === 'undefined') return
    const observer = new ResizeObserver(([entry]) => setWidth(entry.contentRect.width))
    observer.observe(el)
    return () => observer.disconnect()
  }, [])
  return [ref, width] as const
}

/** A height that suits the plot's width: flatter on phones, taller on wide screens (240–420 px). */
export const fluidChartHeight = (width: number) => Math.round(Math.min(420, Math.max(240, width * 0.24)))

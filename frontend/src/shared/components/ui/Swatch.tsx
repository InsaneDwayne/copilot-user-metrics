import { cn } from '@/shared/utils/cn'

/** A small colour key (legends, model rows). Colour it with a background class, e.g. `bg-series-1`. */
export function Swatch({ className }: { className?: string }) {
  return <span className={cn('inline-block size-2.5 flex-none rounded-swatch bg-meter', className)} />
}

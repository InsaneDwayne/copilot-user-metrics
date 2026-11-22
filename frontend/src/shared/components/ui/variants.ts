/**
 * Class recipes for elements that are rendered by more than one tag (a button
 * can be a <button>, a <Link> or an <a>). Components live next to this file.
 */
import { cn } from '@/shared/utils/cn'

export type ButtonVariant = 'primary' | 'secondary' | 'ghost'
export type ButtonSize = 'sm' | 'md' | 'lg' | 'icon'

const BUTTON_VARIANTS: Record<ButtonVariant, string> = {
  primary: 'border-accent text-accent hover:bg-accent/12 active:bg-accent/22',
  secondary: 'border-divider text-fg hover:bg-fg/7 active:bg-fg/14',
  ghost: 'text-accent hover:bg-accent/10 active:bg-accent/18',
}

const BUTTON_SIZES: Record<ButtonSize, string> = {
  sm: 'px-2 py-1 text-sm',
  md: 'px-2.5 py-1.5 text-base',
  lg: 'px-4.5 py-2.5 text-md',
  icon: 'size-9 p-0',
}

export function buttonClass(variant: ButtonVariant = 'secondary', size: ButtonSize = 'md', className?: string) {
  return cn(
    'inline-flex items-center justify-center gap-1.5 rounded-md border border-transparent leading-tight font-medium whitespace-nowrap',
    'no-underline transition-colors disabled:cursor-not-allowed disabled:opacity-45',
    BUTTON_VARIANTS[variant],
    BUTTON_SIZES[size],
    variant === 'ghost' && size !== 'icon' && 'px-1', // ghost buttons sit inline with text
    className,
  )
}

export const inputClass = cn(
  'min-h-9 w-full rounded-md border border-divider bg-surface px-2.5 py-1.5 text-base text-fg caret-accent',
  'hover:border-fg/45 focus-visible:border-accent focus-visible:outline-offset-0',
)

export type Tone = 'accent' | 'neutral' | 'outline'

const TAG_TONES: Record<Tone, string> = {
  accent: 'bg-tint text-on-tint',
  neutral: 'bg-chip text-on-chip',
  outline: 'border border-accent text-accent',
}

export const tagClass = (tone: Tone, className?: string) =>
  cn('inline-flex items-center gap-1 rounded-tag px-2.5 py-0.5 text-2xs tracking-[0.02em]', TAG_TONES[tone], className)

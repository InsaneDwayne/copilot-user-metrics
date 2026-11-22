import { extendTailwindMerge } from 'tailwind-merge'

/**
 * Joins class names and lets later Tailwind classes win over earlier ones
 * (`cn('p-5', 'p-4')` → `'p-4'`), so components accept a `className` override.
 * The custom type scale, radii and shadows from shared/styles/index.css are registered
 * so tailwind-merge doesn't mistake `text-sm` for a colour or drop a shadow.
 */
const merge = extendTailwindMerge({
  extend: {
    theme: {
      text: ['micro', '2xs', 'xs', 'sm', 'base', 'md', 'lead', 'lg', 'xl', '2xl', 'title', '4xl'],
      radius: ['swatch', 'tag'],
      shadow: ['hairline', 'raised'],
    },
  },
})

export type ClassValue = string | false | null | undefined

export const cn = (...classes: ClassValue[]) => merge(...classes)

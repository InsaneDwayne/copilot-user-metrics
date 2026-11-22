import type { ReactNode } from 'react'
import { Brand } from '@/shared/components/Brand'
import { ThemeToggle } from '@/shared/components/ThemeToggle'
import { Tag } from '@/shared/components/ui/Tag'
import { cn } from '@/shared/utils/cn'
import { useAppConfig } from '@/features/app-config'

/**
 * The pages outside the app (sign-in, no access): the app's header, with the content centered
 * below it. Same shell as the app (width, gutters, header height), so moving between these pages
 * and the app doesn't shift the brand.
 */
export function CenteredLayout({ children, className }: { children: ReactNode; className?: string }) {
  const org = useAppConfig().data?.org

  return (
    <div className="mx-auto flex min-h-dvh w-full max-w-page flex-col px-4 sm:px-6 lg:px-8">
      <header className="flex min-h-15 items-center gap-3 py-2">
        <Brand />
        {org && <Tag className="hidden sm:inline-flex">{org}</Tag>}
        <div className="ml-auto">
          <ThemeToggle />
        </div>
      </header>

      <main className="grid flex-1 place-items-center py-10 sm:pb-[12vh]">
        <div className={cn('flex w-full max-w-105 flex-col gap-4', className)}>{children}</div>
      </main>
    </div>
  )
}

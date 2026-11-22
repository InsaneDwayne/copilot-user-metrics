import { ChartBarIcon, CpuIcon, GithubLogoIcon, type Icon, ReceiptIcon } from '@phosphor-icons/react'
import { useState } from 'react'
import { Navigate, useSearchParams } from 'react-router'
import { Banner } from '@/shared/components/ui/Banner'
import { Surface } from '@/shared/components/ui/Surface'
import { buttonClass } from '@/shared/components/ui/variants'
import { useAppConfig } from '@/features/app-config'
import { signInHref } from '@/features/session/api/session'
import { CenteredLayout } from '@/features/session/components/CenteredLayout'
import { homePath } from '@/features/session/utils/homePath'
import { useSession } from '@/features/session/hooks/useSession'

const ERRORS: Record<string, string> = {
  state: 'Sign-in expired or was started in another tab. Please try again.',
  github: 'GitHub sign-in failed. Please try again.',
}

const HIGHLIGHTS: { icon: Icon; label: string }[] = [
  { icon: ChartBarIcon, label: 'AI credits per day' },
  { icon: CpuIcon, label: 'Models you use' },
  { icon: ReceiptIcon, label: 'Included vs billed' },
]

export function SignInPage() {
  const session = useSession()
  const org = useAppConfig().data?.org ?? 'your organization'
  const [params] = useSearchParams()
  const [redirecting, setRedirecting] = useState(false)
  const error = ERRORS[params.get('signin_error') ?? '']

  if (session.data) return <Navigate to={homePath(session.data)} replace />

  return (
    <CenteredLayout>
      <Surface className="gap-6 p-6 sm:p-8">
        <div className="flex flex-col gap-2.5">
          <h1 className="text-title text-pretty">See your own Copilot usage</h1>
          <p className="text-pretty text-fg-muted">
            AI credits, models and cost for your seat in <span className="text-fg">{org}</span>, day by day.
          </p>
        </div>

        <ul className="flex flex-col gap-2.5 text-sm">
          {HIGHLIGHTS.map(({ icon: Glyph, label }) => (
            <li key={label} className="flex items-center gap-2.5">
              <span className="grid size-7 flex-none place-items-center rounded-md text-accent inset-ring inset-ring-line">
                <Glyph aria-hidden />
              </span>
              {label}
            </li>
          ))}
        </ul>

        {error && (
          <Banner role="alert" className="mb-0">
            {error}
          </Banner>
        )}

        <div className="flex flex-col gap-2.5">
          <a
            className={buttonClass('primary', 'lg', 'w-full')}
            href={signInHref()}
            onClick={() => setRedirecting(true)}
            aria-busy={redirecting}
          >
            <GithubLogoIcon size={18} />
            {redirecting ? 'Redirecting to GitHub…' : 'Sign in with GitHub'}
          </a>
          <p className="text-center text-xs text-fg-subtle">You only ever see your own data.</p>
        </div>
      </Surface>
      <p className="px-2 text-center text-xs text-pretty text-fg-subtle">
        For GitHub.com organizations on Copilot Business. No Enterprise account needed.
      </p>
    </CenteredLayout>
  )
}

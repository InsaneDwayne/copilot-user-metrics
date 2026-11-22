import { SignOutIcon } from '@phosphor-icons/react'
import { Avatar } from '@/shared/components/ui/Avatar'
import { Button } from '@/shared/components/ui/Button'
import { useSession } from '@/features/session/hooks/useSession'
import { useSignOut } from '@/features/session/hooks/useSignOut'

export function UserMenu() {
  const { data: session } = useSession()
  const signOut = useSignOut()
  if (!session) return null
  return (
    <>
      <Avatar login={session.login} name={session.name} url={session.avatar_url} />
      <Button
        size="icon"
        title="Sign out"
        aria-label="Sign out"
        onClick={() => signOut.mutate()}
        disabled={signOut.isPending}
      >
        <SignOutIcon />
      </Button>
    </>
  )
}

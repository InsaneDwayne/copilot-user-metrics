import { initials } from '@/shared/utils/format'

interface AvatarProps {
  login: string
  name?: string | null
  url?: string | null
  size?: number
}

export function Avatar({ login, name, url, size = 28 }: AvatarProps) {
  return (
    <span
      className="grid flex-none place-items-center overflow-hidden rounded-full bg-tint text-2xs text-on-tint"
      style={{ width: size, height: size }}
      title={`@${login}`}
    >
      {url ? <img src={url} alt="" className="size-full object-cover" /> : initials(name ?? login)}
    </span>
  )
}

/** Avatar and @login side by side, as in member lists. */
export function Person({ login, url }: { login: string; url?: string | null }) {
  return (
    <span className="inline-flex items-center gap-2.5">
      <Avatar login={login} url={url} />@{login}
    </span>
  )
}

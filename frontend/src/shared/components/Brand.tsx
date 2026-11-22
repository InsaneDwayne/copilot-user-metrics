import { RobotIcon } from '@phosphor-icons/react'
import { Link } from 'react-router'
import { themeConfig } from '@/config/theme'

/**
 * The header's logo and app name, from theme.json. A theme logo is shown as is, at the
 * header height (its own width); the built-in mark is the robot in an accent frame.
 */
export function Brand({ size = 28 }: { size?: number }) {
  const { appName, showAppName, logoUrl, logoUrlDark } = themeConfig
  // With the name hidden, the logo is the link's only content, so it carries the name.
  const alt = showAppName ? '' : appName
  const logoStyle = { height: size }
  return (
    <Link to="/" className="flex items-center gap-2.5 text-md font-medium text-fg no-underline">
      {logoUrl ? (
        <>
          <img src={logoUrl} alt={alt} className={logoUrlDark ? 'w-auto dark:hidden' : 'w-auto'} style={logoStyle} />
          {logoUrlDark && <img src={logoUrlDark} alt={alt} className="hidden w-auto dark:block" style={logoStyle} />}
        </>
      ) : (
        <span
          className="grid place-items-center rounded-md text-lead text-accent inset-ring inset-ring-accent"
          style={{ width: size, height: size }}
          aria-hidden={showAppName}
        >
          <RobotIcon aria-label={showAppName ? undefined : appName} />
        </span>
      )}
      {showAppName && appName}
    </Link>
  )
}

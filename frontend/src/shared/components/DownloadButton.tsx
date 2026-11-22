import { DownloadSimpleIcon, WarningCircleIcon } from '@phosphor-icons/react'
import { useState } from 'react'
import { Button } from '@/shared/components/ui/Button'

interface DownloadButtonProps {
  /** Builds or fetches the file and saves it; a rejection is shown next to the button. */
  onDownload: () => void | Promise<void>
  title: string
  disabled?: boolean
  label?: string
}

/** The small secondary "CSV" button the tables share. */
export function DownloadButton({ onDownload, title, disabled, label = 'CSV' }: DownloadButtonProps) {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const run = async () => {
    setBusy(true)
    setError(null)
    try {
      await onDownload()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Download failed')
    } finally {
      setBusy(false)
    }
  }
  return (
    <span className="flex items-center gap-2">
      {error && (
        <span className="flex items-center gap-1 text-xs text-error" role="alert">
          <WarningCircleIcon aria-hidden />
          {error}
        </span>
      )}
      <Button
        variant="secondary"
        size="sm"
        className="text-xs"
        disabled={disabled || busy}
        aria-busy={busy}
        title={title}
        onClick={() => void run()}
      >
        <DownloadSimpleIcon aria-hidden />
        {label}
      </Button>
    </span>
  )
}

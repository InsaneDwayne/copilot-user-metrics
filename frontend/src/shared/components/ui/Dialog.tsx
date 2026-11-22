import { XIcon } from '@phosphor-icons/react'
import { useEffect, useId, useRef, type ReactNode } from 'react'
import { createPortal } from 'react-dom'
import { cn } from '@/shared/utils/cn'
import { Button } from './Button'

interface DialogProps {
  open: boolean
  onClose: () => void
  title: ReactNode
  /** Short explanation under the title. */
  description?: ReactNode
  children?: ReactNode
  /** Buttons, right-aligned at the bottom. */
  footer?: ReactNode
  className?: string
}

/**
 * The app's modal: a native <dialog> opened with showModal(), so the browser handles the
 * backdrop, focus trapping, Esc and returning focus to whatever opened it. Clicking the
 * backdrop closes it too. Use this (or ConfirmDialog) instead of window.alert/confirm/prompt.
 */
export function Dialog({ open, onClose, title, description, children, footer, className }: DialogProps) {
  const ref = useRef<HTMLDialogElement>(null)
  const titleId = useId()
  const descriptionId = useId()

  useEffect(() => {
    const dialog = ref.current
    if (!dialog) return
    if (open && !dialog.open) {
      dialog.showModal()
      // showModal() focuses the first focusable element (the close button); prefer the marked one.
      dialog.querySelector<HTMLElement>('[data-autofocus]')?.focus()
    }
    if (!open && dialog.open) dialog.close()
  }, [open])

  // Portalled to <body> so it never inherits layout or text styles from where it is opened (a table cell, say).
  return createPortal(
    <dialog
      ref={ref}
      aria-labelledby={titleId}
      aria-describedby={description ? descriptionId : undefined}
      // Esc fires `cancel`; let the parent decide by closing through state.
      onCancel={(e) => {
        e.preventDefault()
        onClose()
      }}
      // A click on the dialog element itself (not its content) is a click on the backdrop.
      onClick={(e) => e.target === e.currentTarget && onClose()}
      className={cn(
        'm-auto w-[calc(100%-2rem)] max-w-md rounded-lg bg-surface p-0 text-left text-fg shadow-raised',
        'backdrop:bg-canvas/70 backdrop:backdrop-blur-[2px]',
        'open:animate-[dialog-in_120ms_ease-out] motion-reduce:open:animate-none',
        className,
      )}
    >
      {open && (
        <div className="flex flex-col gap-4 p-5 sm:p-6">
          <div className="flex items-start gap-3">
            <div className="min-w-0 flex-1">
              <h2 id={titleId} className="text-lg leading-tight font-medium">
                {title}
              </h2>
              {description && (
                <p id={descriptionId} className="mt-1.5 text-sm text-pretty text-fg-muted">
                  {description}
                </p>
              )}
            </div>
            <Button variant="ghost" size="icon" className="-mt-1.5 -mr-2 size-8" aria-label="Close" onClick={onClose}>
              <XIcon />
            </Button>
          </div>
          {children}
          {footer && <div className="flex flex-wrap justify-end gap-2">{footer}</div>}
        </div>
      )}
    </dialog>,
    document.body,
  )
}

interface ConfirmDialogProps {
  open: boolean
  title: ReactNode
  description: ReactNode
  confirmLabel: string
  /** Shown on the confirm button while the action runs. */
  busyLabel?: string
  busy?: boolean
  onConfirm: () => void
  onCancel: () => void
}

/** "Are you sure?" as a modal. Cancel has focus first, so Enter never confirms by accident. */
export function ConfirmDialog({
  open,
  title,
  description,
  confirmLabel,
  busyLabel,
  busy = false,
  onConfirm,
  onCancel,
}: ConfirmDialogProps) {
  return (
    <Dialog
      open={open}
      onClose={onCancel}
      title={title}
      description={description}
      footer={
        <>
          <Button data-autofocus onClick={onCancel} disabled={busy}>
            Cancel
          </Button>
          <Button variant="primary" onClick={onConfirm} disabled={busy}>
            {busy ? (busyLabel ?? confirmLabel) : confirmLabel}
          </Button>
        </>
      }
    />
  )
}

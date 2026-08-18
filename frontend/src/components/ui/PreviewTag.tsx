import { Archive, Ban, type LucideIcon } from 'lucide-react'
import { DEMO, type DemoState } from '../../api/client'
import { cn } from '../../lib/cn'

/**
 * Marks a spot in the preview where the running app would do more.
 *
 * Returns null unless VITE_DEMO is set, so this is provably invisible in the
 * desktop app and in local development — the caveat cannot leak into the real
 * product by accident.
 *
 * Only 'recorded' and 'unavailable' render. 'live' needs no tag: the whole
 * point is that it behaves normally, and badging it would imply otherwise.
 *
 * Muted on purpose. This has to be noticeable enough that a judge never
 * mistakes a recording for a live generation, and quiet enough that it does not
 * become the loudest thing on a screen it is only annotating.
 */
const ICON: Record<'recorded' | 'unavailable', LucideIcon> = {
  recorded: Archive,
  unavailable: Ban,
}

const LABEL: Record<'recorded' | 'unavailable', string> = {
  recorded: 'Recorded',
  unavailable: 'Not in preview',
}

export default function PreviewTag({
  state,
  children,
  className,
}: {
  state: DemoState
  /** The one-line explanation. Sits beside the pill, not inside it. */
  children?: React.ReactNode
  className?: string
}) {
  if (!DEMO || state === 'live') return null

  const Icon = ICON[state]
  return (
    <div className={cn('flex flex-wrap items-center gap-x-2 gap-y-1', className)}>
      <span
        className={cn(
          'inline-flex items-center gap-1 rounded border px-1.5 py-0.5 text-[11px] font-medium whitespace-nowrap',
          state === 'recorded'
            ? 'border-accent/40 text-accent'
            : 'border-line text-faint',
        )}
      >
        <Icon size={11} aria-hidden />
        {LABEL[state]}
      </span>
      {children && <span className="text-[11px] leading-snug text-faint">{children}</span>}
    </div>
  )
}

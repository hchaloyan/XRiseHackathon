import { Copy, Minus, Square, X, type LucideIcon } from 'lucide-react'
import { useEffect, useState } from 'react'
import { cn } from '../lib/cn'

/**
 * Caption buttons for the frameless window (run.py passes `frameless=True`).
 * These are the only way to minimize, maximize or close the app.
 *
 * VS Code's geometry: square 46×36 buttons, flush into the top-right corner,
 * no gap and no radius. Anything softer stops reading as window chrome and
 * starts reading as content. Only the glyph treatment is ours — hairline
 * strokes, faint until hovered, the accent glow the rest of the app already
 * uses for emphasis.
 */

declare global {
  interface Window {
    /** Injected by pywebview after first paint; absent in a browser. */
    pywebview?: {
      api: {
        minimize(): Promise<void>
        /** Toggles, and resolves to the new maximized state. */
        maximize(): Promise<boolean>
        maximized(): Promise<boolean>
        close(): Promise<void>
      }
    }
  }
}

export default function WindowControls({ className }: { className?: string }) {
  // pywebview announces the bridge with `pywebviewready`, which can fire before
  // or after React mounts — hence both the initial read and the listener. In a
  // browser (`run.py --browser`, `npm run dev`) it never fires, and the buttons
  // stay absent rather than present and dead.
  const [api, setApi] = useState(window.pywebview?.api)
  const [maximized, setMaximized] = useState(false)

  useEffect(() => {
    const onReady = () => setApi(window.pywebview?.api)
    window.addEventListener('pywebviewready', onReady)
    return () => window.removeEventListener('pywebviewready', onReady)
  }, [])

  // The window resizes, so this button is no longer the only thing that can
  // maximize it — Aero Snap, Win+Up and a double-click on the drag strip all
  // do, and run.py announces each one. Without this the icon would keep
  // answering for the last click rather than for the window.
  useEffect(() => {
    const onState = (e: Event) => setMaximized((e as CustomEvent<boolean>).detail)
    window.addEventListener('windowstate', onState)
    return () => window.removeEventListener('windowstate', onState)
  }, [])

  if (!api) return null

  return (
    <div className={cn('flex', className)}>
      <CaptionButton icon={Minus} label="Minimize" onClick={() => api.minimize()} />
      {/* Two offset squares for restore, one for maximize — the Windows
          convention, and Lucide's Copy is exactly that glyph.

          `sharp` only while the square is showing. Copy's back square is an
          outline whose corners are curves baked into the path, so squaring off
          its front rect alone would leave one glyph rounded at one corner and
          hard at the other. */}
      <CaptionButton
        icon={maximized ? Copy : Square}
        sharp={!maximized}
        label={maximized ? 'Restore' : 'Maximize'}
        onClick={() => api.maximize().then(setMaximized)}
      />
      {/* Lucide's glyphs don't fill their 24-unit box equally — X spans 12
          units against Square's 18 — so a shared `size` draws the close mark
          at two thirds the others. Sized up to match them optically. */}
      <CaptionButton icon={X} label="Close" size={20} danger onClick={() => api.close()} />
    </div>
  )
}

/** size × strokeWidth. Held constant so the rendered hairline stays ~0.7px
    however large a glyph has to be drawn to look the same weight as its
    neighbours. */
const HAIRLINE = 17.5

function CaptionButton({
  icon: Icon,
  label,
  size = 14,
  sharp,
  danger,
  onClick,
}: {
  icon: LucideIcon
  label: string
  size?: number
  /** Square off the glyph's corners. Every Lucide rect ships with rx=2. */
  sharp?: boolean
  danger?: boolean
  onClick: () => void
}) {
  return (
    <button
      type="button"
      aria-label={label}
      title={label}
      onClick={onClick}
      className={cn(
        'group grid h-9 w-12 place-items-center text-faint transition-colors duration-150',
        'focus-visible:ring-2 focus-visible:ring-accent focus-visible:outline-none focus-visible:ring-inset',
        // Close goes solid on hover, the way every OS does it. The other two
        // take the same 5% white overlay as any other interaction state.
        danger ? 'hover:bg-error hover:text-hi' : 'hover:bg-white/5 hover:text-accent',
      )}
    >
      {/* Thinner than any icon in the content below, because chrome should sit
          behind the data, not compete with it. */}
      <Icon
        size={size}
        strokeWidth={HAIRLINE / size}
        aria-hidden
        className={cn(
          'transition-[filter] duration-150',
          // rx is a real CSS property on SVG geometry in Chromium, so this
          // overrides the attribute Lucide bakes in — no forked icon needed.
          sharp && '[&_rect]:[rx:0]',
          !danger && 'group-hover:drop-shadow-[0_0_5px_var(--color-accent)]',
        )}
      />
    </button>
  )
}

import { useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { CalendarDays, ChevronLeft, ChevronRight } from 'lucide-react'
import { useDay } from '../lib/day'
import { cn } from '../lib/cn'

/**
 * Month grid over the days the dataset actually holds.
 *
 * Days with no production are rendered but not selectable — showing the month
 * with gaps tells the truth about the window's shape, where omitting them
 * silently would leave a supervisor wondering why the 12th cannot be picked.
 *
 * Not a modal: a popover anchored under the date in the header, dismissed by
 * clicking outside or pressing Escape.
 *
 * Lives in the app bar, which is also the window's title bar, so only the three
 * buttons below carry pointer-events-auto. Everything else here — the "(latest
 * on file)" note, the gaps, the padding — inherits `none` from the header grid
 * and falls through to the drag region behind it, which is what lets the window
 * be dragged by the bar around the picker rather than only beside it.
 *
 * The popover is portaled to <body> rather than rendered in place, and that is
 * load-bearing, not tidiness. The header carries backdrop-filter, which makes
 * it a backdrop root: a descendant's own backdrop-filter can only sample
 * within it, so an in-place popover blurs nothing and reads as flat tint. Out
 * at the body it samples the page and frosts properly, like the ask bar.
 */

const WEEKDAYS = ['M', 'T', 'W', 'T', 'F', 'S', 'S']

function iso(d: Date): string {
  // Local parts, not toISOString: that converts to UTC and rolls the date back
  // a day for anyone west of Greenwich.
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(
    d.getDate(),
  ).padStart(2, '0')}`
}

function parse(value: string): Date {
  const [y, m, d] = value.split('-').map(Number)
  return new Date(y, m - 1, d)
}

/** Viewport coords for the portaled popover, measured off the picker.
 *  clientWidth, not innerWidth: it excludes the scrollbar gutter, and so does
 *  the containing block a fixed element's `right` resolves against. innerWidth
 *  would shift the popover left by the gutter. */
function anchorTo(el: HTMLElement) {
  const r = el.getBoundingClientRect()
  return { top: r.bottom + 8, right: document.documentElement.clientWidth - r.right }
}

export default function DayPicker({ daysBehind = 0 }: { daysBehind?: number }) {
  const { day, setDay, days, latest } = useDay()
  const [open, setOpen] = useState(false)
  const [month, setMonth] = useState<Date | null>(null)
  const rootRef = useRef<HTMLDivElement>(null)
  const popRef = useRef<HTMLDivElement>(null)
  /** Taken when the popover opens, re-taken while it is open and the window
      resizes. */
  const [anchor, setAnchor] = useState<{ top: number; right: number } | null>(null)

  const selected = day ?? latest
  const selectable = new Set(days)

  useEffect(() => {
    if (!open) return
    // Taken once on open, so the popover would hang where the picker used to be
    // if the window were dragged narrower with the calendar showing.
    const onResize = () => rootRef.current && setAnchor(anchorTo(rootRef.current))
    window.addEventListener('resize', onResize)
    const onDown = (e: MouseEvent) => {
      // Both refs: the popover is portaled, so it is no longer inside rootRef
      // and a click on a date would otherwise read as a click outside.
      const target = e.target as Node
      if (!rootRef.current?.contains(target) && !popRef.current?.contains(target)) {
        setOpen(false)
      }
    }
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && setOpen(false)
    document.addEventListener('mousedown', onDown)
    document.addEventListener('keydown', onKey)
    return () => {
      window.removeEventListener('resize', onResize)
      document.removeEventListener('mousedown', onDown)
      document.removeEventListener('keydown', onKey)
    }
  }, [open])

  if (!selected) return <span className="text-[15px] text-muted">Loading…</span>

  const cursor = month ?? parse(selected)
  const year = cursor.getFullYear()
  const monthIndex = cursor.getMonth()
  const first = new Date(year, monthIndex, 1)
  const daysInMonth = new Date(year, monthIndex + 1, 0).getDate()
  // Monday-first: getDay() is Sunday-based, so Sunday's 0 becomes 6.
  const leading = (first.getDay() + 6) % 7

  const step = (delta: number) => setMonth(new Date(year, monthIndex + delta, 1))

  const jump = (delta: number) => {
    const i = days.indexOf(selected)
    const next = days[i + delta]
    if (next) setDay(next)
  }

  const index = days.indexOf(selected)

  return (
    <div ref={rootRef} className="relative flex items-center gap-1">
      {/* The dataset is a snapshot and does not advance on its own. Saying
          "latest" when the newest shift is days old would present stale numbers
          as current, which is the one thing a briefing must not do.

          It sits left of the arrows rather than inside the date button: the
          picker is right-anchored, so a note that appears and disappears out
          here extends leftward and leaves the controls where they were.

          The header's outer columns are 1fr each, so under about 1100px this
          note has nowhere left to extend and wraps onto two and then three
          lines, taking the whole app bar with it. Below xl it is dropped
          instead: the date is still on screen, and the briefing says the same
          thing in a sentence directly beneath the header. */}
      {day === null && (
        <span className="mr-1 hidden text-[12px] text-faint xl:inline">
          {daysBehind > 0 ? `(latest on file · ${daysBehind}d ago)` : '(latest)'}
        </span>
      )}

      <button
        type="button"
        onClick={() => jump(-1)}
        disabled={index <= 0}
        aria-label="Previous day"
        className="pointer-events-auto cursor-pointer rounded p-1 text-muted transition-colors duration-150 hover:bg-white/10 hover:text-hi disabled:cursor-default disabled:opacity-30"
      >
        <ChevronLeft size={15} aria-hidden />
      </button>

      <button
        type="button"
        onClick={() => {
          setAnchor(anchorTo(rootRef.current!))
          setMonth(parse(selected))
          setOpen((v) => !v)
        }}
        aria-expanded={open}
        className="pointer-events-auto flex cursor-pointer items-center gap-2 rounded px-2 py-1 text-[15px] text-muted transition-colors duration-150 hover:bg-white/10 hover:text-hi focus-visible:ring-2 focus-visible:ring-accent focus-visible:outline-none"
      >
        <CalendarDays size={15} aria-hidden className="text-faint" />
        {/* Fixed width, or the arrows shuffle every time the date changes —
            "Fri, Jul 3" and "Mon, May 11" are not the same width in a
            proportional face. 88px clears the widest of all 366 strings this
            format produces (86.75px, "Mon, May 11", Inter at 15px); re-measure
            if the size or format changes. tabular-nums holds the digits still
            within it. */}
        <span className="w-[88px] text-center tabular-nums">
          {parse(selected).toLocaleDateString(undefined, {
            weekday: 'short',
            day: 'numeric',
            month: 'short',
          })}
        </span>
      </button>

      <button
        type="button"
        onClick={() => jump(1)}
        disabled={index < 0 || index >= days.length - 1}
        aria-label="Next day"
        className="pointer-events-auto cursor-pointer rounded p-1 text-muted transition-colors duration-150 hover:bg-white/10 hover:text-hi disabled:cursor-default disabled:opacity-30"
      >
        <ChevronRight size={15} aria-hidden />
      </button>

      {open && anchor && createPortal(
        // Same recipe as the ask bar in its opened state — glass-bar,
        // rounded-2xl, and the accent border plus glow it takes on focus-within
        // — so the two things a supervisor opens mid-briefing announce
        // themselves the same way.
        <div
          ref={popRef}
          style={{ top: anchor.top, right: anchor.right }}
          className="glass-bar fixed z-50 w-72 rounded-2xl border border-accent/50 p-3 shadow-glow"
        >
          <div className="flex items-center justify-between">
            <button
              type="button"
              onClick={() => step(-1)}
              aria-label="Previous month"
              className="cursor-pointer rounded p-1 text-muted hover:bg-white/10 hover:text-hi"
            >
              <ChevronLeft size={14} aria-hidden />
            </button>
            <span className="text-xs font-medium text-hi">
              {first.toLocaleDateString(undefined, { month: 'long', year: 'numeric' })}
            </span>
            <button
              type="button"
              onClick={() => step(1)}
              aria-label="Next month"
              className="cursor-pointer rounded p-1 text-muted hover:bg-white/10 hover:text-hi"
            >
              <ChevronRight size={14} aria-hidden />
            </button>
          </div>

          <div className="mt-3 grid grid-cols-7 gap-1 text-center">
            {WEEKDAYS.map((w, i) => (
              <span key={i} className="label-caps text-faint">
                {w}
              </span>
            ))}
            {Array.from({ length: leading }, (_, i) => (
              <span key={`pad-${i}`} />
            ))}
            {Array.from({ length: daysInMonth }, (_, i) => {
              const value = iso(new Date(year, monthIndex, i + 1))
              const has = selectable.has(value)
              const isSelected = value === selected
              return (
                <button
                  key={value}
                  type="button"
                  disabled={!has}
                  onClick={() => {
                    setDay(value)
                    setOpen(false)
                  }}
                  className={cn(
                    'rounded py-1 text-[12px] transition-colors duration-150',
                    isSelected && 'bg-accent font-medium text-black',
                    !isSelected && has && 'cursor-pointer text-hi hover:bg-white/10',
                    // Present but unselectable: the window has no data here.
                    !has && 'text-faint/40',
                  )}
                >
                  {i + 1}
                </button>
              )
            })}
          </div>

          {latest && (
            <button
              type="button"
              onClick={() => {
                setDay(latest)
                setOpen(false)
              }}
              className="mt-3 w-full cursor-pointer rounded border border-line py-1.5 text-[12px] text-muted transition-colors duration-150 hover:bg-white/10 hover:text-hi"
            >
              Jump to most recent
            </button>
          )}
        </div>,
        document.body,
      )}
    </div>
  )
}

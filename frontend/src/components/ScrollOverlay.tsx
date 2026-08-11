import { useEffect, useRef, useState } from 'react'
import { cn } from '../lib/cn'

/**
 * The page's scroll pill, drawn over the content instead of beside it.
 *
 * A native scrollbar reserves a column, and the edge of that column shows
 * against the header glass as a channel running the height of the window.
 * Chromium only offers true overlay scrollbars behind a flag, so the native
 * page bar is zero-width in index.css and the thumb is drawn here: fixed,
 * floating, reserving nothing.
 *
 * This is geometry and dragging only. The wheel, trackpad, keyboard and
 * anchor jumps all still drive the real scroller — nothing here intercepts
 * scrolling, it only reflects and nudges it.
 */

/** Clears the app bar with room to spare. The header measures ~79.5px since it
    started reserving a row for the caption buttons, so this leaves a deliberate
    gap rather than butting the cap against its edge. */
const TOP = 88
const BOTTOM = 16
/** Fixed length, not proportional to content. A normal scrollbar's thumb gets
    longer as the page gets shorter, which on these screens ran to half the
    window; a constant capsule stays a capsule. The cost is that it no longer
    hints at how much content there is — it marks position only. Kept in step
    with the h-11 on the node below. */
const THUMB = 44

export default function ScrollOverlay() {
  const thumb = useRef<HTMLDivElement>(null)
  /** Written by measure(), read by the drag handler — never rendered, so it
      stays a ref and doesn't re-render the tree on every scroll frame. */
  const geom = useRef({ maxScroll: 0, travel: 0 })
  const [scrollable, setScrollable] = useState(false)
  const [dragging, setDragging] = useState(false)

  useEffect(() => {
    // Position is written straight to the node rather than through state:
    // this runs on every scroll frame, and a re-render per frame is both more
    // code and slower than one style write. Height is a class now that the
    // capsule is a fixed length, so only the transform changes per frame.
    const measure = () => {
      const node = thumb.current
      if (!node) return

      const clientH = window.innerHeight
      const maxScroll = document.documentElement.scrollHeight - clientH
      const travel = clientH - TOP - BOTTOM - THUMB

      // A page that fits needs no pill, and neither does a window too short to
      // give the capsule anywhere to travel. The node stays mounted and fades
      // out, so the next measure can still find it.
      if (maxScroll <= 1 || travel <= 0) {
        geom.current = { maxScroll: 0, travel: 0 }
        setScrollable(false)
        return
      }

      geom.current = { maxScroll, travel }
      node.style.transform = `translateY(${(window.scrollY / maxScroll) * travel}px)`
      setScrollable(true)
    }

    measure()
    window.addEventListener('scroll', measure, { passive: true })
    window.addEventListener('resize', measure)
    // Rows expanding and the ask bar answering both change the page height
    // without a scroll or resize event.
    const observer = new ResizeObserver(measure)
    observer.observe(document.body)

    return () => {
      window.removeEventListener('scroll', measure)
      window.removeEventListener('resize', measure)
      observer.disconnect()
    }
  }, [])

  /** Pointer capture keeps the drag alive past the edge of an 8px target. */
  function onPointerDown(e: React.PointerEvent<HTMLDivElement>) {
    const { maxScroll, travel } = geom.current
    if (travel <= 0) return

    e.preventDefault() // no text selection while dragging
    const node = e.currentTarget
    const startY = e.clientY
    const startScroll = window.scrollY
    node.setPointerCapture(e.pointerId)
    setDragging(true)

    const onMove = (ev: PointerEvent) => {
      // Thumb travel maps to scroll range, so the content keeps pace with the
      // cursor however long the page is.
      window.scrollTo({ top: startScroll + ((ev.clientY - startY) / travel) * maxScroll })
    }
    const onUp = (ev: PointerEvent) => {
      node.releasePointerCapture(ev.pointerId)
      node.removeEventListener('pointermove', onMove)
      node.removeEventListener('pointerup', onUp)
      setDragging(false)
    }
    node.addEventListener('pointermove', onMove)
    node.addEventListener('pointerup', onUp)
  }

  return (
    // Two elements, not one: the outer box is the 16px grab target, because a
    // 6px pill is genuinely hard to catch with a mouse. The glass lives on the
    // inner one alone — backdrop-filter applies to the whole border box and
    // ignores bg-clip, so blurring the outer would smear a 16px ghost either
    // side of a 6px mark.
    <div
      ref={thumb}
      onPointerDown={onPointerDown}
      // Duplicates scrolling a screen reader already has; nothing here is the
      // only route to anything.
      aria-hidden
      style={{ top: TOP }}
      className={cn(
        // h-11 is THUMB above — change both together.
        'group fixed right-0 z-50 flex h-11 w-5 justify-center transition-opacity duration-150',
        scrollable ? 'opacity-100' : 'pointer-events-none opacity-0',
      )}
    >
      <div
        className={cn(
          'h-full w-2.5 rounded-full transition-colors duration-150',
          // Actual glass rather than flat translucency: it refracts the page
          // behind it, and the inset hairline catches the light along the top
          // edge the way every other surface in the app does.
          'backdrop-blur-md backdrop-saturate-150',
          'shadow-[inset_0_1px_0_rgb(255_255_255/0.3)]',
          dragging ? 'bg-white/32' : 'bg-white/15 group-hover:bg-white/25',
        )}
      />
    </div>
  )
}

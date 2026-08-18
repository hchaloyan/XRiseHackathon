import { useEffect, type MouseEvent as ReactMouseEvent } from 'react'
import { Activity } from 'lucide-react'
import { NavLink, Outlet, Route, Routes, useOutletContext } from 'react-router'
import { api, DEMO, DEMO_CAPABILITIES } from './api/client'
import type { KpiResponse } from './api/types'
import DayPicker from './components/DayPicker'
import ScrollOverlay from './components/ScrollOverlay'
import { cn } from './lib/cn'
import { DayProvider, useDay } from './lib/day'
import { useFetch } from './lib/useFetch'
import AskBar from './sections/AskBar'
import DocumentsPanel from './sections/DocumentsPanel'
import EventTable from './sections/EventTable'
import InsightHeader from './sections/InsightHeader'
import InventoryPanel from './sections/InventoryPanel'
import KpiGrid, { MachineRanking } from './sections/KpiGrid'
import WindowControls from './sections/WindowControls'

/**
 * Two screens behind react-router, at the user's explicit direction. This is a
 * deliberate override of CLAUDE.md rule 7 ("one screen, no react-router").
 *
 * What rule 7 actually protects is still intact: root cause expands INLINE
 * inside the event table, and the ask bar is fixed to the viewport on both
 * screens — so insight → drill-down → answer never navigates away.
 *
 * /api/kpis is fetched once in the layout and handed to both screens through
 * the outlet, so switching screens costs nothing and refetches nothing.
 */

interface KpiContext {
  kpis: KpiResponse | null
  loading: boolean
  /** ISO date, or null for the newest day. */
  day: string | null
  /** How far the newest record lags the real calendar. 0 when up to date. */
  daysBehind: number
}

const useKpiContext = () => useOutletContext<KpiContext>()

const NAV = [
  { to: '/', label: 'Briefing' },
  { to: '/metrics', label: 'Metrics' },
  { to: '/documents', label: 'Documents' },
]

export default function App() {
  return (
    <DayProvider>
      <Routes>
        <Route element={<Shell />}>
          <Route index element={<BriefingScreen />} />
          <Route path="metrics" element={<MetricsScreen />} />
          <Route path="documents" element={<DocumentsPanel />} />
          {/* A stray URL lands on the briefing rather than a blank screen. */}
          <Route path="*" element={<BriefingScreen />} />
        </Route>
      </Routes>
    </DayProvider>
  )
}

/**
 * Windows restores a maximized window the moment its title bar is dragged, and
 * pywebview's drag region only ever moves the window — so the restore is ours.
 *
 * It waits for real movement rather than firing on mousedown: a plain click on
 * the bar, and the first half of the double-click that maximizes, must not
 * resize the app. Nothing else changes — pywebview's own mousemove handler goes
 * on placing the window under the cursor, at whatever size it now has.
 */
function restoreOnDrag(e: ReactMouseEvent) {
  const { screenX, screenY } = e

  const onMove = (move: MouseEvent) => {
    if (Math.hypot(move.screenX - screenX, move.screenY - screenY) < 8) return
    stop()
    const chrome = window.pywebview?.api
    // Asked rather than tracked: Aero Snap and Win+Up maximize without telling
    // the page, and restoring an already-restored window would move it.
    void chrome?.maximized().then((isMax) => isMax && chrome.maximize())
  }
  const stop = () => {
    window.removeEventListener('mousemove', onMove)
    window.removeEventListener('mouseup', stop)
  }

  window.addEventListener('mousemove', onMove)
  window.addEventListener('mouseup', stop)
}

function Shell() {
  const { day, setDays } = useDay()
  // Every fetch below is keyed on `day`, so changing it in the picker — or in
  // the ask bar's answer to "what was yesterday's OEE" — moves the whole
  // dashboard at once.
  const { data: kpis, loading } = useFetch(() => api.kpis(day), day ?? 'latest')
  const { data: dayList } = useFetch(api.days)

  useEffect(() => {
    if (dayList) setDays(dayList.days)
  }, [dayList, setDays])

  return (
    <div className="min-h-full">
      {/* App bar sits at 08dp — 12% white overlay — carried by glass, so the
          ambient light passes through it as content scrolls beneath.

          Overriding the token rather than the box-shadow: --shadow-glass opens
          with a lit hairline along the top edge, which every other glass
          surface wants and this one no longer can have. The window's 7px sizing
          frame is painted to match this bar (run.py), so the bar's own top edge
          is 7px inside the window — and the highlight drew a grey line across
          the middle of what should read as one continuous surface. Only the
          drop shadow is left. The token is inherited, so this reaches
          glass-bar's var() without depending on which utility Tailwind emits
          last, and nothing inside the header uses it. */}
      <header className="glass-bar sticky top-0 z-40 border-b border-line [--shadow-glass:0_8px_32px_-8px_rgb(0_0_0/0.5)]">
        {/* The window is frameless (run.py), so this bar IS the title bar.
            The drag strip is a layer BEHIND the content rather than a class on
            <header>: pywebview walks UP the DOM from whatever was clicked
            looking for the region, so tagging the header would make every nav
            tab drag the window instead of navigating.

            Being behind is only half of it — the grid below also has to stop
            swallowing the clicks. It covers the whole bar (full height, and a
            wordmark stretched across a 1fr column), so pointer-events-none
            hands the dead space back to the layer and only the controls opt
            back in. Without that, the drag area is just the margin outside
            max-w-7xl: fine maximized, gone the moment the window narrows.

            Double-click maximizes, the way every title bar does. The layer is
            the right place for it: the tabs and the date picker opt back into
            pointer events above, so a double-click on either of those never
            reaches here. */}
        <div
          className="pywebview-drag-region absolute inset-0"
          onMouseDown={restoreOnDrag}
          onDoubleClick={() => void window.pywebview?.api.maximize()}
        />
        <WindowControls className="absolute top-0 right-0 z-10" />

        {/* Three columns rather than a flex row: the centre column is optically
            centred on the page, not merely placed after the wordmark, and it
            stays centred whatever the date string's width turns out to be.
            items-end drops the tab underline onto the header's bottom edge, and
            the pb-* on each cell below is what holds the row off it.

            h-17 is the whole bar: 68px, the title bar and the nav in one band.

            The caption buttons are the other thing in this row, and they are
            overlaid rather than laid out — the grid stays centred on the WINDOW,
            so 168px of buttons in the flow would drag the wordmark and the tabs
            off centre by half that. Reserving the width instead: the centred
            max-w-7xl column clears them on its own once the window is wide
            enough (its right edge is at W/2+616, the buttons start at W-168, so
            they part at W=1584), and below that pr-44 holds the date picker
            clear of them. Both numbers are 3 × the button width in
            WindowControls — change one and change the other. */}
        <div className="pointer-events-none relative mx-auto grid h-17 max-w-7xl grid-cols-[1fr_auto_1fr] items-end gap-4 pr-44 pl-6 min-[1584px]:pr-6">
          <div className="flex items-center gap-3 pb-4">
            <Activity size={22} strokeWidth={2} className="text-accent" aria-hidden />
            <h1 className="text-xl leading-none font-semibold tracking-tight text-hi">
              MFGX <span className="text-accent-gradient">AI</span>
            </h1>
          </div>

          {/* Tabs, indicated by an underline rather than a filled pill.

              pointer-events is an inherited property, so the grid's `none`
              reaches every descendant and each control has to opt back in — the
              tabs here, the three buttons inside DayPicker. Deliberately at
              that grain rather than on the wrapper: the picker's "(latest on
              file)" note and the padding around it are text, not controls, and
              a wrapper-level opt-in made them a dead patch of bar that would
              not drag the window. Anything interactive added to this grid needs
              the same opt-in on the control itself. */}
          <nav className="pointer-events-auto flex items-center gap-2">
            {NAV.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.to === '/'}
                className={({ isActive }) =>
                  cn(
                    'border-b-2 px-4 pt-1 pb-3.5 text-[15px] font-medium transition-colors duration-150',
                    'focus-visible:ring-2 focus-visible:ring-accent focus-visible:outline-none',
                    isActive
                      ? 'border-accent text-accent'
                      : 'border-transparent text-muted hover:text-hi',
                  )
                }
              >
                {item.label}
              </NavLink>
            ))}
          </nav>

          <div className="justify-self-end pb-3.5">
            <DayPicker daysBehind={dayList?.daysBehind ?? 0} />
          </div>
        </div>
      </header>

      {/* Says what this is, once, at the top.
          A preview that looks live is worse than no preview. The hard case is
          not the parts that are switched off — those are obvious — it is the
          briefing narrative and the two root-cause rows, which replay real
          recorded model output and are indistinguishable from a live
          generation unless we say so. Hence three tiers rather than two, and
          hence the inline badges further down the page for anyone who scrolls
          straight past this. */}
      {DEMO && (
        <div className="border-b border-accent/30 bg-accent/10">
          <div className="mx-auto max-w-7xl px-6 py-2.5">
            <p className="text-[12px] text-hi">
              <span className="font-medium">Static preview.</span> There is no backend behind
              this page, so some of the app is running and some of it is a recording. Here is
              exactly which is which.
            </p>

            <ul className="mt-2 flex flex-wrap gap-x-5 gap-y-1.5">
              {DEMO_CAPABILITIES.map((c) => (
                <li key={c.name} className="flex items-center gap-1.5 text-[11px]">
                  <span
                    aria-hidden
                    className={cn(
                      'h-1.5 w-1.5 shrink-0 rounded-full',
                      c.state === 'live'
                        ? 'bg-positive'
                        : c.state === 'recorded'
                          ? 'bg-accent'
                          : 'bg-line',
                    )}
                  />
                  <span className="text-hi">{c.name}</span>
                  <span className="text-faint">— {c.note}</span>
                </li>
              ))}
            </ul>

            <p className="mt-2 text-[11px] text-faint">
              Green is really executing in your browser. Amber is genuine model output captured
              once and replayed. Grey needs a local model, a vector index or the file system.
              Clone the repo and run the desktop app to see all of it live.
            </p>
          </div>
        </div>
      )}

      {/* pb-40 keeps the last row clear of the fixed ask bar. */}
      <div className="mx-auto max-w-7xl px-6 pt-6 pb-40">
        <Outlet
          context={
            {
              kpis,
              loading,
              day,
              daysBehind: dayList?.daysBehind ?? 0,
            } satisfies KpiContext
          }
        />
      </div>

      {/* Persistent across both screens: never scrolled past, never navigated
          away from (CLAUDE.md capability 3). */}
      <AskBar />

      {/* The page's scroll pill. Drawn over the content because a native bar
          reserves a column whose edge shows against the header glass. */}
      <ScrollOverlay />
    </div>
  )
}

/** Narrative and the events it points at — the drill-down flow, intact. */
function BriefingScreen() {
  const { kpis, loading, day, daysBehind } = useKpiContext()
  return (
    <div className="space-y-4">
      {/* Said once, plainly, above the narrative — rather than letting a
          two-day-old shift read as this morning's. */}
      {day === null && daysBehind > 0 && (
        <p className="text-[12px] text-faint">
          No production reported since {kpis ? new Date(`${kpis.day}T00:00:00`).toLocaleDateString(
            undefined,
            { weekday: 'long', day: 'numeric', month: 'long' },
          ) : '—'}. Showing the most recent shift on file.
        </p>
      )}
      <InsightHeader day={day} kpis={kpis} />
      <EventTable events={kpis?.events ?? []} loading={loading} />
    </div>
  )
}

/** The numbers, with room to breathe. */
function MetricsScreen() {
  const { kpis, loading } = useKpiContext()
  return (
    <div className="space-y-4">
      <KpiGrid kpis={kpis} loading={loading} />
      <div className="grid gap-4 lg:grid-cols-3">
        <MachineRanking machines={kpis?.machines ?? []} className="lg:col-span-2" />
        <InventoryPanel inventory={kpis?.inventory ?? null} />
      </div>
    </div>
  )
}

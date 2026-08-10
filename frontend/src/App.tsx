import { Activity } from 'lucide-react'
import { NavLink, Outlet, Route, Routes, useOutletContext } from 'react-router'
import { api } from './api/client'
import type { KpiResponse } from './api/types'
import { cn } from './lib/cn'
import { shortDate } from './lib/format'
import { useFetch } from './lib/useFetch'
import AskBar from './sections/AskBar'
import EventTable from './sections/EventTable'
import InsightHeader from './sections/InsightHeader'
import InventoryPanel from './sections/InventoryPanel'
import KpiGrid, { MachineRanking } from './sections/KpiGrid'

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
}

const useKpiContext = () => useOutletContext<KpiContext>()

const NAV = [
  { to: '/', label: 'Briefing' },
  { to: '/metrics', label: 'Metrics' },
]

export default function App() {
  return (
    <Routes>
      <Route element={<Shell />}>
        <Route index element={<BriefingScreen />} />
        <Route path="metrics" element={<MetricsScreen />} />
        {/* A stray URL lands on the briefing rather than a blank screen. */}
        <Route path="*" element={<BriefingScreen />} />
      </Route>
    </Routes>
  )
}

function Shell() {
  const { data: kpis, loading } = useFetch(api.kpis)

  return (
    <div className="min-h-full">
      {/* App bar sits at 08dp — 12% white overlay — carried by glass, so the
          ambient light passes through it as content scrolls beneath. */}
      <header className="glass-bar sticky top-0 z-40 border-b border-line">
        {/* Three columns rather than a flex row: the centre column is optically
            centred on the page, not merely placed after the wordmark, and it
            stays centred whatever the date string's width turns out to be.
            items-end drops the tab underline onto the header's bottom edge. */}
        <div className="mx-auto grid max-w-7xl grid-cols-[1fr_auto_1fr] items-end gap-4 px-6 pt-7">
          <div className="flex items-center gap-3 pb-4">
            <Activity size={22} strokeWidth={2} className="text-accent" aria-hidden />
            <h1 className="text-xl leading-none font-semibold tracking-tight text-hi">
              MFGX <span className="text-accent-gradient">AI</span>
            </h1>
          </div>

          {/* Tabs, indicated by an underline rather than a filled pill. */}
          <nav className="flex items-center gap-2">
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

          <span className="justify-self-end pb-4 text-[15px] text-muted">
            {kpis ? shortDate(kpis.day) : 'Loading…'}
          </span>
        </div>
      </header>

      {/* pb-40 keeps the last row clear of the fixed ask bar. */}
      <div className="mx-auto max-w-7xl px-6 pt-6 pb-40">
        <Outlet context={{ kpis, loading } satisfies KpiContext} />
      </div>

      {/* Persistent across both screens: never scrolled past, never navigated
          away from (CLAUDE.md capability 3). */}
      <AskBar />
    </div>
  )
}

/** Narrative and the events it points at — the drill-down flow, intact. */
function BriefingScreen() {
  const { kpis, loading } = useKpiContext()
  return (
    <div className="space-y-4">
      <InsightHeader />
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

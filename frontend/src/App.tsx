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
    <div className="relative min-h-full overflow-x-hidden bg-void text-white">
      {/* Textured void: the darkness breathes rather than sitting flat. */}
      <div className="pointer-events-none absolute inset-0 bg-grid" aria-hidden />
      <div
        className="pointer-events-none absolute -top-40 left-1/2 size-[640px] -translate-x-1/2 rounded-full bg-btc opacity-10 blur-[140px]"
        aria-hidden
      />

      {/* pb-40 keeps the last row clear of the fixed ask bar. */}
      <div className="relative mx-auto max-w-7xl px-6 pt-8 pb-40">
        <header className="mb-6 flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <span className="rounded-lg border border-burnt/50 bg-burnt/20 p-2 text-btc">
              <Activity size={18} strokeWidth={2} />
            </span>
            <h1 className="font-heading text-lg leading-none font-semibold tracking-tight">
              MFGX <span className="text-gradient">AI</span>
            </h1>
          </div>

          <nav className="flex items-center gap-1 rounded-full border border-white/10 bg-white/5 p-1">
            {NAV.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.to === '/'}
                className={({ isActive }) =>
                  cn(
                    'rounded-full px-4 py-1.5 font-mono text-[11px] tracking-widest uppercase transition-all duration-300',
                    'focus-visible:ring-2 focus-visible:ring-btc focus-visible:outline-none',
                    isActive
                      ? 'bg-gradient-to-r from-burnt to-btc text-white shadow-glow-orange'
                      : 'text-muted hover:text-white',
                  )
                }
              >
                {item.label}
              </NavLink>
            ))}
          </nav>

          <span className="label-caps text-lg">{kpis ? shortDate(kpis.day) : 'Loading…'}</span>
        </header>

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

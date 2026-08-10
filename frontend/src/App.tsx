import AskBar from './sections/AskBar'
import InsightHeader from './sections/InsightHeader'
import KpiGrid from './sections/KpiGrid'
import EventTable from './sections/EventTable'

/**
 * One screen. No router, no tabs, no modals (CLAUDE.md rule 7).
 * Root cause expands inline inside EventTable; it is not a separate view.
 */
export default function App() {
  return (
    <div className="min-h-full bg-slate-50 text-slate-900">
      <div className="mx-auto max-w-6xl space-y-6 px-6 py-8">
        <AskBar />
        <InsightHeader />
        <KpiGrid />
        <EventTable />
      </div>
    </div>
  )
}

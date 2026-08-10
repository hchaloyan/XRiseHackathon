/**
 * KPI cards + Recharts trends -> GET /api/kpis.
 * Every number here is computed in pandas, never by the model (rule 1).
 */
export default function KpiGrid() {
  return (
    <section className="grid grid-cols-2 gap-4 lg:grid-cols-4">
      {['OEE', 'Availability', 'Scrap Rate', 'Downtime'].map((label) => (
        <div key={label} className="rounded-lg border border-slate-200 bg-white p-4">
          <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">
            {label}
          </div>
          <div className="mt-1 text-2xl font-semibold text-slate-300">—</div>
        </div>
      ))}
    </section>
  )
}

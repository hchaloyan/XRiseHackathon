/**
 * Downtime + quality rows. Each row expands IN PLACE into RootCausePanel
 * (rule 7) -> POST /api/root-cause. Data questions are answered by clicking
 * a row, never by typing in the ask bar.
 */
export default function EventTable() {
  return (
    <section className="rounded-lg border border-slate-200 bg-white p-5">
      <h2 className="text-xs font-semibold uppercase tracking-wide text-slate-500">
        Downtime &amp; Quality Events
      </h2>
      <p className="mt-2 text-sm text-slate-400">Not wired yet.</p>
    </section>
  )
}

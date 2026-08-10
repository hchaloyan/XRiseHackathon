/**
 * Generated narrative -> GET /api/insights. Fires on page open (spec D2).
 * Needs a loading skeleton: generation takes ~6-10s and the user is watching.
 * Narrative is nullable; render nothing in this slot if it comes back null.
 */
export default function InsightHeader() {
  return (
    <section className="rounded-lg border border-slate-200 bg-white p-5">
      <h2 className="text-xs font-semibold uppercase tracking-wide text-slate-500">
        Today's Briefing
      </h2>
      <p className="mt-2 text-sm text-slate-400">Not wired yet.</p>
    </section>
  )
}

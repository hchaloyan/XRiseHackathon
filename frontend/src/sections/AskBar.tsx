/**
 * Persistent ask bar -> POST /api/search. Documents only (CLAUDE.md rule 8).
 * No intent routing. Low-similarity results get the fixed redirect string
 * from spec 7.1 rather than a wrong answer.
 */
export default function AskBar() {
  return (
    <section className="rounded-lg border border-slate-200 bg-white p-4">
      <input
        disabled
        placeholder="Ask about SOPs, manuals, and audit documents…"
        className="w-full rounded-md border border-slate-200 px-3 py-2 text-sm outline-none"
      />
    </section>
  )
}

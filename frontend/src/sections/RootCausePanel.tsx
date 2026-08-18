import { CircleAlert, FileText, Lightbulb, Wrench } from 'lucide-react'
import { api, DEMO, DEMO_NOTES } from '../api/client'
import type { Evidence, EventContext, EventRow, RootCauseResponse } from '../api/types'
import { Badge } from '../components/ui/Badge'
import Analysing from '../components/ui/Analysing'
import PreviewTag from '../components/ui/PreviewTag'
import { clockTime, humanizeCode, minutes } from '../lib/format'
import { useFetch } from '../lib/useFetch'

/**
 * Inline expansion of an EventTable row. Never a modal, never a route.
 * Shows the single most likely cause with the evidence it rests on. The model
 * still returns a ranked list; only the top one is surfaced.
 *
 * The panel drops to the 00dp base surface while the card around it sits at
 * 01dp, so the expansion reads as opening *into* the row rather than floating
 * above it.
 *
 * Hypotheses are nullable: if the model fails, the row still shows its
 * computed evidence and simply omits the cause (spec §5).
 */

/** Analysis is slow and expensive; a collapsed-then-reopened row must not
 *  pay for it twice mid-demo. */
const cache = new Map<string, RootCauseResponse>()

/**
 * Everything here comes off the row we already hold. No correlation, no
 * hypotheses — showing another machine's findings would be worse than
 * showing fewer.
 */
function fromRowAlone(event: EventRow): RootCauseResponse {
  const evidence: Evidence[] = [
    {
      label: 'Machine',
      value: `${event.machineName} (${event.machineId})`,
      detail: event.machineType,
    },
    {
      label: 'Line and shift',
      value: `${event.line} · Shift ${event.shift}`,
      detail: null,
    },
    {
      label: 'Started',
      value: clockTime(event.start),
      detail: event.start.slice(0, 10),
    },
  ]

  if (event.kind === 'downtime') {
    evidence.push({
      label: 'Stoppage',
      value: event.durationMinutes !== null ? minutes(event.durationMinutes) : '—',
      detail: event.reasonCode ? humanizeCode(event.reasonCode) : null,
    })
    if (event.operatorNote) {
      evidence.push({
        label: 'Operator note',
        value: event.operatorNote,
        detail: null,
      })
    }
  } else {
    evidence.push({
      label: 'Rejected units',
      value: event.defectCount !== null ? `${event.defectCount}` : '—',
      detail: event.defectType ? humanizeCode(event.defectType) : null,
    })
  }

  // The row already carries everything EventContext needs, so echo it back
  // rather than leaving the field out and diverging from the API shape.
  const context: EventContext = {
    eventId: event.eventId,
    kind: event.kind,
    machineId: event.machineId,
    machineName: event.machineName,
    machineType: event.machineType,
    line: event.line,
    start: event.start,
    shift: event.shift,
    durationMinutes: event.durationMinutes,
    reasonCode: event.reasonCode,
    operatorNote: event.operatorNote,
    defectType: event.defectType,
    defectCount: event.defectCount,
  }

  // No retrieval ran, so there is nothing honest to cite.
  return {
    eventId: event.eventId,
    event: context,
    evidence,
    sources: [],
    hypotheses: null,
    summary: null,
  }
}

async function loadRootCause(event: EventRow): Promise<RootCauseResponse> {
  const hit = cache.get(event.eventId)
  if (hit) return hit

  let result: RootCauseResponse
  try {
    result = await api.rootCause(event.eventId)
  } catch {
    result = fromRowAlone(event)
  }
  cache.set(event.eventId, result)
  return result
}

export default function RootCausePanel({ event }: { event: EventRow }) {
  const { data, loading } = useFetch(() => loadRootCause(event))

  // While the model works, render the evidence taken straight off the row.
  // It is real, it is instant, and it is a subset of what the response will
  // carry — so the panel fills immediately and then deepens, rather than
  // showing a skeleton for ten seconds and snapping into place.
  const shown = data ?? fromRowAlone(event)

  // Lowest rank wins rather than array position, so an unsorted response from
  // the model still surfaces the right one.
  const top = data?.hypotheses?.length
    ? [...data.hypotheses].sort((a, b) => a.rank - b.rank)[0]
    : null

  return (
    <div className="border-t border-line bg-black/25 px-5 py-5">
      {/* Computed. Always renders — from the row while loading, from the
          response once it lands. */}
      <div className="flex items-center gap-2">
        <CircleAlert size={13} className="text-muted" aria-hidden />
        <h4 className="label-caps">Evidence</h4>
      </div>

      <dl className="mt-3 grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
        {shown.evidence.map((e) => (
          <div key={e.label} className="rounded-lg border border-white/5 bg-white/[0.05] px-3 py-2">
            <dt className="label-caps">{e.label}</dt>
            <dd className="data-figure mt-1 text-sm text-hi">{e.value}</dd>
            {e.detail && <p className="mt-1 text-[12px] leading-snug text-muted">{e.detail}</p>}
          </div>
        ))}
      </dl>

      {/* Generated. Progress while it runs, then the ranked cause. */}
      {loading ? (
        <>
          <div className="mt-6 flex items-center gap-2">
            <Lightbulb size={13} className="text-accent" aria-hidden />
            <h4 className="label-caps">Likely Cause</h4>
          </div>
          <Analysing className="mt-3" />
        </>
      ) : top ? (
        <>
          <div className="mt-6 flex items-center gap-2">
            <Lightbulb size={13} className="text-accent" aria-hidden />
            <h4 className="label-caps">Likely Cause</h4>
          </div>

          {/* Only reachable in the preview for the two rows that carry canned
              analysis, and those look exactly like a live ranking — so say
              which it is. Renders nothing in the real app. */}
          <PreviewTag state="recorded" className="mt-2">
            {DEMO_NOTES.rootCause}
          </PreviewTag>

          {/* The section's one accent-bearing element: a 2px lit rule and
                  a single glow. No accent fill behind the text. */}
          <div className="mt-3 rounded-r-lg border-l-2 border-accent bg-white/[0.05] p-4 shadow-glow">
            <div className="flex flex-wrap items-center gap-2.5">
              <h5 className="text-sm font-medium text-hi">{top.cause}</h5>
              <Badge tone={top.confidence}>{top.confidence} confidence</Badge>
            </div>

            <p className="mt-2.5 text-xs leading-relaxed text-muted">{top.reasoning}</p>

            {top.supportingEvidence.length > 0 && (
              <div className="mt-3 flex flex-wrap gap-1.5">
                {top.supportingEvidence.map((s) => (
                  <span
                    key={s}
                    className="data-figure rounded bg-white/[0.07] px-2 py-0.5 text-[11px] text-muted"
                  >
                    {s}
                  </span>
                ))}
              </div>
            )}

            {top.recommendedAction && (
              <div className="mt-3 flex gap-2 border-t border-line pt-3">
                <Wrench size={13} className="mt-0.5 shrink-0 text-accent" aria-hidden />
                <p className="text-xs leading-relaxed text-hi">{top.recommendedAction}</p>
              </div>
            )}
          </div>
        </>
      ) : DEMO ? (
        // In the preview this is the NORMAL outcome for 16 of the 18 rows, and
        // the generic "unavailable" line reads as a failure rather than as a
        // boundary. Name the reason instead.
        <PreviewTag state="unavailable" className="mt-4">
          {DEMO_NOTES.rootCauseMissing}
        </PreviewTag>
      ) : (
        <p className="mt-4 text-xs text-muted">
          Likely cause unavailable for this event. The computed evidence above is unaffected.
        </p>
      )}

      {/* Computed by retrieval, not written by the model — so a cited
              document always exists. This is the thread from a downtime row
              to the procedure that covers it. */}
      {!loading && data?.sources && data.sources.length > 0 && (
        <div className="mt-5 border-t border-line pt-3">
          <div className="flex items-center gap-2">
            <FileText size={13} className="text-muted" aria-hidden />
            <h4 className="label-caps">Referenced Procedures</h4>
          </div>
          <ul className="mt-2 flex flex-wrap gap-1.5">
            {data.sources.map((s) => (
              <li
                key={`${s.docId}-${s.section}`}
                className="rounded bg-white/[0.07] px-2 py-1 text-[11px] text-muted"
              >
                <span className="data-figure text-accent">{s.docId}</span>
                <span className="text-faint"> · </span>
                {s.section}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}

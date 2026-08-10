import { CircleAlert, Lightbulb, Wrench } from 'lucide-react'
import { api } from '../api/client'
import type { Evidence, EventRow, RootCauseResponse } from '../api/types'
import { Badge } from '../components/ui/Badge'
import { Skeleton, SkeletonLines } from '../components/ui/Skeleton'
import { clockTime, humanizeCode, minutes } from '../lib/format'
import { useFetch } from '../lib/useFetch'

/**
 * Inline expansion of an EventTable row. Never a modal, never a route.
 * Shows the single most likely cause with the evidence it rests on. The model
 * still returns a ranked list; only the top one is surfaced.
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
    { label: 'Machine', value: `${event.machineName} (${event.machineId})`, detail: event.machineType },
    { label: 'Line and shift', value: `${event.line} · Shift ${event.shift}`, detail: null },
    { label: 'Started', value: clockTime(event.start), detail: event.start.slice(0, 10) },
  ]

  if (event.kind === 'downtime') {
    evidence.push({
      label: 'Stoppage',
      value: event.durationMinutes !== null ? minutes(event.durationMinutes) : '—',
      detail: event.reasonCode ? humanizeCode(event.reasonCode) : null,
    })
    if (event.operatorNote) {
      evidence.push({ label: 'Operator note', value: event.operatorNote, detail: null })
    }
  } else {
    evidence.push({
      label: 'Rejected units',
      value: event.defectCount !== null ? `${event.defectCount}` : '—',
      detail: event.defectType ? humanizeCode(event.defectType) : null,
    })
  }

  return { eventId: event.eventId, evidence, hypotheses: null }
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

  // Lowest rank wins rather than array position, so an unsorted response from
  // the model still surfaces the right one.
  const top = data?.hypotheses?.length
    ? [...data.hypotheses].sort((a, b) => a.rank - b.rank)[0]
    : null

  return (
    <div className="border-t border-white/5 bg-black/30 px-4 py-5">
      {loading ? (
        <div className="space-y-4">
          <Skeleton className="h-3 w-32" />
          <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
            {Array.from({ length: 6 }, (_, i) => (
              <Skeleton key={i} className="h-12 w-full" />
            ))}
          </div>
          <SkeletonLines lines={3} />
        </div>
      ) : (
        <>
          {/* Computed. Always renders. */}
          <div className="flex items-center gap-2">
            <CircleAlert size={13} className="text-btc" aria-hidden />
            <h4 className="label-caps">Evidence</h4>
          </div>

          <dl className="mt-3 grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
            {data?.evidence.map((e) => (
              <div
                key={e.label}
                className="rounded-xl border border-white/5 bg-white/[0.02] px-3 py-2"
              >
                <dt className="label-caps">{e.label}</dt>
                <dd className="data-figure mt-1 text-sm text-white/90">{e.value}</dd>
                {e.detail && <p className="mt-1 text-[11px] leading-snug text-muted">{e.detail}</p>}
              </div>
            ))}
          </dl>

          {/* Generated. Collapses silently when the model had nothing. */}
          {top ? (
            <>
              <div className="mt-6 flex items-center gap-2">
                <Lightbulb size={13} className="text-gold" aria-hidden />
                <h4 className="label-caps">Likely Cause</h4>
              </div>

              <div className="mt-3 rounded-xl border border-btc/40 bg-btc/[0.04] p-4 shadow-lift">
                <div className="flex flex-wrap items-center gap-2.5">
                  <h5 className="font-heading text-sm font-medium">{top.cause}</h5>
                  <Badge tone={top.confidence}>{top.confidence} confidence</Badge>
                </div>

                <p className="mt-2.5 text-xs leading-relaxed text-white/70">{top.reasoning}</p>

                {top.supportingEvidence.length > 0 && (
                  <div className="mt-2.5 flex flex-wrap gap-1.5">
                    {top.supportingEvidence.map((s) => (
                      <span
                        key={s}
                        className="rounded-md border border-white/10 bg-white/5 px-2 py-0.5 font-mono text-[10px] text-muted"
                      >
                        {s}
                      </span>
                    ))}
                  </div>
                )}

                {top.recommendedAction && (
                  <div className="mt-3 flex gap-2 border-t border-white/5 pt-3">
                    <Wrench size={13} className="mt-0.5 shrink-0 text-gold" aria-hidden />
                    <p className="text-xs leading-relaxed text-white/80">{top.recommendedAction}</p>
                  </div>
                )}
              </div>
            </>
          ) : (
            <p className="mt-4 text-xs text-muted">
              Likely cause unavailable for this event. The computed evidence above is unaffected.
            </p>
          )}
        </>
      )}
    </div>
  )
}

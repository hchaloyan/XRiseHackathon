import { useEffect, useRef, useState } from 'react'
import { AlertTriangle, FileText, Info, Loader2, Sparkles, TrendingDown } from 'lucide-react'
import { api } from '../api/client'
import type { Callout, InsightResponse, KpiResponse, Severity } from '../api/types'
import ReportDialog from '../components/ReportDialog'
import { Badge } from '../components/ui/Badge'
import { Button } from '../components/ui/Button'
import { Card, CardLabel } from '../components/ui/Card'
import { Skeleton, SkeletonLines } from '../components/ui/Skeleton'
import { cn } from '../lib/cn'

const SEVERITY_ICON: Record<Severity, typeof AlertTriangle> = {
  high: AlertTriangle,
  medium: TrendingDown,
  low: Info,
}

/** Icon color carries severity. No tinted fill behind it — twelve small
 *  colored boxes on one screen is noise, not hierarchy. */
const SEVERITY_COLOR: Record<Severity, string> = {
  high: 'text-error',
  medium: 'text-accent',
  low: 'text-faint',
}

/**
 * Generated narrative -> GET /api/insights, on an explicit click rather than on
 * page open. Generation runs ~10s uncached, so the skeleton is load-bearing,
 * not polish. Narrative is nullable; render nothing in this slot if it comes
 * back null.
 *
 * The backend warms its cache for the newest day at startup, so the first press
 * usually returns in milliseconds — the button is about who decides to spend
 * the model call, not about hiding a wait.
 */
export default function InsightHeader({
  className,
  day,
  kpis,
}: {
  className?: string
  /** ISO date, or null for the newest day. */
  day?: string | null
  /** Already loaded by the shell; the report dialog renders from it rather
   *  than fetching the same snapshot a second time. */
  kpis?: KpiResponse | null
}) {
  const [reportOpen, setReportOpen] = useState(false)
  const [data, setData] = useState<InsightResponse | null>(null)
  const [loading, setLoading] = useState(false)

  /**
   * The day the in-flight request belongs to.
   *
   * Generation takes ~10s uncached, which is long enough to change the date
   * halfway through, and that used to break in two ways at once: `loading`
   * was never cleared, so the button stayed disabled and the new day could
   * not be generated at all; and when the old reply finally landed it was
   * written over whichever day was now on screen — Thursday's narrative
   * above Wednesday's events, with nothing to indicate it.
   *
   * A ref, not state: the resolving request must read the day as it is NOW,
   * not the value captured when the closure was created.
   */
  const wantedDay = useRef<string | null | undefined>(day)

  // A briefing belongs to the day it was generated for: moving the picker
  // clears it rather than leaving Thursday's narrative over Wednesday's events.
  useEffect(() => {
    wantedDay.current = day
    setData(null)
    setReportOpen(false)
    // Abandon any in-flight request. Its reply is now for a day nobody is
    // looking at, and leaving this true is what jammed the button.
    setLoading(false)
  }, [day])

  async function generate() {
    const requested = day
    setLoading(true)
    try {
      const result = await api.insights(requested)
      // Landed after the user moved on: drop it rather than render the wrong
      // day's briefing. The backend caches by day, so nothing is wasted —
      // coming back to this date returns instantly.
      if (wantedDay.current !== requested) return
      setData(result)
    } finally {
      if (wantedDay.current === requested) {
        // api.insights falls back to the fixture rather than throwing, so
        // there is no failure branch to render — only a spinner to put away.
        setLoading(false)
      }
    }
  }

  return (
    <Card size="lg" className={cn('flex flex-col', className)}>
      <CardLabel>Today's Briefing</CardLabel>

      {!data ? (
        <>
          <p className="mt-3 max-w-3xl text-sm leading-relaxed text-muted">
            Summarise this shift's OEE, scrap and downtime from the computed figures.
          </p>

          <Button onClick={generate} disabled={loading} className="mt-4 self-start">
            {loading ? (
              <Loader2 size={15} className="animate-spin" aria-hidden />
            ) : (
              <Sparkles size={15} aria-hidden />
            )}
            {loading ? 'Generating…' : 'Generate briefing'}
          </Button>

          {loading && (
            <div className="mt-6 space-y-5">
              <Skeleton className="h-8 w-4/5" />
              <SkeletonLines lines={4} />
            </div>
          )}
        </>
      ) : (
        <>
          {/* The largest thing on the screen. Weight and size carry it —
              87% white, no gradient. */}
          {data.headline && (
            <h3 className="mt-3 text-2xl leading-snug font-semibold tracking-tight text-hi">
              {data.headline}
            </h3>
          )}

          {data.narrative && (
            <p className="mt-3 max-w-3xl text-sm leading-relaxed text-muted">{data.narrative}</p>
          )}

          {/* Model failed entirely: say so plainly rather than showing an
              empty card (spec §5). The numbers below are unaffected. */}
          {!data.headline && !data.narrative && (
            <p className="mt-3 text-sm text-muted">
              Narrative unavailable. All figures below are computed and unaffected.
            </p>
          )}

          {data.callouts && data.callouts.length > 0 && (
            <ul className="mt-6 divide-y divide-line border-t border-line">
              {data.callouts.map((c) => (
                <CalloutRow key={c.title} callout={c} />
              ))}
            </ul>
          )}

          {/* The summary is the answer; the report is the working behind it.
              Offered after reading, not instead of it — and it opens instantly,
              because everything in it is already computed and on the client. */}
          <Button variant="outline" onClick={() => setReportOpen(true)} className="mt-5 self-start">
            <FileText size={15} aria-hidden />
            View full report
          </Button>
        </>
      )}

      {reportOpen && (
        <ReportDialog
          day={day ?? null}
          kpis={kpis ?? null}
          insight={data}
          onClose={() => setReportOpen(false)}
        />
      )}
    </Card>
  )
}

function CalloutRow({ callout }: { callout: Callout }) {
  const Icon = SEVERITY_ICON[callout.severity]
  return (
    <li className="flex gap-3 py-3">
      <Icon
        size={15}
        strokeWidth={2}
        aria-hidden
        className={cn('mt-0.5 shrink-0', SEVERITY_COLOR[callout.severity])}
      />

      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2">
          <h4 className="text-sm font-medium text-hi">{callout.title}</h4>
          {callout.metric && (
            <Badge tone={callout.severity} className="data-figure">
              {callout.metric}
            </Badge>
          )}
        </div>
        <p className="mt-1 text-xs leading-relaxed text-muted">{callout.detail}</p>
      </div>
    </li>
  )
}

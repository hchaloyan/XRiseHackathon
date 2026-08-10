import { AlertTriangle, Info, TrendingDown } from 'lucide-react'
import { api } from '../api/client'
import type { Callout, Severity } from '../api/types'
import { Badge } from '../components/ui/Badge'
import { Card, CardLabel } from '../components/ui/Card'
import { Skeleton, SkeletonLines } from '../components/ui/Skeleton'
import { cn } from '../lib/cn'
import { useFetch } from '../lib/useFetch'

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
 * Generated narrative -> GET /api/insights. Fires on page open (spec D2).
 * Generation runs ~10s, so the skeleton is load-bearing, not polish.
 * Narrative is nullable; render nothing in this slot if it comes back null.
 */
export default function InsightHeader({ className }: { className?: string }) {
  const { data, loading } = useFetch(api.insights)

  return (
    <Card size="lg" className={cn('flex flex-col', className)}>
      <CardLabel>Today's Briefing</CardLabel>

      {loading ? (
        <div className="mt-4 space-y-5">
          <Skeleton className="h-8 w-4/5" />
          <SkeletonLines lines={4} />
        </div>
      ) : (
        <>
          {/* The largest thing on the screen. Weight and size carry it —
              87% white, no gradient. */}
          {data?.headline && (
            <h3 className="mt-3 text-2xl leading-snug font-semibold tracking-tight text-hi">
              {data.headline}
            </h3>
          )}

          {data?.narrative && (
            <p className="mt-3 max-w-3xl text-sm leading-relaxed text-muted">{data.narrative}</p>
          )}

          {/* Model failed entirely: say so plainly rather than showing an
              empty card (spec §5). The numbers below are unaffected. */}
          {!data?.headline && !data?.narrative && (
            <p className="mt-3 text-sm text-muted">
              Narrative unavailable. All figures below are computed and unaffected.
            </p>
          )}

          {data?.callouts && data.callouts.length > 0 && (
            <ul className="mt-6 divide-y divide-line border-t border-line">
              {data.callouts.map((c) => (
                <CalloutRow key={c.title} callout={c} />
              ))}
            </ul>
          )}
        </>
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

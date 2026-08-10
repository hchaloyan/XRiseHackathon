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

/**
 * Generated narrative -> GET /api/insights. Fires on page open (spec D2).
 * Generation runs ~10s, so the skeleton is load-bearing, not polish.
 * Narrative is nullable; render nothing in this slot if it comes back null.
 */
export default function InsightHeader({ className }: { className?: string }) {
  const { data, loading } = useFetch(api.insights)

  return (
    <Card className={cn('flex flex-col', className)}>
      <CardLabel>Today's Briefing</CardLabel>

      {loading ? (
        <div className="mt-4 space-y-5">
          <Skeleton className="h-9 w-4/5" />
          <SkeletonLines lines={4} />
        </div>
      ) : (
        <>
          {/* Flourish #1: the largest thing on the screen, and the only
              gradient text in the app. */}
          {data?.headline && (
            <h3 className="text-gradient mt-3 font-heading text-2xl leading-tight font-semibold md:text-[2rem]">
              {data.headline}
            </h3>
          )}

          {data?.narrative && (
            <p className="mt-3 text-sm leading-relaxed text-white/70">{data.narrative}</p>
          )}

          {/* Model failed entirely: say so plainly rather than showing an
              empty card (spec §5). The numbers below are unaffected. */}
          {!data?.headline && !data?.narrative && (
            <p className="mt-3 text-sm text-muted">
              Narrative unavailable. All figures below are computed and unaffected.
            </p>
          )}

          {data?.callouts && data.callouts.length > 0 && (
            <ul className="mt-5 space-y-2">
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
    <li className="group flex gap-3 rounded-xl border border-white/5 bg-white/[0.02] p-3 transition-colors duration-300 hover:border-btc/30">
      <span
        className={cn(
          'mt-0.5 h-fit rounded-lg border p-1.5',
          callout.severity === 'high'
            ? 'border-burnt/50 bg-burnt/20 text-btc'
            : callout.severity === 'medium'
              ? 'border-gold/40 bg-gold/10 text-gold'
              : 'border-white/10 bg-white/5 text-muted',
        )}
      >
        <Icon size={14} strokeWidth={2} aria-hidden />
      </span>

      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2">
          <h4 className="font-heading text-sm font-medium">{callout.title}</h4>
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

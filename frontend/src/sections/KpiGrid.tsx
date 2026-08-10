import { ArrowDownRight, ArrowRight, ArrowUpRight } from 'lucide-react'
import { Area, AreaChart, ResponsiveContainer, YAxis } from 'recharts'
import type { KpiResponse, TrendPoint } from '../api/types'
import { Card, CardLabel } from '../components/ui/Card'
import { Skeleton } from '../components/ui/Skeleton'
import { cn } from '../lib/cn'
import { deltaVsMean, minutes, pct } from '../lib/format'

/**
 * KPI cards + sparklines -> GET /api/kpis.
 *
 * Every number here is computed in pandas, never by the model (rule 1). The
 * only client-side arithmetic is the delta against the 14-day mean, which
 * compares values pandas already produced rather than deriving a new metric.
 */

/** Recharts takes SVG attributes, not classes — this is the one place the
 *  accent token has to be repeated as a literal. Matches --color-accent. */
const ACCENT = '#C4A6FF'

type MetricKey = 'oee' | 'availability' | 'scrapRate' | 'downtimeMinutes'

interface MetricDef {
  key: MetricKey
  label: string
  format: (v: number) => string
  /** Scrap and downtime improve by going down. */
  higherIsBetter: boolean
  /** Rates read as percentage points; downtime reads as minutes. */
  deltaUnit: 'pts' | 'min'
}

const METRICS: MetricDef[] = [
  { key: 'oee', label: 'OEE', format: (v) => pct(v), higherIsBetter: true, deltaUnit: 'pts' },
  {
    key: 'availability',
    label: 'Availability',
    format: (v) => pct(v),
    higherIsBetter: true,
    deltaUnit: 'pts',
  },
  {
    key: 'scrapRate',
    label: 'Scrap Rate',
    format: (v) => pct(v, 2),
    higherIsBetter: false,
    deltaUnit: 'pts',
  },
  {
    key: 'downtimeMinutes',
    label: 'Downtime',
    format: minutes,
    higherIsBetter: false,
    deltaUnit: 'min',
  },
]

export default function KpiGrid({
  kpis,
  loading,
}: {
  kpis: KpiResponse | null
  loading: boolean
}) {
  return (
    <section className="grid grid-cols-2 gap-4 lg:grid-cols-4">
      {METRICS.map((m) => (
        <MetricCard key={m.key} metric={m} kpis={kpis} loading={loading} />
      ))}
    </section>
  )
}

function MetricCard({
  metric,
  kpis,
  loading,
}: {
  metric: MetricDef
  kpis: KpiResponse | null
  loading: boolean
}) {
  if (loading || !kpis) {
    return (
      <Card>
        <CardLabel>{metric.label}</CardLabel>
        <Skeleton className="mt-3 h-9 w-24" />
        <Skeleton className="mt-4 h-8 w-full" />
      </Card>
    )
  }

  const current = kpis.plant[metric.key]
  const history = kpis.trend.map((t) => t[metric.key])
  const delta = deltaVsMean(current, history)

  const improved = delta ? (metric.higherIsBetter ? delta.diff > 0 : delta.diff < 0) : false
  const Arrow =
    delta?.direction === 'flat' ? ArrowRight : delta?.direction === 'up' ? ArrowUpRight : ArrowDownRight

  return (
    <Card interactive className="group">
      <CardLabel>{metric.label}</CardLabel>

      <div className="data-figure mt-2 text-[28px] leading-none font-medium text-hi">
        {metric.format(current)}
      </div>

      {delta && (
        <div
          className={cn(
            'mt-2 flex items-center gap-1 text-[12px]',
            delta.direction === 'flat' ? 'text-faint' : improved ? 'text-positive' : 'text-error',
          )}
        >
          <Arrow size={12} strokeWidth={2.5} aria-hidden />
          <span className="data-figure">
            {metric.deltaUnit === 'pts'
              ? `${Math.abs(delta.diff * 100).toFixed(1)} pts`
              : `${Math.abs(Math.round(delta.diff))} min`}
          </span>
          <span className="text-faint">vs 14d avg</span>
        </div>
      )}

      <div className="mt-3 h-10">
        <Sparkline data={kpis.trend} metricKey={metric.key} />
      </div>
    </Card>
  )
}

function Sparkline({ data, metricKey }: { data: TrendPoint[]; metricKey: MetricKey }) {
  const gradientId = `spark-${metricKey}`
  return (
    <ResponsiveContainer width="100%" height="100%">
      <AreaChart data={data} margin={{ top: 2, right: 0, bottom: 0, left: 0 }}>
        <defs>
          <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={ACCENT} stopOpacity={0.18} />
            <stop offset="100%" stopColor={ACCENT} stopOpacity={0} />
          </linearGradient>
        </defs>
        <YAxis hide domain={['dataMin', 'dataMax']} />
        <Area
          type="monotone"
          dataKey={metricKey}
          stroke={ACCENT}
          strokeWidth={1.5}
          fill={`url(#${gradientId})`}
          isAnimationActive={false}
          dot={false}
        />
      </AreaChart>
    </ResponsiveContainer>
  )
}

/**
 * Worst first. Spec §6.1 plants a machine that degrades silently against its
 * ideal cycle time — it never raises a downtime event, so this ranking is the
 * only place it surfaces.
 */
export function MachineRanking({
  machines,
  className,
}: {
  machines: KpiResponse['machines']
  className?: string
}) {
  const ranked = [...machines].sort((a, b) => a.oee - b.oee)
  const worst = ranked[0]?.oee ?? 0

  return (
    <Card size="lg" className={cn('flex flex-col', className)}>
      <div className="flex items-baseline justify-between gap-3">
        <CardLabel>Machine OEE</CardLabel>
        <span className="text-[12px] text-faint">{machines.length || '—'} machines</span>
      </div>

      {/* Rows distribute to fill rather than bunching at the top and leaving
          the card half empty beside the taller inventory panel. */}
      <ul className="mt-5 flex flex-1 flex-col justify-between gap-2.5">
        {ranked.length === 0 &&
          Array.from({ length: 6 }, (_, i) => <Skeleton key={i} className="h-6 w-full" />)}

        {ranked.map((m) => {
          const isWorst = m.oee === worst
          return (
            <li key={m.machineId} className="grid grid-cols-[3.5rem_1fr_3rem] items-center gap-3">
              <span
                className={cn('data-figure text-[12px]', isWorst ? 'text-accent' : 'text-muted')}
                title={m.name}
              >
                {m.machineId}
              </span>

              {/* The worst machine is the point of this card, so it is the one
                  bar that lights up. */}
              <div className="h-1 overflow-hidden rounded-full bg-line">
                <div
                  className={cn(
                    'h-full rounded-full transition-[width] duration-500',
                    isWorst ? 'bg-accent shadow-glow' : 'bg-white/25',
                  )}
                  style={{ width: `${Math.round(m.oee * 100)}%` }}
                />
              </div>

              <span
                className={cn('data-figure text-right text-xs', isWorst ? 'text-accent' : 'text-hi')}
              >
                {pct(m.oee)}
              </span>
            </li>
          )
        })}
      </ul>
    </Card>
  )
}

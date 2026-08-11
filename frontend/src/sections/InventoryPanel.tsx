import { AlertTriangle, Clock, PackageCheck } from 'lucide-react'
import type { Inventory, InventoryItem } from '../api/types'
import { Card, CardLabel } from '../components/ui/Card'
import { Skeleton } from '../components/ui/Skeleton'
import { cn } from '../lib/cn'

/**
 * Inventory is named alongside OEE, scrap and downtime in CLAUDE.md
 * capability 1, and rides in the /api/kpis payload.
 *
 * This panel used to lead with "Lowest cover 4.4 days", which is stock-control
 * vocabulary: it stated a number and left the supervisor to work out which
 * part, whether that was bad, and what to do about it. It now says which part
 * runs out first, on what date, and how much to order — the three things that
 * turn the figure into an action before standup.
 */

const STATUS: Record<
  InventoryItem['status'],
  { label: string; icon: typeof AlertTriangle; tone: string }
> = {
  reorder_now: { label: 'Reorder now', icon: AlertTriangle, tone: 'text-error' },
  order_this_week: { label: 'Order this week', icon: Clock, tone: 'text-accent' },
  ok: { label: 'Stock OK', icon: PackageCheck, tone: 'text-faint' },
}

function whenReadable(iso: string): string {
  const d = new Date(`${iso}T00:00:00`)
  return d.toLocaleDateString(undefined, { weekday: 'short', day: 'numeric', month: 'short' })
}

export default function InventoryPanel({ inventory }: { inventory: Inventory | null }) {
  if (!inventory) {
    return (
      <Card size="lg">
        <CardLabel>Materials</CardLabel>
        <div className="mt-4 space-y-3">
          <Skeleton className="h-10 w-2/3" />
          <Skeleton className="h-3 w-full" />
          <Skeleton className="h-3 w-full" />
          <Skeleton className="h-3 w-4/5" />
        </div>
      </Card>
    )
  }

  const byUrgency = [...inventory.items].sort((a, b) => a.daysOfCover - b.daysOfCover)
  const act = byUrgency.filter((i) => i.status !== 'ok')
  const fine = byUrgency.filter((i) => i.status === 'ok').slice(0, 3)

  return (
    <Card size="lg" className="flex flex-col">
      <CardLabel>Materials</CardLabel>

      {/* The headline is the instruction, not the metric. */}
      <div className="mt-3">
        <p className="text-2xl leading-snug font-semibold tracking-tight text-hi">
          {inventory.partsBelowReorder > 0
            ? `Reorder ${inventory.partsBelowReorder} part${inventory.partsBelowReorder > 1 ? 's' : ''} today`
            : 'No parts need reordering today'}
        </p>
        <p className="mt-1.5 text-xs leading-relaxed text-muted">
          {inventory.soonestDescription} runs out first — about{' '}
          <span className="data-figure text-hi">{inventory.soonestDays} days</span> left, empty
          around {whenReadable(inventory.soonestRunsOutOn)} at current usage.
        </p>
      </div>

      {act.length > 0 && (
        <ul className="mt-5 space-y-2.5">
          {act.map((item) => (
            <PartRow key={item.partId} item={item} />
          ))}
        </ul>
      )}

      {fine.length > 0 && (
        <>
          <div className="label-caps mt-5 border-t border-line pt-4">Nothing needed yet</div>
          <ul className="mt-2.5 space-y-2.5">
            {fine.map((item) => (
              <PartRow key={item.partId} item={item} />
            ))}
          </ul>
        </>
      )}

      <p className="mt-4 text-[11px] leading-relaxed text-faint">
        Days left = stock on hand ÷ average daily usage. Order quantities cover a week of
        usage and clear the reorder point.
      </p>
    </Card>
  )
}

function PartRow({ item }: { item: InventoryItem }) {
  const status = STATUS[item.status]
  const Icon = status.icon
  const urgent = item.status === 'reorder_now'

  return (
    <li className="flex items-start gap-3 text-xs">
      <Icon size={13} className={cn('mt-0.5 shrink-0', status.tone)} aria-hidden />
      <div className="min-w-0 flex-1">
        <div className={cn('truncate', urgent ? 'text-hi' : 'text-muted')} title={item.description}>
          {item.description}
        </div>
        <div className="label-caps mt-0.5 text-faint">
          {item.partId} · {item.line} · {item.onHand} {item.uom} on hand
        </div>
        {item.status !== 'ok' && (
          <div className={cn('mt-1 text-[11px]', urgent ? 'text-error' : 'text-accent')}>
            {status.label}: {item.suggestedOrderQty} {item.uom}
          </div>
        )}
      </div>
      <div className="shrink-0 text-right">
        <div className={cn('data-figure', urgent ? 'text-error' : 'text-muted')}>
          {item.daysOfCover}d
        </div>
        <div className="text-[11px] text-faint">left</div>
      </div>
    </li>
  )
}

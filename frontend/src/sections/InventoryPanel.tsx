import { Package, PackageX } from 'lucide-react'
import type { Inventory, InventoryItem } from '../api/types'
import { Card, CardLabel } from '../components/ui/Card'
import { Skeleton } from '../components/ui/Skeleton'
import { cn } from '../lib/cn'

/**
 * Inventory is named alongside OEE, scrap and downtime in CLAUDE.md
 * capability 1, and rides in the /api/kpis payload. Parts below reorder go
 * first — that is the only part a supervisor acts on before standup.
 */
export default function InventoryPanel({ inventory }: { inventory: Inventory | null }) {
  if (!inventory) {
    return (
      <Card>
        <CardLabel>Material Cover</CardLabel>
        <div className="mt-4 space-y-3">
          <Skeleton className="h-10 w-2/3" />
          <Skeleton className="h-3 w-full" />
          <Skeleton className="h-3 w-full" />
          <Skeleton className="h-3 w-4/5" />
        </div>
      </Card>
    )
  }

  const byCover = [...inventory.items].sort((a, b) => a.daysOfCover - b.daysOfCover)
  const short = byCover.filter((i) => i.belowReorder)
  // Not yet actionable, but the parts that become tomorrow's problem.
  const watch = byCover.filter((i) => !i.belowReorder).slice(0, 4)

  return (
    <Card className="flex flex-col">
      <CardLabel>Material Cover</CardLabel>

      <div className="mt-3 flex items-baseline gap-2">
        <span className="data-figure text-4xl font-medium text-btc">
          {inventory.partsBelowReorder}
        </span>
        <span className="text-sm text-muted">
          of {inventory.partsTracked} parts below reorder
        </span>
      </div>

      <p className="mt-1 text-xs text-muted">
        Lowest cover{' '}
        <span className="data-figure text-gold">{inventory.lowestDaysOfCover} days</span>
      </p>

      {short.length > 0 && (
        <ul className="mt-4 space-y-2">
          {short.map((item) => (
            <PartRow key={item.partId} item={item} short />
          ))}
        </ul>
      )}

      {watch.length > 0 && (
        <>
          <div className="label-caps mt-5 border-t border-white/5 pt-3">Next lowest cover</div>
          <ul className="mt-2 space-y-2">
            {watch.map((item) => (
              <PartRow key={item.partId} item={item} />
            ))}
          </ul>
        </>
      )}
    </Card>
  )
}

function PartRow({ item, short }: { item: InventoryItem; short?: boolean }) {
  const Icon = short ? PackageX : Package
  return (
    <li className="flex items-center gap-3 text-xs">
      <Icon
        size={13}
        className={cn('shrink-0', short ? 'text-burnt' : 'text-white/25')}
        aria-hidden
      />
      <div className="min-w-0 flex-1">
        <div
          className={cn('truncate', short ? 'text-white/80' : 'text-white/50')}
          title={item.description}
        >
          {item.description}
        </div>
        <div className="label-caps mt-0.5">
          {item.partId} · {item.line}
        </div>
      </div>
      <span
        className={cn(
          'data-figure shrink-0 text-right',
          item.daysOfCover < 5 ? 'text-btc' : short ? 'text-gold' : 'text-muted',
        )}
      >
        {item.daysOfCover}d
      </span>
    </li>
  )
}

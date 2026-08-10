import { useState } from 'react'
import { ChevronRight } from 'lucide-react'
import type { EventRow } from '../api/types'
import { Badge } from '../components/ui/Badge'
import { Card, CardLabel } from '../components/ui/Card'
import { Skeleton } from '../components/ui/Skeleton'
import { cn } from '../lib/cn'
import { clockTime, humanizeCode, minutes } from '../lib/format'
import RootCausePanel from './RootCausePanel'

/**
 * Downtime + quality rows. Each row expands IN PLACE into RootCausePanel
 * (rule 7) -> POST /api/root-cause. Data questions are answered by clicking
 * a row, never by typing in the ask bar.
 *
 * Built from grid rows rather than a <table>: the whole row must be a real
 * <button> for keyboard use, and a button spanning <td>s is not valid markup.
 */

const COLS =
  'grid grid-cols-[3.25rem_minmax(0,1.4fr)_5.5rem_9rem_4.5rem_minmax(0,1.6fr)_1.25rem] items-center gap-3'

export default function EventTable({
  events,
  loading,
}: {
  events: EventRow[]
  loading: boolean
}) {
  const [openId, setOpenId] = useState<string | null>(null)

  const rows = [...events].sort((a, b) => b.start.localeCompare(a.start))
  const downtimeCount = rows.filter((r) => r.kind === 'downtime').length

  return (
    <Card size="none" className="overflow-hidden">
      <div className="flex flex-wrap items-baseline justify-between gap-3 px-5 pt-5">
        <CardLabel>Downtime &amp; Quality Events</CardLabel>
        <span className="font-mono text-[11px] text-muted">
          {rows.length ? (
            <>
              {downtimeCount} downtime · {rows.length - downtimeCount} quality · click any row
            </>
          ) : (
            '—'
          )}
        </span>
      </div>

      <div className={cn(COLS, 'label-caps mt-4 border-b border-white/5 px-5 pb-2')} aria-hidden>
        <span>Time</span>
        <span>Machine</span>
        <span>Line</span>
        <span>Reason</span>
        <span className="text-right">Impact</span>
        <span>Note</span>
        <span />
      </div>

      <ul>
        {loading &&
          Array.from({ length: 6 }, (_, i) => (
            <li key={i} className="px-5 py-3">
              <Skeleton className="h-5 w-full" />
            </li>
          ))}

        {rows.map((event) => {
          const open = openId === event.eventId
          const panelId = `rc-${event.eventId}`
          const isDowntime = event.kind === 'downtime'

          return (
            <li key={event.eventId} className="border-b border-white/5 last:border-b-0">
              <button
                type="button"
                onClick={() => setOpenId(open ? null : event.eventId)}
                aria-expanded={open}
                aria-controls={panelId}
                className={cn(
                  COLS,
                  'w-full cursor-pointer px-5 py-3 text-left transition-colors duration-200',
                  'hover:bg-white/[0.03] focus-visible:bg-white/[0.03] focus-visible:outline-none',
                  'focus-visible:ring-2 focus-visible:ring-btc focus-visible:ring-inset',
                  open && 'bg-white/[0.04]',
                )}
              >
                <span className="data-figure text-xs text-white/60">
                  {clockTime(event.start)}
                </span>

                <span className="min-w-0">
                  <span className="block truncate text-xs text-white/90" title={event.machineName}>
                    {event.machineName}
                  </span>
                  <span className="label-caps">{event.machineId}</span>
                </span>

                <span className="font-mono text-[11px] text-muted">
                  {event.line}
                  <span className="ml-1.5 text-white/30">{event.shift}</span>
                </span>

                <span>
                  <Badge tone={isDowntime ? 'downtime' : 'quality'}>
                    {humanizeCode(event.reasonCode ?? event.defectType ?? '—')}
                  </Badge>
                </span>

                <span
                  className={cn(
                    'data-figure text-right text-xs',
                    isDowntime ? 'text-btc' : 'text-gold',
                  )}
                >
                  {isDowntime
                    ? event.durationMinutes !== null
                      ? minutes(event.durationMinutes)
                      : '—'
                    : `${event.defectCount ?? 0} pcs`}
                </span>

                <span className="min-w-0 truncate text-[11px] text-muted" title={event.operatorNote ?? ''}>
                  {event.operatorNote ?? ''}
                </span>

                <ChevronRight
                  size={14}
                  aria-hidden
                  className={cn(
                    'text-muted transition-transform duration-300',
                    open && 'rotate-90 text-btc',
                  )}
                />
              </button>

              {open && (
                <div id={panelId}>
                  <RootCausePanel event={event} />
                </div>
              )}
            </li>
          )
        })}
      </ul>
    </Card>
  )
}

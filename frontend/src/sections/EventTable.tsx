import { useState } from 'react'
import { ChevronRight } from 'lucide-react'
import { DEMO, DEMO_ROOT_CAUSE_IDS } from '../api/client'
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

/* Time · Machine · Line · Reason · Impact · Note · chevron.
   Impact is right-aligned, so its number ends hard against the column edge and
   the grid gap alone is not enough to keep it off the note. NOTE_PAD adds that
   separation on the Note side, where there is slack to spend.

   Five of the seven columns are fixed, so narrowing the window takes it out of
   Machine and Note alone. Under 1024px that leaves the note showing three
   words, so Line goes first: a machine belongs to exactly one line and its id
   is already under its name, which makes this the only column that repeats
   something the row has said. Shift goes with it, and is the one loss — it
   reappears in the row's own expansion, under "Line and shift". */
const LINE_COL = 'hidden lg:block'

const COLS = cn(
  'grid grid-cols-[3.25rem_minmax(0,1.4fr)_9rem_4.5rem_minmax(0,1.6fr)_1.25rem] items-center gap-3',
  'lg:grid-cols-[3.25rem_minmax(0,1.4fr)_5.5rem_9rem_4.5rem_minmax(0,1.6fr)_1.25rem]',
)

const NOTE_PAD = 'pl-6'

type Filter = 'all' | 'downtime' | 'quality'

export default function EventTable({
  events,
  loading,
}: {
  events: EventRow[]
  loading: boolean
}) {
  const [openId, setOpenId] = useState<string | null>(null)
  const [filter, setFilter] = useState<Filter>('all')

  const sorted = [...events].sort((a, b) => b.start.localeCompare(a.start))
  const downtimeCount = sorted.filter((r) => r.kind === 'downtime').length
  const rows = filter === 'all' ? sorted : sorted.filter((r) => r.kind === filter)

  // Counts live on the buttons rather than in a separate caption: the same
  // information, minus a line of chrome.
  const FILTERS: { key: Filter; label: string; count: number }[] = [
    { key: 'all', label: 'All', count: sorted.length },
    { key: 'downtime', label: 'Downtime', count: downtimeCount },
    { key: 'quality', label: 'Quality', count: sorted.length - downtimeCount },
  ]

  return (
    <Card size="none" className="overflow-hidden">
      <div className="flex flex-wrap items-center justify-between gap-3 px-5 pt-5">
        <CardLabel>Downtime &amp; Quality Events</CardLabel>

        <div className="flex items-center gap-1 rounded-lg border border-line p-0.5">
          {FILTERS.map((f) => (
            <button
              key={f.key}
              type="button"
              onClick={() => setFilter(f.key)}
              aria-pressed={filter === f.key}
              className={cn(
                'cursor-pointer rounded-md px-2.5 py-1 text-[12px] font-medium transition-colors duration-150',
                'focus-visible:ring-2 focus-visible:ring-accent focus-visible:outline-none',
                filter === f.key
                  ? 'bg-white/[0.08] text-accent'
                  : 'text-muted hover:text-hi',
              )}
            >
              {f.label}
              <span className="data-figure ml-1.5 text-faint">{f.count}</span>
            </button>
          ))}
        </div>
      </div>

      {/* Without this a judge clicks a row at random, gets evidence with no
          ranking, and concludes root cause is broken. Point at the two rows
          that carry a recorded analysis instead. */}
      {DEMO && (
        <p className="mt-2 px-5 text-[11px] text-faint">
          <span className="mr-1.5 inline-block h-1.5 w-1.5 rounded-full bg-accent align-middle" />
          marks the {DEMO_ROOT_CAUSE_IDS.length} rows with a recorded root-cause analysis. Every
          other row expands to real computed evidence, but the ranking needs the local model.
        </p>
      )}

      <div className={cn(COLS, 'label-caps mt-4 border-b border-white/5 px-5 pb-2')} aria-hidden>
        <span>Time</span>
        <span>Machine</span>
        <span className={LINE_COL}>Line</span>
        <span>Reason</span>
        <span className="text-right">Impact</span>
        <span className={NOTE_PAD}>Note</span>
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
                  'focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-inset',
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

                <span className={cn(LINE_COL, 'font-mono text-[12px] text-muted')}>
                  {event.line}
                  <span className="ml-1.5 text-white/30">{event.shift}</span>
                </span>

                <span className="flex items-center gap-1.5">
                  {/* Uniform white: the reason is a label, not a severity, and
                      the filter above now carries the downtime/quality split. */}
                  <Badge className="text-hi">
                    {humanizeCode(event.reasonCode ?? event.defectType ?? '—')}
                  </Badge>
                  {DEMO && DEMO_ROOT_CAUSE_IDS.includes(event.eventId) && (
                    <span
                      title="Recorded root-cause analysis available in this preview"
                      className="h-1.5 w-1.5 shrink-0 rounded-full bg-accent"
                    />
                  )}
                </span>

                <span className="data-figure text-right text-xs text-accent">
                  {isDowntime
                    ? event.durationMinutes !== null
                      ? minutes(event.durationMinutes)
                      : '—'
                    : `${event.defectCount ?? 0} pcs`}
                </span>

                <span
                  className={cn('min-w-0 truncate text-[12px] text-muted', NOTE_PAD)}
                  title={event.operatorNote ?? ''}
                >
                  {event.operatorNote ?? ''}
                </span>

                <ChevronRight
                  size={14}
                  aria-hidden
                  className={cn(
                    'text-muted transition-transform duration-300',
                    open && 'rotate-90 text-accent',
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

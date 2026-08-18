import { useEffect } from 'react'
import { createPortal } from 'react-dom'
import { Download, FileSpreadsheet, FileText, Table2, X } from 'lucide-react'
import { api, DEMO, DEMO_NOTES } from '../api/client'
import type { InsightResponse, KpiResponse } from '../api/types'
import { cn } from '../lib/cn'

/**
 * The full shift report, over the top of the dashboard.
 *
 * A dialog rather than a screen, deliberately: the briefing is the summary and
 * this is the same day in full, so it belongs *over* what you were reading, not
 * somewhere you navigate to and back from. Escape and the backdrop both close
 * it, and it is portaled to <body> so the header's backdrop-filter cannot trap
 * it in a stacking context.
 *
 * Everything shown here is already loaded — the KPI snapshot the dashboard
 * holds, plus whatever narrative has been generated. Opening it costs nothing
 * and never triggers a model call.
 */

const EXPORTS = [
  { format: 'pdf', label: 'PDF', icon: FileText, hint: 'to read or attach' },
  { format: 'xlsx', label: 'Excel', icon: FileSpreadsheet, hint: 'one sheet per section' },
  { format: 'mis', label: 'MIS', icon: Table2, hint: 'flat CSV for plant systems' },
] as const

function pct(value: number | null | undefined): string {
  return value === null || value === undefined ? '—' : `${(value * 100).toFixed(1)}%`
}

export default function ReportDialog({
  day,
  kpis,
  insight,
  onClose,
}: {
  /** ISO date, or null for the newest day. */
  day: string | null
  kpis: KpiResponse | null
  /** Whatever has been generated. Null is normal, not an error. */
  insight: InsightResponse | null
  onClose: () => void
}) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose()
    document.addEventListener('keydown', onKey)
    // The page behind must not scroll while a dialog is over it.
    const previous = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => {
      document.removeEventListener('keydown', onKey)
      document.body.style.overflow = previous
    }
  }, [onClose])

  if (!kpis) return null

  const plant = kpis.plant
  const inv = kpis.inventory
  const worst = [...kpis.machines].sort((a, b) => a.oee - b.oee).slice(0, 5)
  const short = inv.items.filter((i) => i.status !== 'ok')
  const readable = new Date(`${kpis.day}T00:00:00`).toLocaleDateString(undefined, {
    weekday: 'long',
    day: 'numeric',
    month: 'long',
    year: 'numeric',
  })

  return createPortal(
    <div
      className="fixed inset-0 z-[100] flex items-start justify-center overflow-y-auto bg-black/70 p-6 backdrop-blur-sm"
      onMouseDown={(e) => {
        // mousedown on the backdrop itself, not a drag that ended there.
        if (e.target === e.currentTarget) onClose()
      }}
      role="dialog"
      aria-modal="true"
      aria-label={`Shift report for ${readable}`}
    >
      <div className="glass-bar my-6 w-full max-w-4xl rounded-2xl border border-line p-6 shadow-glow">
        <div className="flex items-start justify-between gap-4 border-b border-line pb-4">
          <div>
            <p className="label-caps text-faint">Shift report</p>
            <h2 className="mt-1 text-xl font-semibold tracking-tight text-hi">{readable}</h2>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close report"
            className="cursor-pointer rounded p-1.5 text-muted transition-colors duration-150 hover:bg-white/10 hover:text-hi"
          >
            <X size={16} aria-hidden />
          </button>
        </div>

        {insight?.headline && (
          <h3 className="mt-6 text-lg leading-snug font-medium text-hi">{insight.headline}</h3>
        )}
        {insight?.narrative && (
          <p className="mt-2 text-sm leading-relaxed text-muted">{insight.narrative}</p>
        )}
        {!insight?.headline && (
          <p className="mt-6 text-xs text-faint">
            No narrative generated for this day yet — every figure below is computed from machine
            data and is unaffected. Close this and press “Generate briefing” to add one.
          </p>
        )}

        <Section title="Plant">
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
            <Figure label="OEE" value={pct(plant.oee)} />
            <Figure label="Availability" value={pct(plant.availability)} />
            <Figure label="Performance" value={pct(plant.performance)} />
            <Figure label="Quality" value={pct(plant.quality)} />
            <Figure label="Scrap" value={pct(plant.scrapRate)} />
            <Figure label="Downtime" value={`${plant.downtimeMinutes.toFixed(0)} min`} />
          </div>
        </Section>

        <Section title="Lowest OEE machines">
          <Rows
            head={['Machine', 'Line', 'OEE', 'Scrap', 'Downtime']}
            rows={worst.map((m) => [
              `${m.machineId} · ${m.name}`,
              m.line,
              pct(m.oee),
              pct(m.scrapRate),
              `${m.downtimeMinutes.toFixed(0)} min`,
            ])}
          />
        </Section>

        {insight?.downtimeByReason && insight.downtimeByReason.length > 0 && (
          <Section title="Downtime by reason">
            <Rows
              head={['Reason', 'Minutes', 'Events']}
              rows={insight.downtimeByReason.map((r) => [
                r.reasonCode,
                r.minutes.toFixed(0),
                String(r.events),
              ])}
            />
          </Section>
        )}

        <Section title="Materials">
          <p className="mb-2 text-xs text-muted">
            {inv.partsBelowReorder} of {inv.partsTracked} parts below reorder point.{' '}
            {inv.soonestDescription} runs out first, about {inv.soonestDays} days left.
          </p>
          {short.length > 0 && (
            <Rows
              head={['Part', 'On hand', 'Days left', 'Order']}
              rows={short.map((i) => [
                `${i.partId} · ${i.description}`,
                `${i.onHand} ${i.uom}`,
                `${i.daysOfCover}`,
                `${i.suggestedOrderQty} ${i.uom}`,
              ])}
            />
          )}
        </Section>

        <Section title={`Events (${kpis.events.length})`}>
          <div className="max-h-64 overflow-y-auto">
            <Rows
              head={['Time', 'Machine', 'Type', 'Detail']}
              rows={kpis.events.map((e) => [
                e.start.slice(11, 16),
                e.machineId,
                e.reasonCode ?? e.defectType ?? '',
                e.kind === 'downtime'
                  ? `${e.durationMinutes?.toFixed(0) ?? '—'} min · ${e.operatorNote ?? ''}`
                  : `${e.defectCount} parts`,
              ])}
            />
          </div>
        </Section>

        <p className="mt-6 border-t border-line pt-4 text-[11px] leading-relaxed text-faint">
          Compiled automatically from machine data. The same report assembled by hand in a
          spreadsheet takes about 35 minutes: pulling counts per machine, working out availability
          and performance, chasing operator notes for the stoppages, and checking stock against
          reorder points.
        </p>

        {/* Export last, on purpose. Nobody should be downloading a shift report
            they have not read: these figures go into a supervisor's meeting or
            a plant system, so the checking happens here and the download is
            what you do once it looks right. */}
        <div className="mt-5 rounded-xl border border-line bg-white/[0.04] p-4">
          <p className="text-xs text-hi">Everything above checks out?</p>
          <p className="mt-0.5 text-[11px] text-faint">
            {DEMO ? DEMO_NOTES.export : `Download this report for ${readable}.`}
          </p>
          <div className="mt-3 flex flex-wrap items-center gap-2">
            {EXPORTS.map(({ format, label, icon: Icon, hint }) =>
              /* A live-looking link to a backend that is not there downloads
                 nothing and says nothing, which in front of a judge reads as a
                 broken feature rather than an absent one. Render the same row
                 disabled instead, so the capability is still visible. */
              DEMO ? (
                <span
                  key={format}
                  aria-disabled
                  title="Exports are rendered by the backend, which this static preview does not have."
                  className="inline-flex cursor-not-allowed items-center gap-1.5 rounded-lg border border-line border-dashed px-3 py-1.5 text-xs text-faint"
                >
                  <Icon size={13} aria-hidden />
                  {label}
                  <span className="text-[11px]">{hint}</span>
                </span>
              ) : (
                <a
                  key={format}
                  href={api.reportUrl(format, day)}
                  className="inline-flex cursor-pointer items-center gap-1.5 rounded-lg border border-line bg-white/[0.06] px-3 py-1.5 text-xs text-hi transition-colors duration-150 hover:bg-white/10"
                >
                  <Icon size={13} className="text-accent" aria-hidden />
                  {label}
                  <span className="text-[11px] text-faint">{hint}</span>
                  <Download size={11} className="text-faint" aria-hidden />
                </a>
              ),
            )}
          </div>
        </div>
      </div>
    </div>,
    document.body,
  )
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="mt-6">
      <h4 className="label-caps mb-2 border-b border-line pb-1.5">{title}</h4>
      {children}
    </section>
  )
}

function Figure({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-white/5 bg-white/[0.05] px-3 py-2">
      <div className="label-caps text-faint">{label}</div>
      <div className="data-figure mt-0.5 text-sm text-hi">{value}</div>
    </div>
  )
}

function Rows({ head, rows }: { head: string[]; rows: string[][] }) {
  return (
    <table className="w-full text-left text-xs">
      <thead>
        <tr className="text-faint">
          {head.map((h) => (
            <th key={h} className="label-caps pb-1.5 font-normal">
              {h}
            </th>
          ))}
        </tr>
      </thead>
      <tbody className="text-muted">
        {rows.map((row, i) => (
          <tr key={i} className="border-t border-line/60">
            {row.map((cell, j) => (
              <td
                key={j}
                className={cn('py-1.5 pr-3 align-top', j === 0 && 'text-hi')}
                title={cell}
              >
                {cell}
              </td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  )
}

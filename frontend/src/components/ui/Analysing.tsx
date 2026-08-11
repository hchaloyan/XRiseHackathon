import { useEffect, useState } from 'react'
import { Loader2 } from 'lucide-react'

/**
 * Progress for the root-cause generation, which takes ~6-10s on a local 7B.
 *
 * The stages are NOT decorative. They name the four things the backend
 * genuinely does in order — correlate events in pandas, retrieve SOP sections,
 * rank hypotheses against that evidence, check citations — so a supervisor
 * watching it learns what the answer is built from. A generic spinner teaches
 * nothing and reads as a hang.
 *
 * Timings are approximate and deliberately conservative: the bar slows as it
 * approaches the end rather than completing and then waiting, which is the
 * pattern that makes a progress indicator feel dishonest.
 */

const STAGES = [
  { at: 0, label: 'Correlating events on this machine and line' },
  { at: 1200, label: 'Pulling the procedures that cover this fault' },
  { at: 2600, label: 'Ranking likely causes against the evidence' },
  { at: 6000, label: 'Checking every citation resolves' },
]

export default function Analysing({ className }: { className?: string }) {
  const [elapsed, setElapsed] = useState(0)

  useEffect(() => {
    const started = Date.now()
    const id = window.setInterval(() => setElapsed(Date.now() - started), 200)
    return () => window.clearInterval(id)
  }, [])

  const stage = [...STAGES].reverse().find((s) => elapsed >= s.at) ?? STAGES[0]

  // Asymptotic: approaches 95% and never reaches it, so a slow run never shows
  // a full bar with nothing happening behind it.
  const progress = 95 * (1 - Math.exp(-elapsed / 4000))

  return (
    <div className={className}>
      <div className="flex items-center gap-2">
        <Loader2 size={13} className="animate-spin text-accent" aria-hidden />
        <p className="text-xs text-muted" aria-live="polite">
          {stage.label}
          <span className="text-faint">…</span>
        </p>
      </div>

      <div className="mt-2.5 h-0.5 w-full overflow-hidden rounded-full bg-white/[0.06]">
        <div
          className="h-full rounded-full bg-accent transition-[width] duration-200 ease-out"
          style={{ width: `${progress}%` }}
        />
      </div>

      {elapsed > 12000 && (
        <p className="mt-2 text-[11px] text-faint">
          Taking longer than usual — the local model may be loading.
        </p>
      )}
    </div>
  )
}

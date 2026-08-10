import { cva, type VariantProps } from 'class-variance-authority'
import type { ComponentProps } from 'react'
import { cn } from '../../lib/cn'

const badge = cva(
  'inline-flex items-center gap-1.5 rounded-lg border px-2 py-0.5 font-mono text-[10px] uppercase tracking-widest whitespace-nowrap',
  {
    variants: {
      tone: {
        /** Downtime rows and high-severity callouts. */
        downtime: 'border-burnt/50 bg-burnt/15 text-btc',
        /** Quality rows — gold reads as "value at risk", not "machine stopped". */
        quality: 'border-gold/40 bg-gold/10 text-gold',
        high: 'border-burnt/60 bg-burnt/20 text-[#FDBA74]',
        medium: 'border-gold/40 bg-gold/10 text-gold',
        low: 'border-white/15 bg-white/5 text-muted',
        neutral: 'border-white/10 bg-white/5 text-muted',
      },
    },
    defaultVariants: { tone: 'neutral' },
  },
)

type BadgeProps = ComponentProps<'span'> & VariantProps<typeof badge>

export function Badge({ className, tone, ...props }: BadgeProps) {
  return <span className={cn(badge({ tone }), className)} {...props} />
}

/**
 * Flourish #2: the one pulsing element on the screen. Suggests a live line
 * feed. Stops entirely under prefers-reduced-motion (see index.css).
 */
export function LiveBadge({ label = 'Live' }: { label?: string }) {
  return (
    <span className="inline-flex items-center gap-2 rounded-full border border-btc/30 bg-btc/10 px-3 py-1 font-mono text-[10px] tracking-widest text-btc uppercase">
      <span className="size-1.5 rounded-full bg-btc animate-pulse-dot" aria-hidden />
      {label}
    </span>
  )
}

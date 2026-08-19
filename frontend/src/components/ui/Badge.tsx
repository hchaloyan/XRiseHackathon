import { cva, type VariantProps } from 'class-variance-authority'
import type { ComponentProps } from 'react'
import { cn } from '../../lib/cn'

/**
 * Text-colored, outline-only. A filled saturated chip is exactly the optical
 * vibration a dark theme has to avoid, and there are up to a dozen of
 * these on screen at once.
 */
const badge = cva(
  'inline-flex items-center gap-1.5 rounded border border-line px-1.5 py-0.5 text-[12px] font-medium whitespace-nowrap',
  {
    variants: {
      tone: {
        high: 'text-error',
        medium: 'text-accent',
        low: 'text-muted',
        neutral: 'text-muted',
      },
    },
    defaultVariants: { tone: 'neutral' },
  },
)

type BadgeProps = ComponentProps<'span'> & VariantProps<typeof badge>

export function Badge({ className, tone, ...props }: BadgeProps) {
  return <span className={cn(badge({ tone }), className)} {...props} />
}

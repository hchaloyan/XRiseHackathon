import { cva, type VariantProps } from 'class-variance-authority'
import type { ComponentProps } from 'react'
import { cn } from '../../lib/cn'

/** 01dp surface. Depth comes from the white overlay baked into surface-1,
 *  so no card here carries a border-glow or a lift transform. */
const card = cva('card-block', {
  variants: {
    size: { sm: 'p-4', md: 'p-5', lg: 'p-6', none: '' },
    /** Opt-in: a static tile that reacts on hover is a lie. */
    interactive: { true: 'card-hover', false: '' },
  },
  defaultVariants: { size: 'md', interactive: false },
})

type CardProps = ComponentProps<'div'> & VariantProps<typeof card>

export function Card({ className, size, interactive, ...props }: CardProps) {
  return <div className={cn(card({ size, interactive }), className)} {...props} />
}

/** Section eyebrow. Every card gets one so the screen scans as a system. */
export function CardLabel({ className, ...props }: ComponentProps<'h2'>) {
  return <h2 className={cn('label-caps', className)} {...props} />
}

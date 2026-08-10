import { cva, type VariantProps } from 'class-variance-authority'
import type { ComponentProps } from 'react'
import { cn } from '../../lib/cn'

const card = cva('rounded-2xl', {
  variants: {
    variant: {
      /** Dark Matter surface floating above the void. */
      block: 'card-block',
      /** Translucent, reveals the grid pattern behind it. */
      glass: 'card-glass',
    },
    size: { sm: 'p-4', md: 'p-5', lg: 'p-6', none: '' },
    /** Opt-in: a static tile that lifts on hover is a lie. */
    interactive: { true: 'card-hover', false: '' },
  },
  defaultVariants: { variant: 'block', size: 'md', interactive: false },
})

type CardProps = ComponentProps<'div'> & VariantProps<typeof card>

export function Card({ className, variant, size, interactive, ...props }: CardProps) {
  return <div className={cn(card({ variant, size, interactive }), className)} {...props} />
}

/** Section eyebrow. Every card gets one so the screen scans as a system. */
export function CardLabel({ className, ...props }: ComponentProps<'h2'>) {
  return <h2 className={cn('label-caps', className)} {...props} />
}

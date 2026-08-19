import { cva, type VariantProps } from 'class-variance-authority'
import type { ComponentProps } from 'react'
import { cn } from '../../lib/cn'

/**
 * The one place a saturated fill is allowed: a single small primary action.
 * Its label is dark-on-accent, since accent is a tone-200 pastel.
 * Disabled is exactly 12% white fill, 38% white label.
 */
const button = cva(
  [
    'inline-flex items-center justify-center gap-2 rounded-lg font-medium',
    'transition-colors duration-150 cursor-pointer',
    'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2 focus-visible:ring-offset-surface',
    'disabled:cursor-not-allowed disabled:bg-line disabled:text-faint disabled:shadow-none disabled:hover:bg-line',
  ],
  {
    variants: {
      variant: {
        /* The one saturated fill in the app, and the one element that glows. */
        primary: 'bg-accent text-surface shadow-glow hover:bg-accent/90',
        outline: 'border border-line text-hi hover:bg-white/5',
        ghost: 'text-muted hover:bg-white/5 hover:text-hi',
      },
      /** 44px floor on the tappable variants, the touch-target minimum. */
      size: { sm: 'h-9 px-4 text-xs', md: 'min-h-11 px-6 text-sm', icon: 'size-11' },
    },
    defaultVariants: { variant: 'primary', size: 'md' },
  },
)

type ButtonProps = ComponentProps<'button'> & VariantProps<typeof button>

export function Button({ className, variant, size, ...props }: ButtonProps) {
  return <button className={cn(button({ variant, size }), className)} {...props} />
}

import { cva, type VariantProps } from 'class-variance-authority'
import type { ComponentProps } from 'react'
import { cn } from '../../lib/cn'

const button = cva(
  [
    'inline-flex items-center justify-center gap-2 rounded-full font-medium',
    'transition-all duration-300 cursor-pointer',
    'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-btc focus-visible:ring-offset-2 focus-visible:ring-offset-void',
    'disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:scale-100',
  ],
  {
    variants: {
      variant: {
        primary: [
          'bg-gradient-to-r from-burnt to-btc text-white uppercase tracking-wider',
          'shadow-glow-orange hover:scale-105 hover:shadow-glow-strong',
        ],
        outline: 'border-2 border-white/20 text-white hover:border-white hover:bg-white/10',
        ghost: 'text-white hover:bg-white/10 hover:text-btc',
        link: 'text-btc hover:underline',
      },
      /** 44px floor on the tappable variants, per design.md touch targets. */
      size: { sm: 'h-9 px-4 text-xs', md: 'min-h-11 px-6 text-sm', icon: 'size-11' },
    },
    defaultVariants: { variant: 'primary', size: 'md' },
  },
)

type ButtonProps = ComponentProps<'button'> & VariantProps<typeof button>

export function Button({ className, variant, size, ...props }: ButtonProps) {
  return <button className={cn(button({ variant, size }), className)} {...props} />
}

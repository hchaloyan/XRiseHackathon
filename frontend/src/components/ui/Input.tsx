import type { ComponentProps } from 'react'
import { cn } from '../../lib/cn'

/**
 * Data-terminal input: bottom border only, orange on focus, glow beneath.
 * One shape, no variants — the app has exactly one input.
 */
export function Input({ className, ...props }: ComponentProps<'input'>) {
  return (
    <input
      className={cn(
        'h-12 w-full rounded-lg bg-black/50 px-4 py-2 text-sm text-white',
        'border-b-2 border-white/20 placeholder:text-white/30',
        'transition-all duration-200',
        'focus-visible:border-btc focus-visible:shadow-focus focus-visible:outline-none',
        'disabled:cursor-not-allowed disabled:opacity-50',
        className,
      )}
      {...props}
    />
  )
}

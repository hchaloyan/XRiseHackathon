import type { ComponentProps } from 'react'
import { cn } from '../../lib/cn'

/**
 * Filled field, translucent so it sits *in* the glass bar rather than on top
 * of it. One shape, no variants — the app has exactly one input.
 */
export function Input({ className, ...props }: ComponentProps<'input'>) {
  return (
    <input
      className={cn(
        'h-12 w-full rounded-xl border border-line bg-white/[0.06] px-4 py-2 text-sm text-hi',
        'placeholder:text-faint',
        'transition-[border-color,box-shadow] duration-200',
        'focus-visible:border-accent/70 focus-visible:shadow-glow focus-visible:outline-none',
        'disabled:cursor-not-allowed disabled:text-faint',
        className,
      )}
      {...props}
    />
  )
}

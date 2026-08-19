import { cn } from '../../lib/cn'

/**
 * Load-bearing, not polish: insight generation runs ~10s and the
 * user is watching an empty slot the whole time.
 */
export function Skeleton({ className }: { className?: string }) {
  return <div className={cn('animate-shimmer rounded-md bg-white/5', className)} />
}

/** Paragraph-shaped skeleton with a ragged last line. */
export function SkeletonLines({ lines = 3 }: { lines?: number }) {
  return (
    <div className="space-y-2.5" aria-hidden>
      {Array.from({ length: lines }, (_, i) => (
        <Skeleton key={i} className={cn('h-3', i === lines - 1 ? 'w-2/5' : 'w-full')} />
      ))}
    </div>
  )
}

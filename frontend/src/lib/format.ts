/**
 * The only place raw API numbers become display strings.
 *
 * The backend sends unformatted values by design (`0.7721`, `256.0`) — pandas
 * owns the arithmetic, this file owns the presentation.
 */

/** 0.7721 -> "77.2%" */
export const pct = (v: number, digits = 1) => `${(v * 100).toFixed(digits)}%`

/** 256 -> "4h 16m", 47 -> "47m" */
export function minutes(v: number): string {
  const total = Math.round(v)
  if (total < 60) return `${total}m`
  const h = Math.floor(total / 60)
  const m = total % 60
  return m === 0 ? `${h}h` : `${h}h ${m}m`
}

/** "2026-08-09T14:39:00" -> "14:39" */
export const clockTime = (iso: string) => iso.slice(11, 16)

/** "2026-08-09" -> "Sun 09 Aug" */
export function shortDate(iso: string): string {
  const d = new Date(`${iso.slice(0, 10)}T00:00:00`)
  return d.toLocaleDateString('en-GB', {
    weekday: 'short',
    day: '2-digit',
    month: 'short',
  })
}

/** "MATERIAL_STARVE" -> "Material Starve" */
export const humanizeCode = (code: string) =>
  code
    .split('_')
    .map((w) => w.charAt(0) + w.slice(1).toLowerCase())
    .join(' ')

/**
 * Signed delta of `current` against the mean of `history`, in percentage
 * points for rates and in raw units otherwise.
 *
 * Only client-side arithmetic in the app, and deliberately so: it compares
 * values pandas already computed rather than deriving a new metric.
 */
export function deltaVsMean(current: number, history: number[]) {
  if (history.length === 0) return null
  const mean = history.reduce((a, b) => a + b, 0) / history.length
  const diff = current - mean
  return { diff, mean, direction: diff === 0 ? 'flat' : diff > 0 ? 'up' : 'down' } as const
}

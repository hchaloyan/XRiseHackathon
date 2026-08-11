import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from 'react'

/**
 * The day the whole dashboard is showing.
 *
 * Context rather than props because two very distant components need it: the
 * picker in the header sets it, and the ask bar sets it too — answering "what
 * was yesterday's OEE" with a button that moves the dashboard to that day is
 * the difference between a redirect and an answer.
 *
 * `null` means "the newest day the dataset holds". The backend already treats
 * a missing `day` param that way, so the app can render before /api/days has
 * returned rather than blocking on it.
 */

interface DayState {
  /** ISO date, or null for the newest day. */
  day: string | null
  setDay: (day: string | null) => void
  /** Selectable days, oldest first. Empty until /api/days resolves. */
  days: string[]
  setDays: (days: string[]) => void
  /** The newest day in the dataset, once known. */
  latest: string | null
}

const DayContext = createContext<DayState | null>(null)

export function DayProvider({ children }: { children: ReactNode }) {
  const [day, setDay] = useState<string | null>(null)
  const [days, setDays] = useState<string[]>([])

  const latest = days.length ? days[days.length - 1] : null

  // Selecting the newest day stores null, so "latest" stays a single concept
  // rather than two states that can disagree after the dataset changes.
  const select = useCallback(
    (next: string | null) => setDay(next && next === latest ? null : next),
    [latest],
  )

  const value = useMemo<DayState>(
    () => ({ day, setDay: select, days, setDays, latest }),
    [day, select, days, latest],
  )

  return <DayContext.Provider value={value}>{children}</DayContext.Provider>
}

export function useDay(): DayState {
  const ctx = useContext(DayContext)
  if (!ctx) throw new Error('useDay must be used inside <DayProvider>')
  return ctx
}

import { useEffect, useState } from 'react'

/**
 * Fire once on mount, expose loading state. Four endpoints do not justify a
 * data-fetching library.
 */
export function useFetch<T>(fetcher: () => Promise<T>, key?: string | number | null) {
  const [data, setData] = useState<T | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<Error | null>(null)

  useEffect(() => {
    let live = true
    setLoading(true)
    fetcher()
      .then((d) => live && setData(d))
      .catch((e: Error) => live && setError(e))
      .finally(() => live && setLoading(false))
    return () => {
      live = false
    }
    // Fetchers are inline arrows; depending on them would refetch every render.
    // `key` is the explicit opt-in: pass the selected day and the hook refetches
    // when it changes, which is how the whole dashboard follows the picker.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key])

  return { data, loading, error }
}

import { useEffect, useState } from 'react'

/**
 * Fire once on mount, expose loading state. Four endpoints do not justify a
 * data-fetching library.
 */
export function useFetch<T>(fetcher: () => Promise<T>) {
  const [data, setData] = useState<T | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<Error | null>(null)

  useEffect(() => {
    let live = true
    fetcher()
      .then((d) => live && setData(d))
      .catch((e: Error) => live && setError(e))
      .finally(() => live && setLoading(false))
    return () => {
      live = false
    }
    // Fetchers are inline arrows; depending on them would refetch every render.
    // Nothing in this app changes its endpoint after mount.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  return { data, loading, error }
}

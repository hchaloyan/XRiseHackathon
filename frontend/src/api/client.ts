import fixtures from '../mocks/fixtures.json'
import type {
  InsightResponse,
  KpiResponse,
  RootCauseResponse,
  SearchResponse,
} from './types'

const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...init,
  })
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
  return res.json() as Promise<T>
}

/**
 * Try the endpoint; fall back to the committed fixture if it is missing or
 * unreachable.
 *
 * Three of the four routers are still empty `APIRouter()` stubs, so this is
 * the normal path today, not an error path. It also means a backend that dies
 * mid-demo degrades to stale-but-correct numbers instead of a red screen
 * (spec §5).
 *
 * An `undefined` fixture rethrows: some rows have no canned analysis, and a
 * caller that can degrade honestly should be told so rather than handed
 * someone else's numbers.
 */
async function withFallback<T>(
  label: string,
  fetcher: () => Promise<T>,
  fixture: T | undefined,
): Promise<T> {
  try {
    return await fetcher()
  } catch (err) {
    if (fixture === undefined) throw err
    console.warn(`[api] ${label} unavailable, serving fixture:`, err)
    return fixture
  }
}

/**
 * Fixture-only lookup for the ask bar when the backend is down. Selects a
 * stored response by substring; it does NOT route between document search and
 * factory data (rule 8) — every branch returns one SearchResponse from the
 * same endpoint, and none of this runs when the backend answers.
 */
function cannedSearch(query: string): SearchResponse {
  const q = query.toLowerCase()
  const hit = fixtures.search.canned.find((c) => c.match.some((m) => q.includes(m)))
  const picked = (hit?.response ?? fixtures.search.default) as SearchResponse
  return { ...picked, query }
}

export const api = {
  kpis: () =>
    withFallback('GET /api/kpis', () => request<KpiResponse>('/api/kpis'), fixtures.kpis as KpiResponse),

  insights: () =>
    withFallback(
      'GET /api/insights',
      () => request<InsightResponse>('/api/insights'),
      fixtures.insights as InsightResponse,
    ),

  rootCause: (eventId: string) =>
    withFallback(
      `POST /api/root-cause ${eventId}`,
      () =>
        request<RootCauseResponse>('/api/root-cause', {
          method: 'POST',
          body: JSON.stringify({ eventId }),
        }),
      // Only the two demo-script rows have a canned analysis. Anything else
      // rethrows so the panel degrades to evidence built from the row itself,
      // rather than showing another machine's findings.
      (fixtures.rootCause as unknown as Record<string, RootCauseResponse | undefined>)[eventId],
    ),

  search: (query: string) =>
    withFallback(
      'POST /api/search',
      () => request<SearchResponse>('/api/search', { method: 'POST', body: JSON.stringify({ query }) }),
      cannedSearch(query),
    ),
}

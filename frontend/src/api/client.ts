/**
 * fetch wrapper. Base URL from env. JSON bodies, camelCase on the wire.
 */
import fixtures from '../mocks/fixtures.json'
import type {
  ExplainResponse,
  InsightResponse,
  KpiResponse,
  RootCauseResponse,
  SearchResponse,
  SopDocument,
} from './types'

/**
 * Dev runs on :5173 and must name the backend absolutely. The packaged desktop
 * app is served BY the backend, so it must not: the window is opened at
 * 127.0.0.1 and a baked "localhost" URL is a different origin to the browser,
 * which CORS then blocks. Relative paths make the question moot.
 */
const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? (import.meta.env.DEV ? 'http://localhost:8000' : '')

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...init,
  })
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
  return res.json() as Promise<T>
}

function post<T>(path: string, body: unknown): Promise<T> {
  return request<T>(path, { method: 'POST', body: JSON.stringify(body) })
}

/**
 * Try the endpoint; fall back to the committed fixture if it is missing or
 * unreachable.
 *
 * Insights and root cause are still empty `APIRouter()` stubs, so this is the
 * normal path for them today, not an error path. It also means a backend that
 * dies mid-demo degrades to stale-but-correct numbers instead of a red screen
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
      () => post<RootCauseResponse>('/api/root-cause', { eventId }),
      // Only the two demo-script rows have a canned analysis. Anything else
      // rethrows so the panel degrades to evidence built from the row itself,
      // rather than showing another machine's findings.
      (fixtures.rootCause as unknown as Record<string, RootCauseResponse | undefined>)[eventId],
    ),

  /**
   * Retrieval only — no model, so this returns in well under a second. It gets
   * no fixture fallback: the knowledge base is really implemented, and an
   * unreachable backend is reported through the UI's fallback message rather
   * than papered over with canned SOPs.
   *
   * Off-corpus queries are handled server-side by the similarity floor, which
   * returns zero results plus the fixed redirect string (rule 8 — no intent
   * classifier runs on the client).
   */
  search: (query: string) => post<SearchResponse>('/api/search', { query }),

  /** Model reasoning over the exact chunks the user already has on screen. */
  explain: (query: string, sopIds: string[]) =>
    post<ExplainResponse>('/api/explain', { query, sopIds }),

  /** The whole document behind a result. Read from disk, no model, no index. */
  sop: (docId: string) => request<SopDocument>(`/api/sops/${encodeURIComponent(docId)}`),
}

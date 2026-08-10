/**
 * fetch wrapper. Base URL from env. JSON bodies, camelCase on the wire.
 */
import type {
  ExplainResponse,
  InsightsResponse,
  KpiResponse,
  RootCauseResponse,
  SearchResponse,
} from './types'

const BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

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

export const searchSOPs = (query: string) =>
  post<SearchResponse>('/api/search', { query })

export const explainSOPs = (query: string, sopIds: string[]) =>
  post<ExplainResponse>('/api/explain', { query, sopIds })

export const getKpis = () => request<KpiResponse>('/api/kpis')

export const getInsights = () => request<InsightsResponse>('/api/insights')

export const analyzeRootCause = (eventId: string) =>
  post<RootCauseResponse>('/api/root-cause', { eventId })

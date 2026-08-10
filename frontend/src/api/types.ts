/**
 * Mirrors backend/app/schemas.py. Kept in sync BY HAND.
 *
 * Same two rules as the Python side (spec 4.1):
 *   - computed fields come from pandas and are always present
 *   - generated fields come from the LLM and are always `| null`
 *
 * Wire format is camelCase.
 */

// ===== Knowledge base =====

export interface SopResult {
  id: string // chunk id, e.g. "SOP-002#3"
  docId: string
  title: string
  section: string
  content: string
  distance: number
}

export interface SearchResponse {
  query: string
  results: SopResult[]
  /** Non-null only when nothing cleared the similarity floor (spec 7.1). */
  fallbackMessage: string | null
}

export interface ExplainStep {
  action: string
  why: string
}

export interface ExplainResponse {
  query: string
  sources: string[]
  explanation: string | null
  steps: ExplainStep[] | null
  commonMistake: string | null
  estimatedMinutes: number | null
}

// ===== Placeholders: fill in as each slice lands =====

export interface KpiResponse {
  [key: string]: unknown
}

export interface InsightsResponse {
  [key: string]: unknown
}

export interface RootCauseResponse {
  [key: string]: unknown
}

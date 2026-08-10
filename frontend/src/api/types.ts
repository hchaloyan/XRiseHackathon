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

/* The insights and root-cause shapes are defined in full further down — the
   placeholders that used to sit here were superseded by them. */

/** GET /api/kpis — all computed in pandas, none of it from the model. */

export interface KpiValues {
  oee: number
  availability: number
  performance: number
  quality: number
  scrapRate: number
  downtimeMinutes: number
  goodCount: number
  totalCount: number
}

export interface MachineKpi extends KpiValues {
  machineId: string
  name: string
  machineType: string
  /** Search terms: ' 3d printing', 'molder', 'cnc'. */
  keywords: string[]
  line: string
  cell: string
}

/** One point per day across the 14-day window. */
export interface TrendPoint extends KpiValues {
  day: string
}

/**
 * Downtime and quality rows share one shape so the table can sort them
 * together. Kind-specific fields are null on the other kind — computed,
 * not generated, despite being nullable.
 */
export interface EventRow {
  eventId: string
  kind: 'downtime' | 'quality'
  machineId: string
  machineName: string
  machineType: string
  line: string
  shift: string
  start: string

  durationMinutes: number | null
  reasonCode: string | null
  operatorNote: string | null

  defectType: string | null
  defectCount: number | null
}

export interface InventoryItem {
  partId: string
  description: string
  line: string
  uom: string
  onHand: number
  reorderPoint: number
  dailyUsage: number
  daysOfCover: number
  belowReorder: boolean
}

export interface Inventory {
  partsTracked: number
  partsBelowReorder: number
  lowestDaysOfCover: number
  items: InventoryItem[]
}

/** Event rows ride along here rather than in a fifth endpoint. */
export interface KpiResponse {
  day: string
  plant: KpiValues
  trend: TrendPoint[]
  machines: MachineKpi[]
  events: EventRow[]
  inventory: Inventory
}

/* ---------------------------------------------------------------------------
 * The three shapes below were defined here FIRST, ahead of the backend, so the
 * frontend could proceed against fixtures (spec §9: "contract lands here, both
 * tracks unblock"). Mirror them into schemas.py when those routers are built.
 * ------------------------------------------------------------------------ */

export type Severity = 'high' | 'medium' | 'low'

/** GET /api/insights */

export interface Callout {
  title: string
  detail: string
  severity: Severity
  /** Pre-formatted by pandas. The model quotes it; it never computes it. */
  metric: string | null
}

export interface InsightResponse {
  /** Computed. */
  day: string
  /** Generated — one line, gets the gradient treatment. */
  headline: string | null
  /** Generated — 2-4 sentences. */
  narrative: string | null
  /** Generated, ranked most severe first. */
  callouts: Callout[] | null
}

/** POST /api/root-cause */

export interface RootCauseRequest {
  eventId: string
}

/** Computed correlation, assembled in pandas before the model is called. */
export interface Evidence {
  label: string
  value: string
  detail: string | null
}

export interface Hypothesis {
  rank: number
  cause: string
  confidence: Severity
  reasoning: string
  /** Labels drawn from `evidence[]`, so the ranking is traceable to numbers. */
  supportingEvidence: string[]
  recommendedAction: string | null
}

export interface RootCauseResponse {
  eventId: string
  /** Computed — renders even when the model fails (spec §5). */
  evidence: Evidence[]
  /** Generated. */
  hypotheses: Hypothesis[] | null
}

/* POST /api/search and /api/explain live at the top of this file. The
   single-answer-plus-citations shape that used to sit here was written against
   a backend that was never built: the implemented knowledge base splits the
   work into retrieval (/search, no model) and reasoning (/explain). */

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

/**
 * One shape for all three outcomes. Switch on `kind`:
 *
 *   'results'      — sections cleared the similarity floor; render `results`.
 *   'conversation' — a greeting or capability question. Render `reply` as a
 *                    chat line and `suggestions` as clickable chips. Matched
 *                    by regex server-side: no model, ~1ms, never intercepts
 *                    a real question.
 *   'metric'       — asks for a figure the plant data holds. `reply` carries
 *                    the computed number and `metricDay` the day it is from.
 *                    Answered in pandas, never by a model.
 *   'general'      — the SOPs do not cover it, so a hosted model answered from
 *                    general knowledge. Render `reply` WITH `disclaimer`.
 *                    Factory-data questions never land here; they keep the
 *                    redirect, because a model inventing an OEE figure is the
 *                    worst failure this app has available to it.
 *   'off_topic'    — nothing cleared the floor (spec 7.1). Render
 *                    `fallbackMessage` plus `suggestions`.
 *
 * `fallbackMessage` is set on both non-results paths, so a UI that only
 * reads it still behaves correctly and simply ignores the richer fields.
 */
export interface SearchResponse {
  query: string
  kind: 'results' | 'conversation' | 'metric' | 'general' | 'off_topic'
  results: SopResult[]
  /** The spoken answer. Set on 'conversation' and on 'general'. */
  reply: string | null
  /**
   * Non-null only on 'general'. MUST be rendered alongside `reply` — it is
   * what stops a model's general knowledge being read as plant procedure.
   */
  disclaimer: string | null
  /**
   * Non-null only on 'metric'. The day the answer is about — the UI offers to
   * move the dashboard there, which is the real answer to "what was
   * yesterday's OEE": the figure, plus the day it belongs to.
   */
  metricDay: string | null
  /** True when metricDay is already on screen, so no jump is offered. */
  metricIsCurrent: boolean
  /** Example questions, all guaranteed to retrieve. Empty on 'results'. */
  suggestions: string[]
  /**
   * Set when the answer came from joining this query to the previous one —
   * "what about the 500T?" resolved against what was already on screen. Show
   * it, so the app never appears to answer a fragment by magic.
   */
  resolvedFrom: string | null
  fallbackMessage: string | null
}

/**
 * GET /api/documents — everything the assistant can answer from.
 *
 * `source` is the ONLY thing separating a hand-authored SOP from an uploaded
 * manual anywhere in the system. Both are chunked, embedded, cited and viewed
 * identically, which is what makes an upload searchable the moment it lands.
 */
export interface DocumentMeta {
  docId: string
  title: string
  source: 'sop' | 'upload'
  /** ".pdf", ".docx", ".md", ".txt", ".csv" */
  format: string
  department: string
  revision: string
  originalName: string
  storedName: string
  sizeBytes: number
  sha256: string
  /** ISO timestamp. Empty for SOPs read off disk. */
  uploadedAt: string
  /** Sections in the vector index. 0 means it is listed but not searchable. */
  chunks: number
  chars: number
}

export interface DocumentListResponse {
  documents: DocumentMeta[]
  /** Advertised by the API so the picker and the validator cannot disagree. */
  acceptedFormats: string[]
  maxBytes: number
}

/** GET /api/sops/{docId} — the whole document, for the in-app viewer. */
export interface SopDocument {
  docId: string
  title: string
  revision: string
  department: string
  /** Raw markdown, front matter already stripped. */
  markdown: string
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

/**
 * GET /api/days — which days the picker may offer.
 *
 * Days with no production are absent rather than empty: selecting one would
 * render a briefing full of zeroes that reads as a bug, not as a gap.
 */
export interface DaysResponse {
  days: string[]
  latest: string
  earliest: string
  /** The real calendar date, from the server. */
  today: string
  /**
   * How far the newest record lags today. Above 0 means the plant has not
   * reported since — the header says so rather than presenting an old shift
   * as the current one.
   */
  daysBehind: number
}

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
  /** What to do, not what to interpret. */
  status: 'reorder_now' | 'order_this_week' | 'ok'
  /** ISO date this part hits zero at current usage. */
  runsOutOn: string
  suggestedOrderQty: number
}

export interface Inventory {
  partsTracked: number
  partsBelowReorder: number
  lowestDaysOfCover: number
  /** The part that runs out first — named, so there is something to chase. */
  soonestPartId: string
  soonestDescription: string
  soonestDays: number
  soonestRunsOutOn: string
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
 * The shapes below were defined here FIRST, ahead of the backend, so the
 * frontend could proceed against fixtures (spec §9). The routers are now
 * built and schemas.py matches these names. Two additions were made when
 * they landed, both computed and both marked below: the KPI block on
 * InsightResponse, and `sources` on RootCauseResponse.
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

export interface WorstMachine {
  machineId: string
  name: string
  line: string
  oee: number
  downtimeMinutes: number
  scrapRate: number
}

export interface ReasonTotal {
  reasonCode: string
  minutes: number
  events: number
}

export interface InsightResponse {
  /** Computed. */
  day: string

  /**
   * Computed — ADDED when the router landed. Always present, so the header
   * renders real numbers even when every generated field below is null.
   * Without this the panel is empty exactly when the model is slow.
   */
  oee: number
  scrapRate: number
  downtimeMinutes: number
  /** Null only on the first day of the window. */
  oeeDelta: number | null
  worstMachines: WorstMachine[]
  downtimeByReason: ReasonTotal[]
  partsBelowReorder: number

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

/** The row that was clicked, echoed back. Computed. */
export interface EventContext {
  eventId: string
  kind: 'downtime' | 'quality'
  machineId: string
  machineName: string
  machineType: string
  line: string
  start: string
  shift: string
  durationMinutes: number | null
  reasonCode: string | null
  operatorNote: string | null
  defectType: string | null
  defectCount: number | null
}

/**
 * Computed — ADDED when the router landed. The SOP sections retrieved for
 * this event, so the panel can cite where the reasoning came from. Retrieval
 * picks these, not the model, so a cited document always exists.
 */
export interface SopCitation {
  docId: string
  title: string
  section: string
}

export interface RootCauseResponse {
  eventId: string
  /** Computed — all three render even when the model fails (spec §5). */
  event: EventContext
  evidence: Evidence[]
  sources: SopCitation[]
  /** Generated. */
  hypotheses: Hypothesis[] | null
  summary: string | null
}

/* POST /api/search and /api/explain live at the top of this file. The
   single-answer-plus-citations shape that used to sit here was written against
   a backend that was never built: the implemented knowledge base splits the
   work into retrieval (/search, no model) and reasoning (/explain). */

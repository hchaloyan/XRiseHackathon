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

// ===== KPI Insights (GET /api/insights) =====

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

/** One line of the morning narrative. Generated. */
export interface Finding {
  text: string
  action: string
}

export interface InsightsResponse {
  // Computed — always present, render these even if the model failed.
  day: string
  oee: number
  scrapRate: number
  downtimeMinutes: number
  /** Null only on the first day of the window. */
  oeeDelta: number | null
  worstMachines: WorstMachine[]
  downtimeByReason: ReasonTotal[]
  partsBelowReorder: number

  // Generated — null when the model fails or times out.
  headline: string | null
  findings: Finding[] | null
}

// ===== Root cause (POST /api/root-cause) =====

/** The row the user clicked. All computed. */
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

/** Supporting data point, computed in pandas. Render under the causes. */
export interface EvidenceItem {
  label: string
  detail: string
}

export interface SopCitation {
  docId: string
  title: string
  section: string
}

/** Generated. Ranked against the evidence. */
export interface RootCauseItem {
  cause: string
  likelihood: 'high' | 'medium' | 'low'
  evidence: string
  action: string
}

export interface RootCauseResponse {
  // Computed — always present.
  event: EventContext
  evidence: EvidenceItem[]
  sources: SopCitation[]

  // Generated — null when the model fails or times out. Evidence and
  // citations still render, so the panel stays useful.
  causes: RootCauseItem[] | null
  summary: string | null
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
}

export interface Inventory {
  partsTracked: number
  partsBelowReorder: number
  lowestDaysOfCover: number
  /** line → minutes lost to MATERIAL_STARVE on the selected day. */
  starvedMinutesByLine: Record<string, number>
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

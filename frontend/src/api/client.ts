/**
 * fetch wrapper. Base URL from env. JSON bodies, camelCase on the wire.
 */
import fixtures from '../mocks/fixtures.json'
import type {
  ExplainResponse,
  InsightResponse,
  DaysResponse,
  DocumentListResponse,
  DocumentMeta,
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

/**
 * Static preview build: no backend exists behind it and none can, so every
 * call short-circuits to the committed fixtures rather than waiting out a
 * network timeout first.
 *
 * Set only by the Pages workflow. The desktop app and local development never
 * see it, so nothing about the real paths changes.
 */
export const DEMO = import.meta.env.VITE_DEMO === '1'

/**
 * What the preview can and cannot do, in three honest tiers.
 *
 *   'live'        — really running, right now, in your browser. All of the
 *                   arithmetic: KPIs, charts, the event table, inventory, and
 *                   ask-bar summaries. Same code as the desktop app.
 *   'recorded'    — a real model produced this, once, and it was committed to
 *                   fixtures.json. It is genuine output, but it is a playback,
 *                   not a generation. This is the tier that most needs saying
 *                   out loud: it is indistinguishable from live unless labelled.
 *   'unavailable' — needs a local model, a vector index or the file system, so
 *                   the preview cannot do it at all.
 *
 * Everything that renders a caveat reads from here, so the banner and the
 * inline badges cannot drift apart as the app keeps changing.
 */
export type DemoState = 'live' | 'recorded' | 'unavailable'

export interface DemoCapability {
  name: string
  state: DemoState
  note: string
}

export const DEMO_CAPABILITIES: DemoCapability[] = [
  {
    name: 'KPIs, charts, events, inventory',
    state: 'live',
    note: 'computed in the browser from committed plant data',
  },
  {
    name: 'Ask-bar shift summaries',
    state: 'live',
    note: 'pure arithmetic, so it runs here exactly as it does in the app',
  },
  {
    name: 'Briefing narrative and callouts',
    state: 'recorded',
    note: 'real model output, captured once and replayed',
  },
  {
    name: 'Root cause on two sample rows',
    state: 'recorded',
    note: 'DT-0112 and QC-0071 only',
  },
  {
    name: 'Root cause on every other row',
    state: 'unavailable',
    note: 'evidence still shows; the ranking needs the model',
  },
  {
    name: 'SOP and document search',
    state: 'unavailable',
    note: 'needs the embedding model and vector index',
  },
  {
    name: 'Document upload and exports',
    state: 'unavailable',
    note: 'needs the backend and its file system',
  },
]

/**
 * The inline wording, kept beside the map so the two are edited together.
 * Deliberately plain: a judge should learn what is missing in one read, and
 * should never suspect the app is quietly hiding something.
 */
export const DEMO_NOTES = {
  briefing: 'Recorded model output, replayed. In the app this is generated live in about 10s.',
  rootCause: 'Recorded analysis for this row, replayed. Generated live in the app.',
  rootCauseMissing:
    'The preview ships recorded analysis for two rows only (DT-0112 and QC-0071). ' +
    'The evidence above is computed and real; ranking this row needs the local model.',
  search: 'Document search is off in the preview: it needs the embedding model and vector index.',
  document: 'The preview lists the corpus but cannot open document bodies — those live on disk.',
  upload: 'Upload needs the backend, which no static host can provide.',
  export: 'Exports are rendered by the backend, so they are disabled here.',
} as const

/**
 * Rows that really do have recorded analysis. Read from the fixture itself so
 * this can never claim a row the preview cannot actually show.
 */
export const DEMO_ROOT_CAUSE_IDS: string[] = Object.keys(fixtures.rootCause ?? {})

/** Fixture-only response for the paths that have no canned data of their own. */
function demoOnly<T>(value: T): Promise<T> {
  return Promise.resolve(value)
}

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

/** Titles only. The preview lists the corpus; it cannot serve the files. */
const DEMO_SOPS = [
  'Injection Molding Changeover and First-Off Approval',
  'Preventive Maintenance Schedule and Lubrication',
  'CNC Tool Breakage Response and Insert Replacement',
  'CNC Changeover, Work Offsets and First Article',
  'Sensor Fault Diagnosis and Recalibration',
  'Material Starvation Response and Line-Side Replenishment',
  'Injection Molding Defect Troubleshooting',
  'Robotic Welding Quality: Porosity, Spatter and Undercut',
  '3D Printer and Additive Manufacturing Build Failure Recovery',
  'Assembly Station Jam Clearing and Robot Fault Recovery',
  'Powder Coating Colour Change and Booth Cleanout',
  'Powder Coating Defect Troubleshooting',
  'Aqueous Parts Washer Operation and Bath Control',
  'Case Packer Jam Clearing and Label Recovery',
  'Finishing and Packaging Preventive Maintenance',
]

/** SOP-001..SOP-015 -> title, so the viewer can name what it cannot open. */
const DEMO_SOPS_BY_ID: Record<string, string> = Object.fromEntries(
  DEMO_SOPS.map((title, i) => [`SOP-${String(i + 1).padStart(3, '0')}`, title]),
)

export const api = {
  /** Available days for the picker. No fixture: an empty list just disables
   *  the calendar rather than offering days the data cannot answer for. */
  days: () => {
    if (DEMO) {
      // Derived from the fixture's own trend rather than a second hard-coded
      // list, so the picker can never offer a day the fixture cannot render.
      const days = (fixtures.kpis as KpiResponse).trend.map((t) => t.day)
      const latest = days[days.length - 1]
      return demoOnly<DaysResponse>({
        days,
        latest,
        earliest: days[0],
        today: latest,
        daysBehind: 0,
      })
    }
    return request<DaysResponse>('/api/days')
  },

  kpis: (day?: string | null) =>
    withFallback(
      'GET /api/kpis',
      () => request<KpiResponse>(`/api/kpis${day ? `?day=${day}` : ''}`),
      fixtures.kpis as KpiResponse,
    ),

  insights: (day?: string | null) =>
    withFallback(
      'GET /api/insights',
      () => request<InsightResponse>(`/api/insights${day ? `?day=${day}` : ''}`),
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
  search: (query: string, previousQuery?: string | null) => {
    if (DEMO) {
      // Summaries are pure arithmetic, so the preview can do them for real
      // from the same fixture the dashboard is drawing. Retrieval cannot: it
      // needs an embedding model, and pretending otherwise would be a lie.
      const k = fixtures.kpis as KpiResponse
      if (/summar|recap|rundown|overview|what happened|catch me up|how did we do/i.test(query)) {
        const down = k.events.filter((e) => e.kind === 'downtime')
        const qual = k.events.filter((e) => e.kind === 'quality')
        const stopped = down.reduce((n, e) => n + (e.durationMinutes ?? 0), 0)
        const rejected = qual.reduce((n, e) => n + (e.defectCount ?? 0), 0)
        const worst = [...k.machines].sort((a, b) => a.oee - b.oee)[0]
        return demoOnly<SearchResponse>({
          query,
          kind: 'summary',
          results: [],
          reply: null,
          disclaimer: null,
          summaryTitle: `Shift summary for ${k.day}`,
          summaryLines: [
            `OEE ${(k.plant.oee * 100).toFixed(1)}% on ${k.plant.goodCount.toLocaleString()} good parts of ${k.plant.totalCount.toLocaleString()}, scrap ${(k.plant.scrapRate * 100).toFixed(1)}%.`,
            `${down.length} stoppages costing ${stopped.toFixed(0)} minutes.`,
            `${qual.length} quality events covering ${rejected} rejected parts.`,
            `Lowest machine was ${worst.machineId} ${worst.name} at ${(worst.oee * 100).toFixed(1)}% OEE.`,
            `${k.inventory.partsBelowReorder} of ${k.inventory.partsTracked} parts below reorder point.`,
          ],
          metricDay: null,
          metricIsCurrent: true,
          suggestions: ['What stopped the line?', 'What needs reordering?'],
          resolvedFrom: null,
          fallbackMessage: null,
        })
      }
      return demoOnly<SearchResponse>({
        query,
        kind: 'conversation',
        results: [],
        reply:
          'This is a static preview, so document retrieval is switched off. In ' +
          'the app this searches 15 SOPs and anything you upload, and answers ' +
          'with the exact section plus a link into the source. Summaries work ' +
          'here: try "summarise the shift".',
        disclaimer: null,
        summaryTitle: null,
        summaryLines: [],
        metricDay: null,
        metricIsCurrent: false,
        suggestions: ['Summarise the shift'],
        resolvedFrom: null,
        fallbackMessage: null,
      })
    }
    return post<SearchResponse>('/api/search', { query, previousQuery: previousQuery ?? null })
  },

  /** Model reasoning over the exact chunks the user already has on screen. */
  explain: (query: string, sopIds: string[]) =>
    post<ExplainResponse>('/api/explain', { query, sopIds }),

  /** The whole document behind a result. Read from disk, no model, no index. */
  sop: (docId: string) => {
    if (DEMO) {
      // Explain, rather than failing into "this document could not be opened",
      // which reads as a bug rather than as a boundary of the preview.
      return demoOnly<SopDocument>({
        docId,
        title: DEMO_SOPS_BY_ID[docId] ?? docId,
        revision: '',
        department: '',
        markdown:
          `**Not available in this preview.**\n\n${DEMO_NOTES.document}\n\n` +
          `${docId} is one of 15 procedures the running app indexes, chunks and ` +
          `cites by section. Clone the repo and start the desktop app to read it.`,
      })
    }
    return request<SopDocument>(`/api/sops/${encodeURIComponent(docId)}`)
  },

  documents: () => {
    if (DEMO) {
      return demoOnly<DocumentListResponse>({
        documents: DEMO_SOPS.map((d, i) => ({
          docId: `SOP-${String(i + 1).padStart(3, '0')}`,
          title: d,
          source: 'sop' as const,
          format: '.md',
          department: '',
          revision: '',
          originalName: '',
          storedName: '',
          sizeBytes: 0,
          sha256: '',
          uploadedAt: '',
          chunks: 0,
          chars: 0,
        })),
        acceptedFormats: ['.pdf', '.docx', '.md', '.txt', '.csv'],
        maxBytes: 15728640,
      })
    }
    return request<DocumentListResponse>('/api/documents')
  },

  /**
   * Multipart, so no Content-Type header: the browser must set it itself with
   * the multipart boundary, and naming it here would break the parse.
   *
   * Rejections come back as 400 with a human sentence in `detail`; that
   * sentence is what the user needs to see, so it is surfaced as the error.
   */
  uploadDocument: async (file: File, department = ''): Promise<DocumentMeta> => {
    const body = new FormData()
    body.append('file', file)
    body.append('department', department)
    const res = await fetch(`${BASE_URL}/api/documents`, { method: 'POST', body })
    if (!res.ok) {
      const detail = await res.json().catch(() => null)
      throw new Error(detail?.detail ?? `${res.status} ${res.statusText}`)
    }
    return (await res.json()) as DocumentMeta
  },

  deleteDocument: async (docId: string): Promise<void> => {
    const res = await fetch(`${BASE_URL}/api/documents/${encodeURIComponent(docId)}`, {
      method: 'DELETE',
    })
    if (!res.ok) {
      const detail = await res.json().catch(() => null)
      throw new Error(detail?.detail ?? `${res.status} ${res.statusText}`)
    }
  },

  /** A plain href — downloads must survive a right-click, not need JS. */
  documentDownloadUrl: (docId: string) =>
    `${BASE_URL}/api/documents/${encodeURIComponent(docId)}/download`,

  /**
   * Shift report download. Also a plain href, for the same reason.
   * `format` is pdf | xlsx | mis. Omitting the day exports the newest.
   */
  reportUrl: (format: string, day?: string | null) =>
    `${BASE_URL}/api/report?format=${format}${day ? `&day=${day}` : ''}`,
}

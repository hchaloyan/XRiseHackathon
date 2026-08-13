# MFGX AI

An AI copilot for a manufacturing shift supervisor. It opens on the morning
briefing, drills into any event without navigating away, and answers questions
from the plant's own SOPs and manuals.

Built for the MFGX AI hackathon: *every manufacturing user should save at least
30 minutes per day using AI.*

- Design spec: [docs/superpowers/specs/2026-08-10-mfgx-ai-design.md](docs/superpowers/specs/2026-08-10-mfgx-ai-design.md)
- Working agreements: [CLAUDE.md](CLAUDE.md)

## What it does

**Briefing** — press Generate and the day's OEE, scrap, downtime and material
position come back as a headline, two or three sentences, and ranked callouts.
Every figure is computed in pandas first; the model only writes the prose around
numbers it was handed. **View full report** opens the same day in full — every
machine, every event, materials with order quantities, and the procedures that
cover the day's faults — exportable as PDF, Excel or MIS CSV.

**Root cause** — click any downtime or quality row and it expands in place.
Evidence is correlated in pandas *before* the model is called: recurrence on that
machine, what else happened within four hours, the machine's output that day,
and any part below its reorder point. The model ranks hypotheses against that
evidence and cites the SOP sections behind them.

**Ask bar** — persistent, answers from the document corpus. It also handles the
things a supervisor actually types: greetings, follow-up fragments
("what about the 500T?"), abbreviations (`IMM`, `PPE`, `OOT`), machine ids, and
British/American spelling. Questions about plant figures are answered from
computed data with a link to that day's briefing, never guessed at.

**Documents** — upload SOPs, manuals and audit records (PDF, DOCX, MD, TXT,
CSV). They are chunked, embedded and searchable within seconds, and cited by the
same machinery as the built-in corpus. Uploads are checked before indexing:
extension allowlist, magic bytes, size cap, SHA-256 dedupe, extractable text,
and a relevance test against the plant's own vocabulary.

**Any day** — the date picker moves the whole dashboard across the 30-day
window. When the newest record lags the calendar, the app says so rather than
presenting an old shift as today's.

## Prerequisites

Ollama, running locally, with both models pulled:

```bash
ollama pull qwen2.5:7b-instruct   # 4.7 GB — narrative, root cause
ollama pull nomic-embed-text      # 274 MB — retrieval
ollama serve
```

**Python 3.11+** and **Node 20.12+** (Vite 8 needs `node:util.styleText`; Node
22 LTS is the safe choice).

## Run as a desktop app

One process in a native window. Uvicorn serves the API *and* the built UI on the
same origin in a background thread — no second dev server, no CORS, no browser
chrome.

```bash
cd backend && python -m venv .venv && .venv/Scripts/activate
pip install -r requirements.txt
cd ../frontend && npm install && npm run build && cd ..
python backend/calibrate_kb.py --reindex   # build the vector index, see below
python run.py                              # or double-click start.bat on Windows
```

The window opens in about a second; the model warms behind it, so the first
briefing of a session may take a few seconds longer than later ones. Closing the
window stops the server.

`python run.py --browser` opens the default browser instead — the fallback if
the native window misbehaves on an unfamiliar machine.

The window renders `frontend/dist`, not your working tree, so **rebuild after
any UI change**. Use the two-server setup below for hot reload while developing.

## Setup for development

No `.env` is needed — every setting has a working default in
`backend/app/config.py`. Copy `.env.example` to `backend/.env` only to add a
Groq key or switch inference to the hosted fallback.

**Backend** (`:8000`):

```bash
cd backend
python -m venv .venv
.venv/Scripts/activate        # Windows
# source .venv/bin/activate   # macOS / Linux
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

**Frontend** (`:5173`, hot reload — talks to `:8000`):

```bash
cd frontend
npm install
npm run dev
```

Do not create `frontend/.env`. `VITE_API_BASE_URL` is baked in at build time,
and a `localhost` value makes the packaged app a different origin from the
window's `127.0.0.1`, which CORS then blocks — the app silently falls back to
fixtures and looks fine while showing canned data.

Check `http://localhost:8000/health` before debugging anything else.

## The vector index

SOPs and uploads are chunked, embedded with `nomic-embed-text` and stored in a
persistent Chroma collection under `backend/chroma/` (gitignored).

```bash
python backend/calibrate_kb.py            # report distances against the index
python backend/calibrate_kb.py --reindex  # rebuild it first
```

Reindex after editing any SOP or changing the embedding model. The script also
calibrates `MAX_MATCH_DISTANCE`, the similarity floor that decides when the ask
bar says "I answer from SOPs and manuals" instead of returning an irrelevant
procedure. It prints two query sets — questions the corpus answers and factory
data questions it must not — and **exits non-zero if more than one data question
gets through**.

## The dataset

Committed, so every teammate sees identical numbers. 15 machines across 5 lines,
30 days, 20 inventory parts, 15 SOPs.

```bash
python data/seed.py          # run ONCE, output committed, never re-run
python data/seed_append.py   # dry run: what an expansion would add
python data/seed_append.py --write
```

`seed_append.py` is append-only: it reads what `seed.py` produced and adds to
it, leaving every existing row's id, timestamp and numbers untouched.

Three narratives are planted in the data for root cause to find — a changeover
that overruns every shift B on M-22, a defect spike following one changeover on
M-31, and a silent cycle-time drift on M-13 with no downtime events at all.
`backend/test_kpi_engine.py` asserts all three still hold.

## Layout

```
data/               seed.py, seed_append.py, generated JSON, 15 SOP markdown files
backend/app/
  routers/          kpis, insights, root_cause, search, documents
  services/         kpi_engine (all arithmetic), knowledge_base, documents,
                    root_cause, metric_query, query_expansion, conversation, report
  llm/              base.py interface, ollama_client, hosted_client
  prompts/          markdown, not string literals
frontend/src/
  sections/         AskBar, InsightHeader, KpiGrid, EventTable, RootCausePanel,
                    InventoryPanel, DocumentsPanel
  components/       DayPicker, ReportDialog, SopViewer, ui/
  lib/              day context, useFetch, formatting
run.py              desktop launcher
```

## Rules that matter

1. **The model never does arithmetic.** Every OEE, scrap, downtime and inventory
   figure comes from pandas in `kpi_engine.py`. The LLM writes narrative and
   ranks hypotheses; it is handed numbers and never asked to produce one.
2. **All model calls go through `llm/base.py`**, switched by `LLM_PROVIDER`. A
   per-call override sends only the general-knowledge answers to a hosted model,
   so nothing computed from plant data depends on an external service.
3. **Structured output via JSON schema**, never by asking politely. Array bounds
   live in the schema.
4. **`schemas.py` is the contract.** Mirror it into `api/types.ts` by hand.
5. **Root cause expands inline**, never as a modal or a route. The app grew to
   three screens at the team's decision, but the drill-down never navigates away
   — insight, evidence, answer, all in place.
6. **Degrade, never fail.** Computed fields always render; generated fields are
   nullable. If the model is down, the briefing shows real numbers and says the
   narrative is unavailable.
7. **The ask bar does not classify intent.** Metric questions are caught by name
   against a closed vocabulary, off-corpus questions by a calibrated similarity
   floor. Neither is a model deciding where your question should go.

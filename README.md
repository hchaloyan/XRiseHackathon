# MFGX AI

An AI copilot for a manufacturing shift supervisor. It opens on the morning
briefing. You drill into any event without navigating away, and it answers your
questions from the plant's own SOPs and manuals.

Built for the MFGX AI hackathon: *every manufacturing user should save at least
30 minutes per day using AI.*

**Live preview, no install:** https://hchaloyan.github.io/XRiseHackathon/

---

## What it does

**Briefing.** Press Generate. The day's OEE, scrap, downtime and material
position come back as a headline, two or three sentences, and ranked callouts.
pandas computes every figure first, and the model only writes prose around
numbers it was handed. **View full report** opens the same day in full: every
machine, every event, materials with order quantities, and the procedures
covering the day's faults. You can export that report as PDF, Excel or MIS CSV.

**Root cause.** Click any downtime or quality row and it expands in place. The
app correlates evidence in pandas *before* it calls the model: recurrence on
that machine, what else happened within four hours, the machine's output that
day, and any part below its reorder point. The model then ranks hypotheses
against that evidence and cites the SOP sections behind them.

**Ask bar.** The bar stays on screen and answers from the document corpus. It
handles what a supervisor actually types: greetings, follow-up fragments ("what
about the 500T?"), abbreviations (`IMM`, `PPE`, `OOT`), and machine ids. Ask
what happened and it tells you rather than pointing at a table. "summarise the
shift", "what stopped the line", "how is M-22 doing", "what needs reordering"
and about thirty other phrasings all return the numbers in the chat. pandas
assembles every line, so a summary is exactly as trustworthy as the dashboard
and costs no model call.

**Documents.** Upload SOPs, manuals and audit records (PDF, DOCX, MD, TXT,
CSV). The app chunks and embeds them, makes them searchable within seconds, and
cites them through the same machinery as the built-in corpus. It checks every
upload before indexing: extension allowlist, magic bytes, size cap, SHA-256
dedupe, extractable text, and a relevance test against the plant's own
vocabulary.

**Any day.** Use the date picker to move the whole dashboard across the 30-day
window. When the newest record lags the calendar, the app says so rather than
presenting an old shift as today's.

---

## The preview link

The Pages build runs the real UI on the committed sample data in
`frontend/src/mocks`. You can click through the briefing, change the date, open
an event, read the full report and see the document list.

No backend sits behind it, so some capabilities run live and others are
replayed recordings. The preview labels all three states rather than leaving
you to guess. Every caveat reads from one map in `frontend/src/api/client.ts`
(`DEMO_CAPABILITIES`), so the banner and the inline badges cannot drift apart:

| | What | Why |
|---|---|---|
| **Live** | KPIs, charts, event table, inventory, ask-bar summaries | pure arithmetic, so it runs in the browser exactly as it does in the app |
| **Recorded** | Briefing narrative and callouts; root cause on `DT-0112` and `QC-0071` | real model output, captured once and replayed, then badged in place, because a replay is otherwise indistinguishable from a live generation |
| **Off** | SOP search, root cause on other rows, upload, exports | needs a local model, the vector index or the file system |

The preview disables controls that cannot work rather than leaving them live,
so nothing fails silently in front of a reader. It also marks the two rows
carrying a recorded analysis in the event table, so you know which to open.

Every push to `main` publishes the preview automatically
([.github/workflows/pages.yml](.github/workflows/pages.yml)). Enable it once
under **Settings → Pages → Source: GitHub Actions**. The workflow sets
`BASE_PATH` for the project subpath and copies `index.html` to `404.html`.
Pages has no rewrite rules, so without that copy a deep link would miss the
router.

---

## Running it

### Prerequisites

Run Ollama locally with both models pulled:

```bash
ollama pull qwen2.5:7b-instruct   # 4.7 GB, narrative and root cause
ollama pull nomic-embed-text      # 274 MB, retrieval
ollama serve
```

You also need **Python 3.11+** and **Node 20.12+**. Vite 8 needs
`node:util.styleText`, so Node 22 LTS is the safe choice.

You do not need a `.env` file. Every setting has a working default in
`backend/app/config.py`. Copy `.env.example` to `backend/.env` only to add a
Groq key or to switch inference to the hosted fallback. Without that key, the
ask bar returns its standard redirect for questions the SOPs do not cover, and
every other feature works as normal.

### As a desktop app

The app runs as one process in a native window. Uvicorn serves the API *and*
the built UI on the same origin from a background thread. That means no second
dev server, no CORS and no browser chrome.

Run one command per line. Windows PowerShell 5.1 does not understand `&&`,
which arrived in PowerShell 7. `;` is a poor substitute, because it runs the
next command even when the previous one failed.

```powershell
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

cd ..\frontend
npm install
npm run build

cd ..
python backend\calibrate_kb.py --reindex   # build the vector index
python run.py                              # or double-click start.bat
```

macOS and Linux, same order:

```bash
cd backend && python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cd ../frontend && npm install && npm run build && cd ..
python backend/calibrate_kb.py --reindex
python run.py
```

The window opens in about a second. The model warms up behind it, so the first
briefing of a session may take a few seconds longer than later ones. Closing
the window stops the server. `python run.py --browser` opens the default
browser instead. Use that fallback if the native window misbehaves on an
unfamiliar machine.

The window renders `frontend/dist`, not your working tree. **Rebuild after any
UI change**, or use the two-server setup below.

### For development

**Backend** (`:8000`):

```powershell
cd backend
python -m venv .venv
.venv\Scripts\activate        # Windows;  source .venv/bin/activate  elsewhere
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

**Frontend** (`:5173`, hot reload, talks to `:8000`):

```bash
cd frontend
npm install
npm run dev
```

Do not create `frontend/.env`. Vite bakes `VITE_API_BASE_URL` in at build time.
A `localhost` value makes the packaged app a different origin from the window's
`127.0.0.1`, and CORS then blocks it. The app silently falls back to fixtures
and looks fine while showing canned data.

Check `http://localhost:8000/health` before debugging anything else.

---

## Internals

### Rules that matter

1. **The model never does arithmetic.** Every OEE, scrap, downtime and
   inventory figure comes from pandas in `kpi_engine.py`. The LLM writes
   narrative and ranks hypotheses. You hand it numbers and never ask it to
   produce one.
2. **All model calls go through `llm/base.py`**, switched by `LLM_PROVIDER`. A
   per-call override sends only general-knowledge answers to a hosted model.
   Nothing computed from plant data depends on an external service.
3. **Structured output via JSON schema**, never by asking politely. Array
   bounds live in the schema.
4. **`schemas.py` is the contract.** Mirror it into `api/types.ts` by hand.
5. **Root cause expands inline**, never as a modal or a route. The app grew to
   three screens at the team's decision, but the drill-down never navigates
   away. You get insight, evidence and answer in place.
6. **Degrade, never fail.** Computed fields always render, and generated fields
   are nullable. If the model is down, the briefing shows real numbers and says
   the narrative is unavailable.
7. **The ask bar does not classify intent.** It catches metric questions by
   name against a closed vocabulary. It catches summaries with a closed set of
   shift phrasings that must also name something on the floor. It catches
   off-corpus questions with a calibrated similarity floor. None of these is a
   model deciding where your question should go. A regex you can read decides
   that "show me the downtime" is a summary and "show me the changeover steps"
   is a document search.

### The vector index

The app chunks SOPs and uploads, embeds them with `nomic-embed-text`, and
stores them in a persistent Chroma collection under `backend/chroma/`
(gitignored).

```bash
python backend/calibrate_kb.py            # report distances against the index
python backend/calibrate_kb.py --reindex  # rebuild it first
```

Reindex after you edit any SOP or change the embedding model. The script also
calibrates `MAX_MATCH_DISTANCE`. That is the similarity floor that decides when
the ask bar says "I answer from SOPs and manuals" instead of returning an
irrelevant procedure. The script prints three query sets: questions the corpus
answers, factory data questions it must not, and document references like
`SOP-003` that bypass the floor entirely. It **exits non-zero if more than one
data question gets through**.

### The dataset

The dataset is committed, so every teammate sees identical numbers. It covers
15 machines across 5 lines, 30 days, 20 inventory parts and 15 SOPs.

```bash
python data/seed.py          # run ONCE, output committed, never re-run
python data/seed_append.py   # dry run: what an expansion would add
python data/seed_append.py --write
```

`seed_append.py` is append-only. It reads what `seed.py` produced and adds to
it, and it leaves every existing row's id, timestamp and numbers untouched.

The data carries three planted narratives for root cause to find:

- a changeover that overruns every shift B on M-22,
- a defect spike following one changeover on M-31,
- a silent cycle-time drift on M-13 with no downtime events at all.

`backend/test_kpi_engine.py` asserts that all three still hold.

### Layout

```
data/               seed.py, seed_append.py, generated JSON, 15 SOP markdown files
backend/app/
  routers/          kpis, insights, root_cause, search, documents
  services/         kpi_engine (all arithmetic), knowledge_base, documents,
                    root_cause, metric_query, summary_query, query_expansion,
                    conversation, report
  llm/              base.py interface, ollama_client, hosted_client
  prompts/          markdown, not string literals
frontend/src/
  sections/         AskBar, InsightHeader, KpiGrid, EventTable, RootCausePanel,
                    InventoryPanel, DocumentsPanel
  components/       DayPicker, ReportDialog, SopViewer, ui/
  lib/              day context, useFetch, formatting
run.py              desktop launcher
```
</content>

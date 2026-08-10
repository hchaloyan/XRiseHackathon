# CLAUDE.md

Guidance for Claude Code working in this repository.

## What this is

An 8-hour hackathon submission for the **MFGX AI** problem statement: *every manufacturing user should save at least 30 minutes per day using AI.*

**This is one app with one screen, not three tools behind three tabs.** A supervisor opens it once in the morning and everything resolves in place. Three capabilities, in build priority order:

1. **KPI Insights** — daily auto-generated narrative on OEE, scrap, downtime, and inventory. Renders on load; the user never has to ask for it.
2. **Root Cause Analysis** — clicking any downtime or quality row expands it in place into ranked likely causes with supporting data points.
3. **Knowledge Base / SOP Search** — a persistent ask bar answering from SOPs, manuals, and audit docs with cited source sections.

The demo narrative is a time comparison: *"this supervisor's morning routine is 35 minutes in Excel; here it is in 40 seconds."* That story only lands if it is one continuous flow — insight, drill-down, answer — without navigation between them. Every scope decision serves that comparison.

## Hard constraints

- **8 hours, total.** Code freeze at hour 7:00. The last hour is demo rehearsal, not development.
- **Demo-first.** If a feature cannot be shown in a five-minute demo, it does not get built.
- **No new infrastructure.** No Postgres, no Docker, no message queues, no auth.

## Stack

| Layer | Choice | Notes |
|---|---|---|
| Frontend | React + TypeScript, Vite | Tailwind for styling, Recharts for charts |
| Transport | REST over HTTP | JSON only, no streaming, no websockets |
| Backend | Python + FastAPI | Pydantic models are the API contract |
| Data | pandas over committed JSON/CSV | No database server |
| Vector store | ChromaDB, persistent client, in-process | `where` filters handle metadata |
| Embeddings | `nomic-embed-text` via Ollama | Reuses the Ollama dependency; no sentence-transformers |
| Inference | Ollama, `qwen2.5:7b-instruct` | vLLM only if a teammate already has it running on a 24GB+ GPU |

## Repository layout

```
mfgx-ai/
├── CLAUDE.md
├── README.md
├── .env.example
│
├── data/
│   ├── seed.py                    # run ONCE, commit the output, never touch again
│   ├── generated/
│   │   ├── machines.json          # machine_id, line, cell, ideal_cycle_time
│   │   ├── production_runs.json   # run_id, machine_id, start, end, good_count, total_count
│   │   ├── downtime_events.json   # event_id, machine_id, start, end, reason_code, operator_note
│   │   └── quality_events.json    # event_id, machine_id, defect_type, count, timestamp
│   └── sops/                      # 5-8 markdown docs, hand-written, realistic
│       ├── SOP-001-line-changeover.md
│       ├── SOP-002-preventive-maintenance.md
│       └── ...                    # front-matter: doc_id, title, revision, department
│
├── backend/
│   ├── requirements.txt
│   ├── .env
│   ├── chroma/                    # persisted index — gitignored
│   └── app/
│       ├── main.py                # FastAPI app, CORS middleware, router registration
│       ├── config.py              # env-driven settings
│       ├── schemas.py             # ALL Pydantic request/response models — single source of truth
│       ├── routers/
│       │   ├── kpis.py            # GET  /api/kpis
│       │   ├── insights.py        # GET  /api/insights
│       │   ├── root_cause.py      # POST /api/root-cause
│       │   └── search.py          # POST /api/search
│       ├── services/
│       │   ├── data_loader.py     # load JSON into DataFrames once at startup, cache in module state
│       │   ├── kpi_engine.py      # ALL arithmetic lives here — pure pandas, zero LLM
│       │   ├── root_cause.py      # correlate events, assemble evidence, then call the model
│       │   └── knowledge_base.py  # chunk, embed, index, query
│       ├── llm/
│       │   ├── base.py            # abstract interface: complete(prompt, schema) -> dict
│       │   ├── ollama_client.py   # local, default
│       │   └── hosted_client.py   # fallback, selected by LLM_PROVIDER env var
│       └── prompts/
│           ├── kpi_insights.md
│           ├── root_cause.md
│           └── sop_answer.md      # prompts as files, not string literals in code
│
└── frontend/
    ├── package.json
    ├── tailwind.config.js
    └── src/
        ├── main.tsx
        ├── App.tsx
        ├── api/
        │   ├── client.ts          # fetch wrapper, base URL from env
        │   └── types.ts           # mirrors backend schemas.py — keep them in sync by hand
        ├── mocks/
        │   └── fixtures.json      # sample responses; build UI against these before the API exists
        └── sections/              # stacked on one screen — NO router, no tabs
            ├── AskBar.tsx         # persistent, top of viewport → /api/search
            ├── InsightHeader.tsx  # generated narrative, renders on load → /api/insights
            ├── KpiGrid.tsx        # cards + Recharts → /api/kpis
            ├── EventTable.tsx     # downtime/quality rows, each expandable
            └── RootCausePanel.tsx # inline expansion of a row → /api/root-cause
```

## Architectural rules

These are not stylistic preferences. Breaking them is how this project fails on stage.

1. **The model never does arithmetic.** Every OEE, scrap rate, downtime total, and availability figure is computed in `kpi_engine.py` with pandas. The LLM receives pre-aggregated numbers and produces narrative and ranked hypotheses only. A wrong OEE figure in front of manufacturing judges ends the project.

2. **All model calls go through `llm/base.py`.** One function signature, two implementations, switched by `LLM_PROVIDER`. If the local model is slow or incoherent at hour six, this is a one-variable change instead of a refactor under pressure.

3. **Structured output via schema, not prompting.** Pass a JSON schema to Ollama's `format` parameter. A 7B model asked politely for JSON will drift by the third call.

4. **`schemas.py` is the contract.** Define the response shapes before writing logic, mirror them into `api/types.ts`, and have the frontend build against `mocks/fixtures.json`. This is what lets frontend and backend proceed in parallel instead of serially.

5. **Prompts live in `prompts/` as markdown files.** Iterating on a prompt should not require touching Python.

6. **No LangChain.** For four endpoints it is abstraction you will spend time fighting.

7. **One screen. No react-router, no tabs, no modals.** Root cause expands inline inside the event table; it is not a separate view. If a capability cannot be reached without navigating away, the demo loses its continuity.

8. **The ask bar hits `/api/search` only.** Do not build an intent classifier that routes free-text between document search and factory data — it is the highest-risk, lowest-visibility component in the project, and it fails silently on stage. Document questions go in the bar; data questions are answered by clicking the row.

## Build order

Sequenced so that something demoable exists at every checkpoint.

| Time | Milestone |
|---|---|
| 0:00–0:45 | Scaffold both apps. `data/seed.py` runs and commits output. CORS configured. One endpoint returns a hardcoded fixture and the frontend renders it. **Vertical slice before depth.** |
| 0:45–2:00 | `kpi_engine.py` — real numbers from real DataFrames. `KpiGrid` and `EventTable` render live. This is a working demo with zero AI. |
| 2:00–3:30 | KPI Insights. Wire `llm/`, add the insights prompt, `InsightHeader` renders generated narrative on load. |
| 3:30–5:00 | Root Cause Analysis. Evidence assembly first, model call second, inline expansion last. |
| 5:00–6:15 | Knowledge Base. Chunk SOPs, index into Chroma, `AskBar` returns answers with source citations. |
| 6:15–7:00 | Polish the single screen top to bottom. It is the only thing judges see. |
| 7:00–8:00 | **Code freeze.** Rehearse the demo end to end at least three times. |

If you are behind at 5:00, cut the Knowledge Base. KPI Insights and Root Cause carry the 30-minute claim on their own.

## Setup order for the team

Do these before the clock starts, not at hour zero:

- `ollama pull qwen2.5:7b-instruct` and `ollama pull nomic-embed-text` — pulling 5GB over venue wifi is a classic way to lose the first hour.
- Confirm `ollama run qwen2.5:7b-instruct` responds locally.
- Node and Python toolchains installed and verified on every machine.

## Explicitly out of scope

Authentication. User accounts. Docker. Any database server. Websockets or streaming responses. Mobile responsive layouts. Test coverage beyond a smoke check that endpoints return 200. Multi-tenancy. Real-time data ingestion. Email/WhatsApp integration. Dashboard builder. Meeting summaries.

Do not add these. Do not suggest adding these.

## Conventions

- Snake_case in Python, camelCase in TypeScript. Convert at the serialization boundary via Pydantic aliases.
- Backend runs on `:8000`, frontend on `:5173`. Both hardcoded.
- Commit the generated data. Reproducibility of the seed script matters less than every teammate having identical numbers.
- Small commits, push often. Merge conflicts at hour six are expensive.

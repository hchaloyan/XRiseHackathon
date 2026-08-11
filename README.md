# MFGX AI

AI-powered manufacturing copilot. One screen: a supervisor opens it in the morning and their whole routine resolves in place — daily KPI narrative, inline root-cause analysis, and SOP search.

Built for the MFGX AI hackathon: *every manufacturing user should save at least 30 minutes per day using AI.*

- Design spec: [docs/superpowers/specs/2026-08-10-mfgx-ai-design.md](docs/superpowers/specs/2026-08-10-mfgx-ai-design.md)
- Working agreements: [CLAUDE.md](CLAUDE.md)

## Prerequisites

Ollama, running locally, with both models pulled:

```bash
ollama pull qwen2.5:7b-instruct   # 4.7 GB
ollama pull nomic-embed-text      # 274 MB
ollama serve
```

Python 3.11+ and Node 20+.

## Run as a desktop app

One process in a native window. Uvicorn serves the API *and* the built UI on the
same origin in a background thread — no second dev server, no CORS, no browser
chrome. Build the UI once, then launch:

```bash
cd frontend && npm install && npm run build && cd ..
python run.py            # or double-click start.bat on Windows
```

The window opens once the model pre-warm finishes. Closing it stops the server.

`python run.py --browser` opens the default browser instead — the fallback if
the native window misbehaves on an unfamiliar machine.

The window renders `frontend/dist`, not your working tree, so rebuild after any
UI change. Use the two-server setup below for hot reload while developing.

## Setup

No `.env` needed — every setting defaults correctly in `backend/app/config.py`.
Copy `.env.example` to `backend/.env` only if you switch to the hosted model
fallback.

**Backend** (`:8000`):

```bash
cd backend
python -m venv .venv
.venv/Scripts/activate        # Windows
# source .venv/bin/activate   # macOS / Linux
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

**Frontend** (`:5173`, hot reload — talks to `:8000` via `VITE_API_BASE_URL`):

```bash
cd frontend
npm install
npm run dev
```

Check `http://localhost:8000/api/health` before debugging anything else.

## Generating the dataset

Run once. The output is committed so every teammate has identical numbers.

```bash
python data/seed.py
```

## Layout

```
data/          seed.py, generated JSON, hand-written SOP markdown
backend/app/   FastAPI: routers, services (all arithmetic), llm/, prompts/
frontend/src/  One screen: api/, mocks/, sections/
```

## Rules that matter

1. **The model never does arithmetic.** Every OEE, scrap, and downtime figure comes from pandas in `kpi_engine.py`. The LLM only writes narrative and ranks hypotheses.
2. **All model calls go through `llm/base.py`**, switched by `LLM_PROVIDER`.
3. **Structured output via JSON schema**, never by asking politely. Array bounds go in the schema.
4. **`schemas.py` is the contract.** Mirror it into `api/types.ts` by hand.
5. **One screen.** No router, no tabs, no modals — root cause expands inline.
6. **Degrade, never fail.** Computed fields always render; generated fields are nullable.

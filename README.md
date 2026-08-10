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

## Setup

```bash
cp .env.example backend/.env
```

**Backend** (`:8000`):

```bash
cd backend
python -m venv .venv
.venv/Scripts/activate        # Windows
# source .venv/bin/activate   # macOS / Linux
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

**Frontend** (`:5173`):

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

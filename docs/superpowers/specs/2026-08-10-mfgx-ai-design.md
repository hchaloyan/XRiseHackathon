# MFGX AI — Design Spec

**Date:** 2026-08-10
**Status:** Approved, pending implementation plan
**Supersedes:** portions of `CLAUDE.md` (deltas explicitly marked below)

## 1. Purpose

An 8-hour hackathon submission for the MFGX AI problem statement: *every manufacturing user should save at least 30 minutes per day using AI.*

One app, one screen. A supervisor opens it once in the morning and their entire routine resolves in place — no navigation, no tabs, no modals. The demo is a time comparison: **"this supervisor's morning routine is 35 minutes in Excel; here it is in 40 seconds."** Every scope decision in this document serves that comparison.

## 2. Verified environment

Confirmed working before the design was finalized. These are measurements, not assumptions.

| Item | Status |
|---|---|
| Python | 3.11.9 |
| Node / npm | 24.11.0 / 11.6.1 |
| GPU | RTX 3060 Ti, **8192 MiB VRAM**, driver 591.86 |
| System RAM | 23.9 GB |
| Ollama server | 0.30.10, running on `:11434` |
| `qwen2.5:7b-instruct` | Pulled, 4.7 GB — fits fully in VRAM |
| `nomic-embed-text` | Pulled, 274 MB |
| Structured output (`format` param) | **Validated** — returned valid parseable JSON on first attempt |
| Cold generation latency | 221 tokens in **10.5 s**, including model load |

Two findings from the structured-output test drive design decisions below:

1. Asked for *two* items, the model returned *three*. Count constraints must live in the JSON schema, not the prompt.
2. ~10 s cold latency includes model load. A startup pre-warm removes that portion.

## 3. Locked decisions

| # | Decision | Rationale |
|---|---|---|
| D1 | **Ollama local** is the demo-day inference path | Fully offline, no venue-wifi dependency, no API key. Hardware verified sufficient. |
| D2 | Insights narrative is **generated when the page opens**, with a loading skeleton | User's explicit call. Matches `CLAUDE.md` as written. |
| D3 | Backend fires a throwaway `keep_alive: "30m"` call at startup | Makes the model VRAM-resident. Removes model-load time from every request. Does **not** cache output — narrative is still generated fresh per page open. |
| D4 | **Knowledge Base / SOP search is core and protected** | *Delta from `CLAUDE.md`.* It is the clearest "30 minutes saved" story of the five named features. |
| D5 | **Root Cause Analysis is the cuttable feature** if behind at hour 5 | *Delta from `CLAUDE.md`*, which named the Knowledge Base as cuttable. Follows from D4. |
| D6 | Data is **fully synthetic** via `seed.py`, run once and committed | No organizer dataset. Reproducibility matters less than every teammate having identical numbers. |
| D7 | No intent classifier on the ask bar | Retains `CLAUDE.md` rule #8. Mitigated by the threshold guard in §7. |

## 4. Architecture

Unchanged from `CLAUDE.md`: React + TypeScript + Vite + Tailwind + Recharts frontend on `:5173`; Python + FastAPI backend on `:8000`; pandas over committed JSON; ChromaDB persistent client in-process; REST/JSON only.

The eight architectural rules in `CLAUDE.md` remain in force. Two are load-bearing enough to restate:

- **Rule 1 — the model never does arithmetic.** Every OEE, scrap rate, downtime total, and availability figure is computed in `kpi_engine.py` with pandas. The LLM receives pre-aggregated numbers and produces narrative and ranked hypotheses only.
- **Rule 2 — all model calls go through `llm/base.py`.** One signature, two implementations, switched by `LLM_PROVIDER`.

### 4.1 Computed vs. generated separation

Every response model splits fields into two categories:

- **Computed** — produced by pandas. Always present. Never nullable.
- **Generated** — produced by the LLM. Always nullable.

This is the structural expression of rule 1, and it is what makes §5 possible.

## 5. Error handling: degrade, never fail

**No endpoint returns 5xx because the model misbehaved.**

If Ollama times out, is unreachable, or emits unparseable JSON, the endpoint returns its computed fields with the generated fields set to `null`. The frontend renders the numbers and collapses the narrative slot.

On stage, a missing paragraph is invisible. A red error screen ends the demo.

Timeouts: 30 s on insights and root cause, 20 s on SOP answer generation. On timeout, return computed-only rather than waiting.

## 6. Data design

`seed.py` runs once, output is committed, and it is never run again. Schema per `CLAUDE.md`: `machines.json`, `production_runs.json`, `downtime_events.json`, `quality_events.json`.

### 6.0 Volume

Sized so the event table is scrollable and realistic without being slow to scan on stage:

- **3 lines**, **4 machines each** = 12 machines
- **14 days** of history, ending "yesterday"
- **2 shifts/day** (A and B), which is what makes the shift-B pattern in §6.1 visible
- ~**340** production runs, ~**120** downtime events, ~**90** quality events

The dashboard defaults to the most recent full day. The 14-day window exists so trend charts and the cycle-time drift have something to plot against.

### 6.1 Planted patterns

Uniform random data gives root-cause analysis nothing to find and produces generic filler. The seed deliberately plants three discoverable signals, and the demo script walks them in order:

1. **Recurring changeover overrun** — one machine, concentrated on shift B, `reason_code CHANGEOVER` events running consistently long. The headline root-cause find.
2. **Correlated quality spike** — a defect type whose rate jumps immediately after a specific changeover event, so cause and effect must be correlated *across two different event tables*.
3. **Silent cycle-time drift** — one machine slowly degrading against its `ideal_cycle_time`, depressing OEE without ever raising a downtime event. This is the "you would never catch this in Excel" moment.

## 7. Knowledge Base

5–8 hand-written realistic SOP markdown docs with front-matter (`doc_id`, `title`, `revision`, `department`). Chunked, embedded via `nomic-embed-text`, indexed into a persistent Chroma collection. Answers cite their source sections.

### 7.1 Out-of-scope query guard

Rule #8 keeps the ask bar pointed at `/api/search` only, with no intent routing. But a judge will type *"what was OEE yesterday?"* into it — this is near-certain, not hypothetical.

The mitigation is a threshold, not a classifier: if every retrieved chunk falls below a similarity floor, return a fixed string — *"I answer from SOPs and manuals. For line data, click any row below."*

Roughly ten lines. No routing logic, no silent failure. It converts the most likely off-script moment into one that looks deliberate.

The floor is **calibrated, not guessed**. During the Knowledge Base slice, run two fixed query sets against the index — five questions answerable from the SOPs, five factory-data questions that are not — and set the cutoff between the two observed distance bands. Record the chosen value in `config.py` as a named constant so it can be adjusted without hunting for a literal. If the bands overlap, widen the SOP corpus rather than lowering the floor.

## 8. Prompting and structured output

Prompts live in `prompts/` as markdown files, per rule #5.

**Shape is constrained by JSON schema; content is constrained by the prompt.** Every array in every schema carries explicit `minItems` and `maxItems`. This follows directly from the smoke test, where a prose instruction to return two items produced three.

## 9. Revised build order

Reordered from `CLAUDE.md` to reflect D4 and D5. Sequenced so something demoable exists at every checkpoint.

| Time | Milestone |
|---|---|
| 0:00–0:45 | Both scaffolds running, CORS configured. `seed.py` written, run, committed. `schemas.py` complete, mirrored to `types.ts`, `fixtures.json` populated. One endpoint returns a fixture and the frontend renders it. **Contract lands here — both tracks unblock.** |
| 0:45–2:00 | `kpi_engine.py` — real numbers from real DataFrames. `KpiGrid` and `EventTable` render live. **A working demo with zero AI.** |
| 2:00–3:15 | KPI Insights. `llm/` layer, startup pre-warm, insights prompt, `InsightHeader` with loading skeleton. |
| 3:15–5:00 | **Knowledge Base** (moved earlier — protected). Chunk, embed, index, `AskBar` returns cited answers. Threshold guard included. |
| 5:00–6:15 | **Root Cause Analysis** (cuttable). Evidence assembly first, model call second, inline row expansion last. |
| 6:15–7:00 | Polish the single screen top to bottom. It is the only thing judges see. |
| 7:00–8:00 | **Code freeze.** Rehearse end to end at least three times. |

If behind at 5:00, cut Root Cause Analysis. KPI Insights and the Knowledge Base carry the 30-minute claim.

## 10. Work allocation

Role: **architecture + contract, then float.**

Hour 0–1 deliverables, in order, all blocking others: both scaffolds + CORS → `schemas.py` → `types.ts` → `fixtures.json` → `seed.py` run and committed. After the contract lands, float to whichever track is furthest behind.

Concurrent tracks once the contract exists:

| Track | Owner | Work |
|---|---|---|
| A | Backend | `kpi_engine.py`, then root-cause evidence assembly |
| B | Frontend | The five sections, built against `fixtures.json` |
| C | Content | 5–8 hand-written SOP markdown docs. Zero dependencies, and it is what makes retrieval look real rather than toy. |

## 11. Testing

Smoke check only, per `CLAUDE.md`: every endpoint returns 200 with a schema-valid body, and returns computed fields when the LLM is forced to fail. No coverage target.

## 12. Out of scope

Per `CLAUDE.md`, unchanged: authentication, user accounts, Docker, any database server, websockets or streaming, mobile responsive layouts, multi-tenancy, real-time ingestion, email/WhatsApp integration, dashboard builder, meeting summaries. Do not add these.

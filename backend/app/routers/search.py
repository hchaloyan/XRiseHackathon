"""Router: /api/search and /api/explain.

Two steps, deliberately separate (the "medium" design):
  1. /api/search  - retrieval only. No model. Fast enough to feel instant.
  2. /api/explain - model reasoning over chunks the user already saw.

Rule 8 holds: neither endpoint classifies intent. Off-corpus queries are
handled by the similarity floor in knowledge_base.search(), which returns
nothing, and we reply with the fixed redirect string.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException

from app.config import settings
from app.llm.base import get_client
from app.schemas import (
    EXPLAIN_SCHEMA,
    OFF_TOPIC_MESSAGE,
    ExplainRequest,
    ExplainResponse,
    ExplainStep,
    SearchRequest,
    SearchResponse,
    SOPResult,
)
from app.services.knowledge_base import INCLUDE_GET, get_knowledge_base

router = APIRouter(prefix="/api", tags=["search"])

PROMPT_DIR = Path(__file__).resolve().parents[1] / "prompts"


def _render(template_name: str, **values: str) -> str:
    """Load a prompt file and substitute {placeholders}.

    str.replace, not str.format - SOP text contains braces and format() would
    raise KeyError on them.
    """
    text = (PROMPT_DIR / template_name).read_text(encoding="utf-8")
    for key, value in values.items():
        text = text.replace("{" + key + "}", value)
    return text


def _as_context(chunks: list[dict]) -> str:
    return "\n\n".join(
        f"**{c['title']} - {c['section']}** ({c['doc_id']}):\n{c['content']}"
        for c in chunks
    )


@router.post("/search", response_model=SearchResponse)
def search_sops(payload: SearchRequest) -> SearchResponse:
    """Retrieval only. No LLM call, so this stays sub-second."""
    query = payload.query.strip()
    if len(query) < 3:
        raise HTTPException(status_code=400, detail="Query too short")

    chunks = get_knowledge_base().search(query, top_k=settings.retrieval_top_k)

    if not chunks:
        # Either the corpus is empty or nothing cleared max_match_distance.
        return SearchResponse(query=query, results=[], fallback_message=OFF_TOPIC_MESSAGE)

    return SearchResponse(
        query=query,
        results=[
            SOPResult(
                id=c["id"],
                doc_id=c["doc_id"],
                title=c["title"],
                section=c["section"],
                content=c["content"],
                distance=round(c["distance"], 4),
            )
            for c in chunks
        ],
        fallback_message=None,
    )


@router.post("/explain", response_model=ExplainResponse)
def explain_sop(payload: ExplainRequest) -> ExplainResponse:
    """Reason over the exact chunks the user selected.

    Uses the ids from /api/search rather than re-running retrieval, so the
    explanation is grounded in the text on screen. On model failure the
    response still carries its COMPUTED field (sources) with generated fields
    left null - the UI keeps the SOP snippets either way.
    """
    query = payload.query.strip()
    if len(query) < 3:
        raise HTTPException(status_code=400, detail="Query too short")
    if not payload.sop_ids:
        raise HTTPException(status_code=400, detail="sop_ids required")

    kb = get_knowledge_base()
    fetched = kb.collection.get(ids=payload.sop_ids, include=INCLUDE_GET)

    ids = fetched.get("ids") or []
    if not ids:
        raise HTTPException(status_code=404, detail="No such SOP chunks")

    documents = fetched.get("documents") or []
    metadatas = fetched.get("metadatas") or []

    chunks = [
        {
            "doc_id": (metadatas[i] or {}).get("doc_id", ids[i].split("#")[0]),
            "title": (metadatas[i] or {}).get("title", ""),
            "section": (metadatas[i] or {}).get("section", "General"),
            "content": documents[i],
        }
        for i in range(len(ids))
    ]
    sources = sorted({c["doc_id"] for c in chunks})

    prompt = _render("sop_explain.md", query=query, sop_content=_as_context(chunks))
    result = get_client().complete(prompt, EXPLAIN_SCHEMA, timeout=settings.search_timeout)

    if result is None:
        return ExplainResponse(query=query, sources=sources)

    raw_steps = result.get("steps") or []
    steps = [
        ExplainStep(action=str(s.get("action", "")), why=str(s.get("why", "")))
        for s in raw_steps
        if isinstance(s, dict)
    ]

    minutes = result.get("estimated_minutes")
    return ExplainResponse(
        query=query,
        sources=sources,
        explanation=result.get("explanation"),
        steps=steps or None,
        common_mistake=result.get("common_mistake"),
        estimated_minutes=int(minutes) if isinstance(minutes, (int, float)) else None,
    )

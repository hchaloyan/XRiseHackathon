"""Router: /api/search and /api/explain.

Two steps, deliberately separate (the "medium" design):
  1. /api/search  - retrieval only. No model. Fast enough to feel instant.
  2. /api/explain - model reasoning over chunks the user already saw.

No intent classifier: nothing here routes a *question* between document
search and factory data. /api/search has a conversational shell in front of it, but it
only intercepts whole-query pattern matches that are not questions at all
(greetings, thanks, "what can you do"), by regex and never by a model. Real
queries fall through to retrieval, and off-corpus ones are still caught by
the similarity floor in knowledge_base.search().
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.config import settings
from app.llm.base import get_client, render_prompt
from app.schemas import (
    EXPLAIN_SCHEMA,
    GENERAL_DISCLAIMER,
    GENERAL_SCHEMA,
    OFF_TOPIC_MESSAGE,
    ExplainRequest,
    ExplainResponse,
    ExplainStep,
    SearchRequest,
    SearchResponse,
    SopDocument,
    SOPResult,
)
from app.services import conversation, metric_query, summary_query
from app.services.knowledge_base import INCLUDE_GET, get_knowledge_base, read_sop

# No prefix here - main.py applies /api to every router uniformly.
router = APIRouter(tags=["search"])

def _general_answer(query: str) -> str | None:
    """Answer from general knowledge. None on any failure - the caller then
    falls back to the plain redirect, which is always correct."""
    client = get_client(settings.general_provider)
    result = client.complete(
        render_prompt("general_answer.md", query=query),
        GENERAL_SCHEMA,
        timeout=settings.general_timeout,
        max_tokens=300,
    )
    if not result:
        return None
    answer = str(result.get("answer") or "").strip()
    return answer or None


def _as_context(chunks: list[dict]) -> str:
    return "\n\n".join(
        f"**{c['title']} - {c['section']}** ({c['doc_id']}):\n{c['content']}"
        for c in chunks
    )


@router.post("/search", response_model=SearchResponse)
def search_sops(payload: SearchRequest) -> SearchResponse:
    """Conversational shell first, then retrieval. No LLM call on either path,
    so this stays sub-second."""
    query = payload.query.strip()
    if len(query) < 2:
        raise HTTPException(status_code=400, detail="Query too short")

    # Track 1: greetings, thanks, "what can you do". Whole-query pattern
    # matches only, so a real question never lands here. No model, no
    # embedding - this returns in about a millisecond.
    turn = conversation.match(query)
    if turn is not None:
        return SearchResponse(
            query=query,
            kind="conversation",
            reply=turn.reply,
            suggestions=turn.suggestions,
            fallback_message=turn.reply,  # existing UI renders this field
        )

    # Track 2: "what happened?". Before the metric guard on purpose: a
    # question like "summarise downtime today" contains a metric word, and the
    # useful answer is the breakdown, not one number.
    if summary_query.wants_summary(query):
        summary = summary_query.answer(query)
        return SearchResponse(
            query=query,
            kind="summary",
            summary_title=summary.title,
            summary_lines=summary.bullets,
            suggestions=summary.follow_ups,
            metric_day=summary.day,
            metric_is_current=summary.is_current_day,
            fallback_message=summary.title,  # older UI reads this field only
        )

    # Track 3: metric questions, caught by name BEFORE retrieval.
    #
    # This used to be left to the similarity floor, which meant the guarantee
    # rested on "what was OEE yesterday" happening to score 0.477. Re-phrase it
    # and the guarantee evaporates. Catching it by name makes the behaviour a
    # property of the code instead of a property of the embedding, and it lets
    # us answer with the real figure rather than only refusing.
    if metric_query.is_metric_question(query):
        answered = metric_query.answer(query)
        return SearchResponse(
            query=query,
            kind="metric",
            reply=answered["reply"],
            metric_day=answered["day"],
            metric_is_current=answered["is_current_day"],
            fallback_message=answered["reply"],  # older UI reads this field only
        )

    # Track 4: retrieval, with the previous query available as context.
    #
    # Both orderings below end up trying the fragment alone AND joined to the
    # previous query; only the order differs. That keeps follow-up handling a
    # preference rather than a decision - a misread fragment still gets its
    # plain retrieval, so the worst case is the ranking we would have had
    # anyway.
    kb = get_knowledge_base()
    previous = (payload.previous_query or "").strip()
    joined = f"{previous} {query}".strip() if previous else ""

    attempts: list[tuple[str, str | None]] = [(query, None)]
    if joined:
        if conversation.is_followup(query):
            attempts.insert(0, (joined, joined))  # fragment: context first
        else:
            attempts.append((joined, joined))  # complete question: context last

    chunks: list[dict] = []
    resolved_from: str | None = None
    for text, source in attempts:
        chunks = kb.search(text, top_k=settings.retrieval_top_k)
        if chunks:
            resolved_from = source
            break

    if not chunks:
        # Nothing cleared the floor. Two very different situations hide here,
        # and conflating them is the failure this branch exists to prevent.
        #
        # A question naming a factory metric ("what was OEE yesterday") must
        # keep the redirect: the answer lives in the event table, and a model
        # asked for it would invent a number.
        #
        # Anything else ("what does OEE mean", "why does MIG welding go
        # porous") is general knowledge with no plant data in it. Answering
        # that is useful and safe, provided it is labelled as not coming from
        # the SOPs.
        if settings.general_provider != "off":
            answer = _general_answer(query)
            if answer:
                return SearchResponse(
                    query=query,
                    kind="general",
                    reply=answer,
                    disclaimer=GENERAL_DISCLAIMER,
                    suggestions=conversation.EXAMPLE_QUESTIONS,
                    fallback_message=answer,  # older UI reads this field only
                )

        return SearchResponse(
            query=query,
            kind="off_topic",
            suggestions=conversation.EXAMPLE_QUESTIONS,
            fallback_message=OFF_TOPIC_MESSAGE,
        )

    return SearchResponse(
        query=query,
        kind="results",
        resolved_from=resolved_from,
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


@router.get("/sops/{doc_id}", response_model=SopDocument)
def get_sop(doc_id: str) -> SopDocument:
    """The full document behind a result, for the in-app viewer."""
    doc = read_sop(doc_id)
    if doc is None:
        raise HTTPException(status_code=404, detail=f"No SOP {doc_id}")
    return SopDocument(**doc)


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

    prompt = render_prompt("sop_explain.md", query=query, sop_content=_as_context(chunks))
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

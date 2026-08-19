"""Smoke check for the ask bar retrieval slice. Run: python test_knowledge_base.py

Guards the three things that made the ask bar look broken: one SOP sweeping the
whole result list, a section indexed as two chunks under one heading, and a
cutoff that cannot tell a procedure question from a factory-data question.

Needs Ollama up. Chunking asserts do not.
"""

from pathlib import Path

from app.config import settings
from app.services.knowledge_base import KnowledgeBase, get_knowledge_base
from calibrate_kb import BY_REFERENCE, IN_CORPUS, OUT_OF_CORPUS

# Answering these from an SOP is the failure that ends the demo: a data question
# met with a confident-looking procedure. Unlike the softer overlap cases, these
# have no plausible reading as a document question.
MUST_REDIRECT = [
    "what was OEE yesterday",
    "which machine had the most downtime this week",
    "what is the scrap rate for M-22",
    "show me downtime by shift",
]


def _all_chunks() -> list[dict]:
    out = []
    for path in sorted(Path(settings.sop_dir).glob("*.md")):
        meta, body = KnowledgeBase._parse_front_matter(path.read_text(encoding="utf-8"))
        doc_id = meta.get("doc_id") or path.stem
        out += [dict(c, doc_id=doc_id) for c in KnowledgeBase._chunk_document(body, doc_id)]
    return out


def test_chunks_are_whole_sections():
    """No section split across two chunks: the pair rendered as duplicate rows
    with the same heading, and the tail was often a fragment (one was 14 chars).
    """
    chunks = _all_chunks()
    assert chunks, "no SOPs found"
    for doc_id in {c["doc_id"] for c in chunks}:
        sections = [c["section"] for c in chunks if c["doc_id"] == doc_id]
        assert len(sections) == len(set(sections)), f"{doc_id} repeats a section: {sections}"
    shortest = min(chunks, key=lambda c: len(c["text"]))
    assert len(shortest["text"]) > 100, f"fragment indexed: {shortest}"


def test_one_result_per_document():
    kb = get_knowledge_base()
    for query in IN_CORPUS:
        results = kb.search(query)
        assert results, f"no match for an in-corpus question: {query}"
        doc_ids = [r["doc_id"] for r in results]
        assert len(doc_ids) == len(set(doc_ids)), f"{query} -> repeated docs {doc_ids}"


def test_realistic_questions_are_answered():
    """The cutoff must survive terse and vague phrasing, not just questions
    written in the SOPs' own register. A five-query calibration set once put
    this at 0.26, which rejected "how do I clear a jam"."""
    kb = get_knowledge_base()
    missed = [q for q in IN_CORPUS if not kb.search(q)]
    assert not missed, f"real questions rejected by max_match_distance: {missed}"


def test_named_documents_resolve_exactly():
    """"summarize SOP 001" is a reference, not a content question, and scores
    like off-topic text. It is answered by id lookup instead."""
    kb = get_knowledge_base()
    for query in BY_REFERENCE:
        results = kb.search(query)
        assert results, f"named document not found: {query}"
        assert len({r["doc_id"] for r in results}) == 1, query
        assert all(r["distance"] == 0.0 for r in results), "exact match, not similarity"


def test_factory_data_is_redirected():
    """Data questions belong to the event table. The similarity floor is
    the only thing standing between a judge's OEE question and a confident-
    looking maintenance procedure.

    The bands overlap, so this tolerates a bounded number of soft admissions
    but never one of MUST_REDIRECT.
    """
    kb = get_knowledge_base()
    for query in MUST_REDIRECT:
        assert kb.search(query) == [], f"factory-data question answered from SOPs: {query}"
    admitted = [q for q in OUT_OF_CORPUS if kb.search(q)]
    assert len(admitted) <= 1, f"floor too loose, admitted {admitted}"


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
            print(f"ok  {name}")

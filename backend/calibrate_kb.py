"""Calibrate MAX_MATCH_DISTANCE for the ask bar (spec 7.1).

Run from backend/:

    python calibrate_kb.py            # query the existing index
    python calibrate_kb.py --reindex  # rebuild the index first

Prints the best cosine distance for two fixed query sets - questions the SOPs
answer, and factory-data questions they do not - then recommends a cutoff
between the two bands. Set the result as MAX_MATCH_DISTANCE in backend/.env.

If the bands overlap, widen the SOP corpus. Do not lower the floor to force a
separation; that is how a judge's data question gets answered with a
confident-looking maintenance procedure.
"""

from __future__ import annotations

import sys

from app.config import settings
from app.services.knowledge_base import KnowledgeBase, embed_texts

# Answerable from the SOP corpus. Deliberately phrased the way a supervisor
# would ask, not using the exact headings from the documents.
IN_CORPUS = [
    "how do I purge the barrel for a colour change",
    "what causes porosity in the robot welds",
    "the part lifted off the plate on the 3D printer, what do I check",
    "what is on the weekly PM for the CNC machines",
    "a tool broke mid-cycle, what do I do with the parts already made",
]

# Factory-data questions. Rule 8 says these belong to the event table, not the
# ask bar. Every one of these must fall ABOVE the cutoff so the ask bar returns
# the redirect instead of an irrelevant SOP.
OUT_OF_CORPUS = [
    "what was OEE yesterday",
    "which machine had the most downtime this week",
    "how many parts did we scrap on the molding line today",
    "what is the scrap rate for M-22",
    "show me downtime by shift",
]


def best_distances(kb: KnowledgeBase, queries: list[str]) -> list[tuple[str, float, str]]:
    rows = []
    for q in queries:
        raw = kb.collection.query(
            query_embeddings=[embed_texts([q])[0]],
            n_results=1,
            include=["metadatas", "distances"],  # type: ignore[arg-type]
        )
        distances = (raw.get("distances") or [[]])[0]
        metadatas = (raw.get("metadatas") or [[]])[0]
        if not distances:
            rows.append((q, 999.0, "-"))
            continue
        meta = metadatas[0] or {}
        label = f"{meta.get('doc_id', '?')} / {meta.get('section', '?')}"
        rows.append((q, float(distances[0]), label))
    return rows


def main() -> int:
    kb = KnowledgeBase()

    if "--reindex" in sys.argv:
        print("Rebuilding index...\n")
        kb.index_sops(force=True)

    if kb.collection.count() == 0:
        print("Index is empty. Add SOPs to data/sops/ and rerun with --reindex.")
        return 1

    print(f"\n{kb.collection.count()} chunks indexed. Embedding model: {settings.embed_model}\n")

    in_rows = best_distances(kb, IN_CORPUS)
    out_rows = best_distances(kb, OUT_OF_CORPUS)

    print("ANSWERABLE FROM SOPs  (want LOW distance)")
    print("-" * 78)
    for q, d, label in in_rows:
        print(f"  {d:6.3f}  {label:28} {q}")

    print("\nFACTORY DATA, NOT IN SOPs  (want HIGH distance)")
    print("-" * 78)
    for q, d, label in out_rows:
        print(f"  {d:6.3f}  {label:28} {q}")

    worst_in = max(d for _, d, _ in in_rows)
    best_out = min(d for _, d, _ in out_rows)

    print("\n" + "=" * 78)
    print(f"  worst in-corpus distance : {worst_in:.3f}   (must stay BELOW the cutoff)")
    print(f"  best  out-of-corpus      : {best_out:.3f}   (must stay ABOVE the cutoff)")
    print(f"  current MAX_MATCH_DISTANCE: {settings.max_match_distance}")
    print("=" * 78)

    if best_out <= worst_in:
        print(
            "\nBANDS OVERLAP. A data question scores as well as a real one.\n"
            "Do not split the difference - widen the SOP corpus so the on-topic\n"
            "questions retrieve more strongly, then rerun."
        )
        return 1

    recommended = round((worst_in + best_out) / 2, 2)
    print(f"\nRecommended:  MAX_MATCH_DISTANCE={recommended}")
    print(f"Margin: {best_out - worst_in:.3f}. Below ~0.05 is fragile - judges will")
    print("phrase things differently than these ten queries.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

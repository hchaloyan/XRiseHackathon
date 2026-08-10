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
from app.services.knowledge_base import KnowledgeBase, _doc_reference, embed_query

# Answerable from the SOP corpus. Deliberately phrased the way a supervisor
# would ask, not using the exact headings from the documents.
#
# Keep this list WIDE and keep it awkward. An earlier five-query version was
# written in the same register as the SOP prose, reported a comfortable 0.045
# margin, and produced a cutoff that rejected "how do I clear a jam". Terse
# queries ("material starvation") and vague ones ("tell me about preventive
# maintenance") are what actually get typed, and they score worst.
IN_CORPUS = [
    "how do I purge the barrel for a colour change",
    "what causes porosity in the robot welds",
    "the part lifted off the plate on the 3D printer, what do I check",
    "what is on the weekly PM for the CNC machines",
    "a tool broke mid-cycle, what do I do with the parts already made",
    "how do I clear a jam",
    "what PPE do I need to clear a jam",
    "what do I do if a sensor is faulty",
    "material starvation",
    "tell me about preventive maintenance",
    "how do I do a mold changeover",
    "what's in the changeover SOP",
    "robot won't restart after a fault",
    "parts are coming out with sink marks",
    "when do I escalate a quality problem",
    "how do I set work offsets on the CNC",
    "how do I recover an SLS recoater strike",
]

# Queries that name a document outright. Answered by exact id lookup in
# knowledge_base.search(), so they never reach the distance floor and must NOT
# be calibrated against - they score like off-topic text and would drag the
# cutoff up into the factory-data band.
BY_REFERENCE = ["summarize SOP 001", "what does SOP-001 cover", "SOP-003"]

# Factory-data questions. Rule 8 says these belong to the event table, not the
# ask bar. Every one of these must fall ABOVE the cutoff so the ask bar returns
# the redirect instead of an irrelevant SOP.
OUT_OF_CORPUS = [
    "what was OEE yesterday",
    "which machine had the most downtime this week",
    "how many parts did we scrap on the molding line today",
    "what is the scrap rate for M-22",
    "show me downtime by shift",
    "what is our availability trend",
    "how many good parts did M-11 make",
    "which line is underperforming",
    "what is the inventory level for TL-2003",
    "compare this week to last week",
]


def best_distances(kb: KnowledgeBase, queries: list[str]) -> list[tuple[str, float, str]]:
    rows = []
    for q in queries:
        raw = kb.collection.query(
            query_embeddings=[embed_query(q)],
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
    print(f"  worst in-corpus distance : {worst_in:.3f}   (want BELOW the cutoff)")
    print(f"  best  out-of-corpus      : {best_out:.3f}   (want ABOVE the cutoff)")
    print(f"  current MAX_MATCH_DISTANCE: {settings.max_match_distance}")
    print("=" * 78)

    # The bands overlap on realistic phrasing, so there is no midpoint to take.
    # Sweep instead and read the trade directly.
    print("\n  cutoff   answered      admitted (rule 8 violations)")
    print("  " + "-" * 74)
    sweep = []
    for cut in [round(0.20 + 0.01 * i, 2) for i in range(26)]:
        answered = sum(1 for _, d, _ in in_rows if d <= cut)
        # At most one admitted data question. More than one and the redirect
        # has stopped working, which is the failure that costs the demo.
        viable = len([q for q, d, _ in out_rows if d <= cut]) <= 1
        sweep.append((cut, answered, viable))

    # Take the MIDDLE of the widest viable plateau, not its first cutoff. The
    # edge of a plateau sits a thousandth away from a real query it rejects;
    # that is how the previous value ended up rejecting "how do I clear a jam".
    best = max((a for _, a, v in sweep if v), default=0)
    plateau = [cut for cut, a, v in sweep if v and a == best]
    best_cut = plateau[len(plateau) // 2] if plateau else None

    for cut, answered, _ in sweep:
        admitted = [q for q, d, _ in out_rows if d <= cut]
        note = ", ".join(q[:34] for q in admitted[:2]) or "none"
        mark = "  <-" if cut == best_cut else ""
        print(f"  {cut:.2f}    {answered:2d}/{len(in_rows)}        {note}{mark}")

    if best_out <= worst_in:
        print(
            "\nBANDS OVERLAP: some data questions score better than some real ones.\n"
            "No cutoff separates them cleanly. Pick from the sweep above, and widen\n"
            "the SOP corpus if the answered count is too low to demo."
        )

    if best_cut:
        print(f"\nRecommended:  MAX_MATCH_DISTANCE={best_cut}  ({best}/{len(in_rows)} answered)")
        print(f"Headroom: {best_cut - worst_in:+.3f} over the worst real question, ")
        print(f"          {min((d for _, d, _ in out_rows if d > best_cut), default=1.0) - best_cut:+.3f} under the next data question.")
    print("\nDocument-reference queries bypass this floor entirely:")
    for q in BY_REFERENCE:
        print(f"  {q!r:34} -> {_doc_reference(q)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

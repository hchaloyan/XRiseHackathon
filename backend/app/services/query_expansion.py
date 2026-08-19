"""Expand a query into retrieval vocabulary before it is embedded.

The corpus and the people typing at it do not share a vocabulary:

  - The SOPs are internally inconsistent. "mold" appears in six documents and
    "mould" in four; "molding" and "moulding" split four/four. Whichever
    spelling a supervisor types, they are half-matching their own manuals.
  - Operators use abbreviations the documents spell out. "IMM", "PPE" and
    "OOT" appear in zero SOPs, yet "imm" is a keyword on four machines in
    machines.json.
  - People ask about assets by id. "M-13" appears in exactly one document and
    "M-22" in one, so "what's wrong with M-22" has almost nothing to match on
    even though SOP-003 and SOP-004 are entirely about that machine's type.

This module closes those gaps by rewriting the query only. Documents are
indexed as written, so the viewer still shows the real text, and nothing here
can change what a citation says.

Two properties keep it safe:

  - It is a dictionary, not a model. Every expansion is inspectable and the
    same input always produces the same output.
  - It ADDS terms and never removes them. The original wording stays in the
    string, so a query that already worked continues to score at least as
    well.
"""

from __future__ import annotations

import re

from app.services.data_loader import load

# Spelling variants. Both forms go into the query because both forms are in
# the corpus - replacing one with the other would just move the miss.
_VARIANTS: dict[str, str] = {
    "mould": "mold",
    "mold": "mould",
    "moulding": "molding",
    "molding": "moulding",
    "moulded": "molded",
    "molded": "moulded",
    "colour": "color",
    "color": "colour",
    "utilisation": "utilization",
    "utilization": "utilisation",
    "aluminium": "aluminum",
    "aluminum": "aluminium",
    "fibre": "fiber",
    "fiber": "fibre",
}

# Abbreviations operators type, spelled out the way the SOPs write them.
_ABBREVIATIONS: dict[str, str] = {
    "imm": "injection molding machine press",
    "pm": "preventive maintenance",
    "ppe": "personal protective equipment safety lockout",
    "oot": "out of tolerance dimensional",
    "qc": "quality control inspection",
    "sls": "SLS powder bed 3D printer additive",
    "fdm": "FDM filament 3D printer additive",
    "cnc": "CNC machining",
    "cmm": "coordinate measuring machine first article inspection",
    "wip": "work in progress material",
    "oem": "manufacturer specification",
    "sop": "standard operating procedure",
    "rpm": "spindle speed",
    "psi": "pressure",
    "3d": "3D printer additive manufacturing",
    "changeover": "changeover setup first-off",
    "jam": "jam blockage stuck part",
}

_MACHINE_ID = re.compile(r"\bm-?\s?(\d{2})\b", re.IGNORECASE)

# Words that name a factory metric rather than a procedure. A query containing
# one is not expanded at all.
#
# This guard is not optional. Without it "what is the scrap rate for M-22"
# picks up the whole CNC vocabulary from the machine table and starts scoring
# like a real procedure question, which walks it straight under the similarity
# floor - the exact failure the floor exists to prevent. Expansion must
# never be able to talk a data question into the corpus.
METRIC_TERMS = frozenset({
    "oee", "scrap", "downtime", "availability", "performance", "utilisation",
    "utilization", "throughput", "yield", "inventory", "uptime",
})


def _machine_expansions() -> dict[str, str]:
    """machine_id -> the words the SOPs actually use about that asset.

    Built from machines.json rather than hand-written, so adding a machine to
    the seed data cannot leave this table stale.
    """
    machines = load()["machines"]
    table: dict[str, str] = {}
    for row in machines.itertuples():
        # Name, type and line only. The `keywords` column pulls hardest of all
        # ("tonnage", "plastics", "metal cutting") and is the reason a data
        # question about a machine started scoring like a procedure. The terms
        # worth having from it - "imm", "molder" - are in _ABBREVIATIONS,
        # where they are reached by typing them rather than by naming a
        # machine that happens to have them.
        table[row.machine_id.upper()] = f"{row.name} {row.machine_type} {row.line} line"
    return table


_machines: dict[str, str] | None = None


def machine_expansions() -> dict[str, str]:
    global _machines
    if _machines is None:
        _machines = _machine_expansions()
    return _machines


def names_a_metric(query: str) -> bool:
    """True when the query asks about a factory figure rather than a procedure.

    The single guard that keeps the separation intact across three features:
    expansion refuses to enrich these, the lexical fallback refuses to match
    them, and the general-knowledge answerer refuses to answer them. A model
    guessing at this plant's OEE is the worst thing this app could do.
    """
    return any(t in METRIC_TERMS for t in re.findall(r"[a-z0-9-]+", query.lower()))


def expand(query: str) -> str:
    """Return the query plus any retrieval vocabulary it implies.

    The original text always leads, so the expansion can only add signal. The
    caller embeds the result; the raw query is what gets echoed back to the
    user and what /api/explain later receives.
    """
    tokens = re.findall(r"[a-z0-9-]+", query.lower())
    if any(token in METRIC_TERMS for token in tokens):
        return query

    extra: list[str] = []
    seen: set[str] = set()

    def add(text: str) -> None:
        for word in text.split():
            key = word.lower()
            if key not in seen and key not in query.lower():
                seen.add(key)
                extra.append(word)

    for token in tokens:
        if token in _VARIANTS:
            add(_VARIANTS[token])
        if token in _ABBREVIATIONS:
            add(_ABBREVIATIONS[token])

    # Machine ids: "M-22", "m22" and "M 22" all reach the same asset.
    for match in _MACHINE_ID.finditer(query):
        machine_id = f"M-{match.group(1)}"
        expansion = machine_expansions().get(machine_id)
        if expansion:
            add(expansion)

    if not extra:
        return query
    return f"{query} {' '.join(extra)}"

"""Conversational shell in front of the knowledge base.

CLAUDE.md rule 8 rules out an intent classifier routing free text between
document search and factory data, and that still holds: nothing here decides
where a *question* goes. This handles only the turns that are not questions -
greetings, thanks, "what can you do" - which are matched by fixed patterns,
not by a model.

Two properties make this safe to add this late:

  - It is deterministic. A regex either matches or it does not; there is no
    confidence score to be wrong about on stage.
  - It runs before retrieval only for whole-query matches. "hello" is a
    greeting; "hello world label on the HMI" is not, and falls straight
    through to search.

Cost is a string comparison, so the conversational path answers in about a
millisecond with no model and no embedding call.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# Shown as clickable chips whenever we have nothing better to offer. Drawn
# from the SOP corpus so every one of them is guaranteed to retrieve.
EXAMPLE_QUESTIONS = [
    "How do I purge the barrel for a colour change?",
    "What causes porosity in the robot welds?",
    "What is on the weekly PM for the CNC machines?",
    "The part lifted off the 3D printer plate - what do I check?",
]

# What the ask bar can and cannot do, in the supervisor's terms. Reused by
# the greeting and the capability answer so they never drift apart.
_CAPABILITY = (
    "I answer from the plant's SOPs, manuals and audit documents - "
    "procedures, troubleshooting steps and maintenance schedules. "
    "For line data like OEE, scrap or downtime, click any row in the table below."
)


@dataclass(frozen=True)
class ConversationTurn:
    intent: str
    reply: str
    suggestions: list[str]


# Anchored to the whole query. Trailing punctuation is stripped before
# matching, so "hello!" and "hello" behave the same.
_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    (
        "greeting",
        re.compile(
            # Keep every alternative inside the one outer group, and close it
            # before the optional trailing address form.
            r"^(hi|hello|hey|yo|howdy|hiya|greetings"
            r"|good\s+(morning|afternoon|evening))"
            r"(\s+(there|mate|team|all))?$"
        ),
    ),
    (
        "thanks",
        re.compile(r"^(thanks|thank\s+you|thx|ta|cheers|nice|perfect|great|got\s+it)"
                   r"(\s+(a\s+lot|so\s+much|very\s+much))?$"),
    ),
    (
        "farewell",
        re.compile(r"^(bye|goodbye|see\s+you|later|good\s?night|cya)$"),
    ),
    (
        "capability",
        re.compile(
            r"^(help"
            r"|what\s+(can|do)\s+you\s+(do|help\s+with|know)"
            r"|who\s+are\s+you"
            r"|what\s+are\s+you"
            r"|how\s+do\s+(you|i)\s+use\s+(this|you)"
            r"|what\s+(is|are)\s+(this|you\s+for)"
            r"|how\s+does\s+this\s+work)"
            r"\??$"
        ),
    ),
    (
        "identity",
        re.compile(r"^(are\s+you\s+(a\s+)?(bot|ai|human|real)|is\s+this\s+(a\s+)?(bot|ai))\??$"),
    ),
]

_REPLIES = {
    "greeting": f"Morning. {_CAPABILITY}",
    "thanks": "Any time. Ask me anything else from the SOPs.",
    "farewell": "Good shift.",
    "capability": _CAPABILITY,
    "identity": (
        "I am an assistant running on the plant's own documents. "
        f"{_CAPABILITY}"
    ),
}

# Suggestions are worth showing when the user is oriented and looking for a
# starting point, and noise when they are signing off.
_WITH_SUGGESTIONS = {"greeting", "capability", "identity"}

# Guardrail: a greeting is short. Anything longer is a real query that merely
# starts with a greeting word, and belongs to retrieval.
_MAX_WORDS = 6


def _normalise(query: str) -> str:
    text = query.strip().lower()
    text = re.sub(r"[!.,;:]+$", "", text)  # keep '?' - capability patterns use it
    return re.sub(r"\s+", " ", text)


def match(query: str) -> ConversationTurn | None:
    """Return a conversational turn, or None to fall through to retrieval."""
    text = _normalise(query)
    if not text or len(text.split()) > _MAX_WORDS:
        return None

    for intent, pattern in _PATTERNS:
        if pattern.match(text):
            return ConversationTurn(
                intent=intent,
                reply=_REPLIES[intent],
                suggestions=EXAMPLE_QUESTIONS if intent in _WITH_SUGGESTIONS else [],
            )
    return None

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
from datetime import datetime

# Shown as clickable chips whenever we have nothing better to offer. Drawn
# from the SOP corpus so every one of them is guaranteed to retrieve.
EXAMPLE_QUESTIONS = [
    "Summarise the shift",
    "What stopped the line today?",
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
    "I can also summarise the shift: ask what happened, what stopped the line, "
    "how a machine is doing or what needs reordering, and you get the numbers "
    "here rather than a pointer to the table."
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
        re.compile(
            r"^(thanks|thank\s+you|thx|ta|cheers|nice|perfect|great|got\s+it"
            r"|brilliant|lovely|magic|that\s+helps|that\s+helped|useful|"
            r"makes\s+sense|understood|noted)"
            r"(\s+(a\s+lot|so\s+much|very\s+much|mate|team))?$"
        ),
    ),
    (
        "farewell",
        re.compile(
            r"^(bye|goodbye|see\s+you|later|good\s?night|cya|"
            r"that\s+is\s+all|thats\s+all|that's\s+all|im\s+done|i'm\s+done|done)$"
        ),
    ),
    (
        # The user is telling us the answer missed. A dead end here reads as a
        # broken assistant; offering the corpus's own questions is the honest
        # recovery, and it costs nothing to be gracious about it.
        "miss",
        re.compile(
            r"^(no|nope|not\s+(that|this|it|what\s+i\s+meant|helpful|right|useful)"
            r"|wrong|thats\s+wrong|that's\s+wrong|thats\s+not\s+(it|right)"
            r"|that's\s+not\s+(it|right)|try\s+again|useless|unhelpful"
            r"|i\s+meant\s+something\s+else|not\s+quite)\??$"
        ),
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

def time_of_day(now: datetime | None = None) -> str:
    """Morning / afternoon / evening, by the server's local clock.

    Boundaries follow the shift pattern in the data rather than the clock
    face: shift A starts 06:00 and shift B at 14:00 (see data_loader._shift),
    so 14:00 is when this plant stops saying "morning".
    """
    hour = (now or datetime.now()).hour
    if hour < 12:
        return "morning"
    if hour < 18:
        return "afternoon"
    return "evening"


def _greeting_reply(now: datetime | None = None) -> str:
    return f"Good {time_of_day(now)}. {_CAPABILITY}"


def _farewell_reply(now: datetime | None = None) -> str:
    # "Good shift" reads oddly on the way out of an evening shift.
    return "Good shift." if time_of_day(now) == "morning" else "See you next shift."


_STATIC_REPLIES = {
    "thanks": "Any time. Ask me anything else from the SOPs.",
    "capability": _CAPABILITY,
    "identity": (
        "I am an assistant running on the plant's own documents. "
        f"{_CAPABILITY}"
    ),
    "miss": (
        "Sorry - let me try again. Naming the machine, the reason code or the "
        "defect usually lands it, for example \"M-31 weld porosity\" or "
        "\"changeover on the 350T\". Or start from one of these:"
    ),
}


def _reply_for(intent: str, now: datetime | None = None) -> str:
    if intent == "greeting":
        return _greeting_reply(now)
    if intent == "farewell":
        return _farewell_reply(now)
    return _STATIC_REPLIES[intent]

# Suggestions are worth showing when the user is oriented and looking for a
# starting point, and noise when they are signing off.
_WITH_SUGGESTIONS = {"greeting", "capability", "identity", "miss"}

# Guardrail: a greeting is short. Anything longer is a real query that merely
# starts with a greeting word, and belongs to retrieval.
_MAX_WORDS = 6


def _normalise(query: str) -> str:
    text = query.strip().lower()
    text = re.sub(r"[!.,;:]+$", "", text)  # keep '?' - capability patterns use it
    return re.sub(r"\s+", " ", text)


# Openings that only make sense against something already on screen. A query
# starting with one of these is asking about the previous topic, so retrieval
# should see both strings joined rather than the fragment alone.
_FOLLOWUP = re.compile(
    r"^(and|also|what\s+about|how\s+about|what\s+if|ok\s+but|but\s+what|"
    r"then\s+what|what\s+else|anything\s+else|same\s+for|same\s+on|"
    r"and\s+for|for\s+the|on\s+the|why|why\s+not|how\s+come|"
    r"the\s+next\s+step|next\s+step|after\s+that|before\s+that|"
    r"does\s+that|do\s+they|is\s+it|are\s+they|what\s+about\s+the)\b"
)

# A follow-up is a fragment. Anything longer is a complete question that
# happens to start with "why", and stands on its own.
_FOLLOWUP_MAX_WORDS = 8


def is_followup(query: str) -> bool:
    """True when the query only makes sense against the previous one.

    Deliberately narrow. Getting this wrong in the permissive direction drags
    the previous topic into an unrelated question, which reads far worse than
    simply answering the fragment badly - and the caller treats it as a
    preference for ordering, not a decision, so a false positive still falls
    back to plain retrieval.
    """
    text = _normalise(query)
    if not text or len(text.split()) > _FOLLOWUP_MAX_WORDS:
        return False
    return bool(_FOLLOWUP.match(text))


def match(query: str, now: datetime | None = None) -> ConversationTurn | None:
    """Return a conversational turn, or None to fall through to retrieval.

    `now` is injectable so the time-of-day greeting can be tested without
    waiting for the afternoon.
    """
    text = _normalise(query)
    if not text or len(text.split()) > _MAX_WORDS:
        return None

    for intent, pattern in _PATTERNS:
        if pattern.match(text):
            return ConversationTurn(
                intent=intent,
                reply=_reply_for(intent, now),
                suggestions=EXAMPLE_QUESTIONS if intent in _WITH_SUGGESTIONS else [],
            )
    return None

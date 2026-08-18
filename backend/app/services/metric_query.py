"""Answer metric questions with computed figures and a pointer to the day.

Why this exists as a guard rather than a similarity outcome:

The floor in knowledge_base.search() was doing this job, and it did it by
accident of geometry. "what was OEE yesterday" scored 0.477 and fell out; a
differently phrased metric question could score 0.33 and stay in, and then the
ask bar answers a question about this plant's output with a maintenance
procedure. That is the rule 8 failure the floor exists to prevent, and leaving
it to a distance was always a bet on phrasing.

So metric questions are now caught by name, before retrieval, against a closed
vocabulary. That is not the free-text intent classifier rule 8 rules out - it
is a keyword guard over eleven words, and the same METRIC_TERMS set already
used by query expansion and the lexical fallback.

Having caught them, we can do better than a redirect. Every figure here comes
from kpi_engine, which is pandas (rule 1). The model is not involved, so the
number is either right or the arithmetic is broken - it can never be invented.
"""

from __future__ import annotations

import re
from datetime import date, timedelta

from app.services import kpi_engine
from app.services.query_expansion import METRIC_TERMS

# Which figure the question is about. Order matters: the first match wins, so
# the more specific terms are listed before the general ones.
_METRIC_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("scrap_rate", re.compile(r"\b(scrap|reject|defect\s+rate|quality\s+rate)\b")),
    ("downtime_minutes", re.compile(r"\b(downtime|stopped|stoppage|uptime)\b")),
    ("availability", re.compile(r"\bavailabilit(y|ies)\b")),
    ("performance", re.compile(r"\bperformance\b")),
    ("inventory", re.compile(r"\b(inventory|stock|material\s+cover|reorder)\b")),
    ("oee", re.compile(r"\boee\b|\boverall\s+equipment\b")),
]

_TODAY = re.compile(r"\b(today|now|currently|current|right\s+now|this\s+shift)\b")
_YESTERDAY = re.compile(r"\b(yesterday|last\s+night|previous\s+day)\b")
_THIS_WEEK = re.compile(r"\b(this\s+week|past\s+week|last\s+week|last\s+7\s+days|trend)\b")
_ISO_DATE = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")
_DAY_MONTH = re.compile(
    r"\b(\d{1,2})(?:st|nd|rd|th)?\s+(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)",
    re.IGNORECASE,
)
_MONTHS = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]


def is_metric_question(query: str) -> bool:
    """True when the query asks for a figure this plant's data holds."""
    tokens = re.findall(r"[a-z0-9-]+", query.lower())
    if any(t in METRIC_TERMS for t in tokens):
        return True
    return any(pattern.search(query.lower()) for _, pattern in _METRIC_PATTERNS)


def _requested_day(query: str, available: list[date]) -> tuple[date, str, date | None]:
    """Resolve the day asked about, and the day we can actually answer for.

    Returns (answerable_day, phrasing, requested_day). `requested_day` is the
    calendar date the words meant; when it is not in the dataset the caller
    says so rather than answering about a different day under its name.

    "Today" and "yesterday" resolve against the REAL calendar, not against the
    end of the dataset. The data is a committed snapshot that does not advance
    on its own, so on any day after it was generated the honest answer to
    "what is today's OEE" is "nothing recorded yet, here is the most recent
    shift" - not yesterday's figure wearing today's label.
    """
    latest = available[-1]
    text = query.lower()
    real_today = date.today()

    # A date that parses as digits but is not a real calendar date - "31 feb",
    # "2026-02-30" - must not take the endpoint down. The regexes match the
    # shape; only date() knows whether the day exists in that month.
    match = _ISO_DATE.search(text)
    if match:
        try:
            wanted = date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
        except ValueError:
            return latest, "latest", None
        return _clamp(wanted, available), "asked", wanted

    match = _DAY_MONTH.search(text)
    if match:
        month = _MONTHS.index(match.group(2).lower()[:3]) + 1
        year = real_today.year if month <= real_today.month else real_today.year - 1
        try:
            wanted = date(year, month, int(match.group(1)))
        except ValueError:
            return latest, "latest", None
        return _clamp(wanted, available), "asked", wanted

    if _YESTERDAY.search(text):
        wanted = real_today - timedelta(days=1)
        return _clamp(wanted, available), "yesterday", wanted
    if _THIS_WEEK.search(text):
        return latest, "week", None
    if _TODAY.search(text):
        return _clamp(real_today, available), "today", real_today
    return latest, "latest", None


def _clamp(wanted: date, available: list[date]) -> date:
    if wanted in available:
        return wanted
    # Nearest day we actually hold, so a question about a gap still lands
    # somewhere real rather than returning zeros.
    return min(available, key=lambda d: abs((d - wanted).days))


def _day_month(day: date) -> str:
    """'5 Aug' - built by hand rather than with strftime.

    "%-d" is a glibc extension for a day without its leading zero. Linux and
    macOS accept it; Windows raises ValueError and takes the endpoint down with
    it. There is no portable strftime code for this, so the number is formatted
    directly and only the month name comes from strftime.
    """
    return f"{day.day} {day:%b}"


def _which_metric(query: str) -> str:
    text = query.lower()
    for name, pattern in _METRIC_PATTERNS:
        if pattern.search(text):
            return name
    return "oee"


def answer(query: str) -> dict:
    """Computed figures for the day the question is about.

    Returns the day to switch the dashboard to, a plain sentence, and the
    figures behind it. Nothing here is generated.
    """
    days = sorted({point["day"] for point in kpi_engine.trend()})
    day, phrasing, requested = _requested_day(query, days)
    metric = _which_metric(query)

    facts = kpi_engine.plant(day)
    inventory = kpi_engine.inventory(day)
    latest = days[-1]

    # The words asked for a day the plant has no record of. Say that first,
    # then answer for the most recent shift there IS a record of. Answering
    # silently about a different day is how a supervisor takes yesterday's
    # scrap figure into a meeting about today.
    stale = requested is not None and requested not in days
    preamble = ""
    if stale and requested is not None:
        gap = (requested - day).days
        ago = f", {gap} day{'s' if gap != 1 else ''} earlier" if gap > 0 else ""
        preamble = (
            f"No production recorded for {requested:%a %d %b} yet. "
            f"The most recent shift on file is {day:%a %d %b}{ago}. "
        )

    when = {
        "today": "Then",
        "yesterday": "Then",
        "week": "Across the window",
        "asked": "Then",
        "latest": "Most recent shift",
    }.get(phrasing, str(day)) if stale else {
        "today": "Today",
        "yesterday": "Yesterday",
        "week": "Across the window",
        "asked": _day_month(day),
        "latest": "Most recent shift",
    }.get(phrasing, str(day))

    if metric == "scrap_rate":
        headline = f"{when}, scrap was {facts['scrap_rate'] * 100:.1f}%."
    elif metric == "downtime_minutes":
        headline = f"{when}, the plant lost {facts['downtime_minutes']:.0f} minutes to downtime."
    elif metric == "availability":
        headline = f"{when}, availability was {facts['availability'] * 100:.1f}%."
    elif metric == "performance":
        headline = f"{when}, performance ran at {facts['performance'] * 100:.1f}%."
    elif metric == "inventory":
        headline = (
            f"{inventory['parts_below_reorder']} of {inventory['parts_tracked']} parts "
            f"are below their reorder point."
        )
    else:
        headline = f"{when}, plant OEE was {facts['oee'] * 100:.1f}%."

    if day == latest:
        pointer = "The full briefing is above, with the machines and events behind it."
    else:
        pointer = (
            f"That is {day:%d %b}. The dashboard is showing {latest:%d %b} - "
            "switch the date at the top right, or use the button below."
        )

    return {
        "day": day,
        "metric": metric,
        "reply": f"{preamble}{headline} {pointer}",
        "stale": stale,
        "oee": facts["oee"],
        "scrap_rate": facts["scrap_rate"],
        "downtime_minutes": facts["downtime_minutes"],
        "is_current_day": day == latest,
    }

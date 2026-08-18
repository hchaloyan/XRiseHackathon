"""Answer "what happened?" in the chat, from computed data.

The ask bar could already look things up and refuse things, but a supervisor
asking "summarise the most recent activities" got pointed at the dashboard
instead of being told. Sending someone to go and read a table is not an answer,
and it is the one question people type first.

So summaries are a first-class answer now. Every line is assembled from pandas
in kpi_engine, so this is fast, deterministic, and cannot invent a figure. The
model is not involved at all.

This is NOT an intent classifier over free text. It is a keyword match against
a closed set of things a technician asks about their own shift, and it runs
before the metric guard for one reason: "summarise downtime today" contains a
metric word, and the useful reply is the breakdown, not a single number.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, timedelta

from app.services import kpi_engine

# Nouns that mean "something on the production floor". Used to keep the
# imperative phrasings ("show me the ...") from swallowing procedure questions,
# which is the one way this gate could break CLAUDE.md rule 8.
_FLOOR = (
    r"(shift|day|line|plant|floor|downtime|stoppages?|scrap|quality|defects?|"
    r"oee|machines?|materials?|stock|inventory|reorders?|numbers|figures|"
    r"status|summary|report|events?|problems?|issues?)"
)

# Words that mean "tell me what happened", in the register people actually use.
_SUMMARY = re.compile(
    r"\b(summar(y|ise|ize)|recap|rundown|run\s?down|overview|brief(ing|\s+me)?|"
    r"catch\s*me\s*up|catch\s*up|fill\s+me\s+in|bring\s+me\s+up\s+to\s+speed|"
    r"hand\s?(over|off)|shift\s+(report|summary|review)|morning\s+report|"
    r"what\s+happened|what'?s?\s+happened|what'?s\s+new|"
    # "how is M-22 doing", "how are things", "how did we do". The trailing verb
    # is what separates asking after something from "how do I clear a jam".
    r"how\s+(is|are|was|were|did)\s+[\w\s-]{1,24}?\s*(doing|running|performing|going|do|going\s+on|tracking|holding\s+up|look(ing)?)|"
    r"how\s+(did|is|are|was)\s+(we|it|things|today|yesterday|the\s+\w+)|"
    r"how'?s\s+(it|things|the\s+\w+)|what'?s\s+going\s+on|how\s+bad\b|"
    r"where\s+are\s+we(\s+at)?|how\s+are\s+we\s+(doing|tracking|looking)|"
    # Status, but only where it names the floor. "status of the interlock" is a
    # procedure question and must stay out of here.
    r"status\s+update|(shift|line|plant|machine|production|floor)\s+status|"
    r"status\s+(of|on)\s+(the\s+)?(line|plant|floor|shift|machine|production|m-?\s?\d)|"
    r"any(thing)?\s+(issues|problems|trouble|concerns|i\s+should\s+know)|"
    r"(top|main|biggest)\s+(issue|problem|concern)s?|"
    r"what\s+(broke|went\s+wrong|went\s+down|stopped|hurt\s+us)|worst\s+\w+|"
    # Asked as an instruction rather than a question. These MUST name
    # something on the floor: "show me the downtime" is a summary, but "show me
    # the changeover steps" is a procedure question and belongs in retrieval.
    r"(show|give|get)\s+me\s+(the\s+|a\s+|an\s+)?(\w+\s+)?" + _FLOOR + r"|"
    r"tell\s+me\s+(what\s+happened|about\s+(the\s+|today'?s?\s+)?(\w+\s+)?" + _FLOOR + r")|"
    r"what\s+needs\s+(attention|ordering|reorder\w*|restocking|chasing|fixing|looking)|"
    r"what\s+(should\s+i|do\s+i\s+need\s+to)\s+(know|order|reorder|chase|watch|worry))\b",
    re.IGNORECASE,
)

# The subject, when the words name one. Order matters: the first hit wins, so
# the narrower topics come before the general ones.
_TOPICS: list[tuple[str, re.Pattern[str]]] = [
    ("materials", re.compile(r"\b(material\w*|stock|inventory|reorder\w*|order\w*|part[s]?\s+short|running\s+out|consumable\w*)\b", re.I)),
    ("quality", re.compile(r"\b(defect\w*|scrap\w*|reject\w*|quality|porosity|sink\s*mark|burr\w*)\b", re.I)),
    ("downtime", re.compile(r"\b(downtime|stoppage\w*|stopped|stopping|breakdown\w*|outage\w*|jam\w*|fault\w*)\b", re.I)),
    ("machines", re.compile(r"\b(machine\w*|asset\w*|equipment|cell|worst\s+performer)\b", re.I)),
    ("performance", re.compile(r"\b(oee|performance|availability|output|productivity|how\s+did\s+we\s+do)\b", re.I)),
]

_MACHINE_ID = re.compile(r"\bm-?\s?(\d{2})\b", re.IGNORECASE)
_LINE = re.compile(r"\b(molding|moulding|machining|assembly|finishing|packaging)\b", re.I)

_YESTERDAY = re.compile(r"\byesterday\b", re.I)
_WEEK = re.compile(r"\b(this\s+week|last\s+week|past\s+week|last\s+7\s+days|week)\b", re.I)


@dataclass
class Summary:
    title: str
    bullets: list[str] = field(default_factory=list)
    day: date | None = None
    is_current_day: bool = True
    follow_ups: list[str] = field(default_factory=list)


def wants_summary(query: str) -> bool:
    """True when the question asks to be told what happened."""
    return bool(_SUMMARY.search(query))


def _clock(value) -> str:
    """HH:MM from whatever `start` happens to be.

    kpi_engine.events() carries pandas Timestamps, not the ISO strings the API
    serialises them into, so slicing the value works on the wire and raises
    here. Formatting handles both.
    """
    if hasattr(value, "strftime"):
        return value.strftime("%H:%M")
    return str(value)[11:16]


def _pct(value: float) -> str:
    return f"{value * 100:.1f}%"


def _plural(n: int, one: str, many: str | None = None) -> str:
    return one if n == 1 else (many or one + "s")


def _resolve_day(query: str, days: list[date]) -> date:
    latest = days[-1]
    if _YESTERDAY.search(query):
        wanted = date.today() - timedelta(days=1)
        return wanted if wanted in days else latest
    return latest


def answer(query: str) -> Summary:
    """A computed summary of whatever the question is about."""
    days = sorted({p["day"] for p in kpi_engine.trend()})
    day = _resolve_day(query, days)
    latest = days[-1]
    events = kpi_engine.events(day)
    plant = kpi_engine.plant(day)

    machine_hit = _MACHINE_ID.search(query)
    line_hit = _LINE.search(query)

    if machine_hit:
        summary = _machine(f"M-{machine_hit.group(1)}", day, events)
    elif line_hit:
        summary = _line(line_hit.group(1).upper().replace("MOULDING", "MOLDING"), day, events)
    else:
        topic = next((name for name, pattern in _TOPICS if pattern.search(query)), None)
        summary = {
            "materials": _materials,
            "quality": _quality,
            "downtime": _downtime,
            "machines": _machines,
            "performance": _performance,
        }.get(topic, _shift)(day, events, plant)

    summary.day = day
    summary.is_current_day = day == latest
    return summary


# ---------------------------------------------------------------- summaries


def _shift(day: date, events: list[dict], plant: dict) -> Summary:
    """The default: what a supervisor wants on walking in."""
    downtime = [e for e in events if e["kind"] == "downtime"]
    quality = [e for e in events if e["kind"] == "quality"]
    stopped = sum(e["duration_minutes"] or 0 for e in downtime)
    rejected = sum(e["defect_count"] or 0 for e in quality)
    inventory = kpi_engine.inventory(day)
    by_reason = kpi_engine.downtime_by_reason(day)
    worst = kpi_engine.by_machine(day)[0]

    bullets = [
        f"OEE {_pct(plant['oee'])} on {plant['good_count']:,} good parts of "
        f"{plant['total_count']:,}, scrap {_pct(plant['scrap_rate'])}.",
        f"{len(downtime)} {_plural(len(downtime), 'stoppage')} costing "
        f"{stopped:.0f} minutes"
        + (f", the largest being {by_reason[0]['reason_code']} at {by_reason[0]['minutes']:.0f} minutes."
           if by_reason else "."),
        f"{len(quality)} quality {_plural(len(quality), 'event')} covering "
        f"{rejected} rejected {_plural(rejected, 'part')}."
        if quality else "No quality events logged.",
        f"Lowest machine was {worst['machine_id']} {worst['name']} at "
        f"{_pct(worst['oee'])} OEE.",
    ]
    if inventory["parts_below_reorder"]:
        bullets.append(
            f"{inventory['parts_below_reorder']} of {inventory['parts_tracked']} parts "
            f"below reorder point. {inventory['soonest_description']} runs out first, "
            f"about {inventory['soonest_days']} days left."
        )

    return Summary(
        title=f"Shift summary for {day:%a %d %b}",
        bullets=bullets,
        follow_ups=["What stopped the line?", "Show me the worst machines", "What needs reordering?"],
    )


def _downtime(day: date, events: list[dict], plant: dict) -> Summary:
    rows = [e for e in events if e["kind"] == "downtime"]
    by_reason = kpi_engine.downtime_by_reason(day)
    total = sum(e["duration_minutes"] or 0 for e in rows)

    bullets = [
        f"{total:.0f} minutes lost across {len(rows)} "
        f"{_plural(len(rows), 'stoppage')}."
    ]
    bullets += [
        f"{r['reason_code']}: {r['minutes']:.0f} minutes over {r['events']} "
        f"{_plural(r['events'], 'event')}."
        for r in by_reason[:5]
    ]
    longest = max(rows, key=lambda e: e["duration_minutes"] or 0, default=None)
    if longest:
        bullets.append(
            f"Longest single stop was {longest['machine_id']} for "
            f"{longest['duration_minutes']:.0f} minutes"
            + (f': "{longest["operator_note"]}"' if longest["operator_note"] else ".")
        )

    return Summary(
        title=f"Stoppages on {day:%a %d %b}",
        bullets=bullets,
        follow_ups=["Show me the worst machines", "Give me the shift summary"],
    )


def _quality(day: date, events: list[dict], plant: dict) -> Summary:
    rows = [e for e in events if e["kind"] == "quality"]
    by_type = kpi_engine.defects_by_type(day)
    rejected = sum(e["defect_count"] or 0 for e in rows)

    if not rows:
        return Summary(
            title=f"Quality on {day:%a %d %b}",
            bullets=["No quality events were logged on this day."],
            follow_ups=["Give me the shift summary"],
        )

    worst_machine = max(
        {e["machine_id"] for e in rows},
        key=lambda mid: sum(e["defect_count"] or 0 for e in rows if e["machine_id"] == mid),
    )
    bullets = [
        f"{rejected} rejected {_plural(rejected, 'part')} across {len(rows)} "
        f"{_plural(len(rows), 'event')}, plant scrap {_pct(plant['scrap_rate'])}."
    ]
    bullets += [f"{d['defect_type']}: {d['count']} parts." for d in by_type[:5]]
    bullets.append(f"Most affected machine was {worst_machine}.")

    return Summary(
        title=f"Quality on {day:%a %d %b}",
        bullets=bullets,
        follow_ups=["What stopped the line?", "Give me the shift summary"],
    )


def _materials(day: date, events: list[dict], plant: dict) -> Summary:
    inventory = kpi_engine.inventory(day)
    short = [i for i in inventory["items"] if i["status"] != "ok"]

    bullets = [
        f"{inventory['parts_below_reorder']} of {inventory['parts_tracked']} parts "
        f"are below their reorder point."
    ]
    bullets += [
        f"{i['part_id']} {i['description']}: {i['on_hand']} {i['uom']} left, about "
        f"{i['days_of_cover']} days. Order {i['suggested_order_qty']} {i['uom']}."
        for i in short[:5]
    ]
    if not short:
        bullets.append("Nothing needs ordering today.")
    starved = inventory.get("starved_minutes_by_line") or {}
    for line, minutes in starved.items():
        bullets.append(f"The {line} line lost {minutes:.0f} minutes to material starvation.")

    return Summary(
        title=f"Materials on {day:%a %d %b}",
        bullets=bullets,
        follow_ups=["Give me the shift summary", "What stopped the line?"],
    )


def _machines(day: date, events: list[dict], plant: dict) -> Summary:
    machines = kpi_engine.by_machine(day)  # already worst first
    bullets = [
        f"{m['machine_id']} {m['name']}: OEE {_pct(m['oee'])}, "
        f"{m['downtime_minutes']:.0f} min down, scrap {_pct(m['scrap_rate'])}."
        for m in machines[:5]
    ]
    bullets.insert(0, f"{len(machines)} machines ran. The five lowest on OEE:")
    return Summary(
        title=f"Machines on {day:%a %d %b}",
        bullets=bullets,
        follow_ups=["What stopped the line?", "Give me the shift summary"],
    )


def _performance(day: date, events: list[dict], plant: dict) -> Summary:
    facts = kpi_engine.insight_facts(day)
    bullets = [
        f"OEE {_pct(plant['oee'])}, made of availability {_pct(plant['availability'])}, "
        f"performance {_pct(plant['performance'])} and quality {_pct(plant['quality'])}.",
        f"{plant['good_count']:,} good parts of {plant['total_count']:,}, "
        f"scrap {_pct(plant['scrap_rate'])}.",
        f"{plant['downtime_minutes']:.0f} minutes of downtime.",
    ]
    if facts["prior_oee"] is not None:
        delta = (facts["oee_delta"] or 0) * 100
        direction = "up" if delta >= 0 else "down"
        bullets.append(
            f"That is {direction} {abs(delta):.1f} points on {facts['prior_day']:%a %d %b}."
        )
    return Summary(
        title=f"How the plant ran on {day:%a %d %b}",
        bullets=bullets,
        follow_ups=["Show me the worst machines", "What stopped the line?"],
    )


def _machine(machine_id: str, day: date, events: list[dict]) -> Summary:
    machine_id = machine_id.upper()
    rows = [e for e in events if e["machine_id"].upper() == machine_id]
    stats = next(
        (m for m in kpi_engine.by_machine(day) if m["machine_id"].upper() == machine_id), None
    )
    if stats is None:
        return Summary(
            title=f"{machine_id} on {day:%a %d %b}",
            bullets=[f"No production recorded for {machine_id} on this day."],
        )

    downtime = [e for e in rows if e["kind"] == "downtime"]
    quality = [e for e in rows if e["kind"] == "quality"]
    bullets = [
        f"OEE {_pct(stats['oee'])} on {stats['good_count']:,} good of "
        f"{stats['total_count']:,} parts, scrap {_pct(stats['scrap_rate'])}.",
        f"{stats['downtime_minutes']:.0f} minutes down across {len(downtime)} "
        f"{_plural(len(downtime), 'stoppage')}.",
    ]
    bullets += [
        f"{_clock(e['start'])} {e['reason_code']}, {e['duration_minutes']:.0f} min"
        + (f': "{e["operator_note"]}"' if e["operator_note"] else "")
        for e in downtime[:4]
    ]
    for e in quality[:3]:
        bullets.append(f"{_clock(e['start'])} {e['defect_type']}, {e['defect_count']} parts.")

    return Summary(
        title=f"{machine_id} {stats['name']} on {day:%a %d %b}",
        bullets=bullets,
        follow_ups=["Give me the shift summary", "Show me the worst machines"],
    )


def _line(line: str, day: date, events: list[dict]) -> Summary:
    rows = [e for e in events if e["line"].upper() == line]
    machines = [m for m in kpi_engine.by_machine(day) if m["line"].upper() == line]
    if not machines:
        return Summary(
            title=f"{line} line on {day:%a %d %b}",
            bullets=[f"No machines found on a line called {line}."],
        )

    stopped = sum(e["duration_minutes"] or 0 for e in rows if e["kind"] == "downtime")
    rejected = sum(e["defect_count"] or 0 for e in rows if e["kind"] == "quality")
    total = sum(m["total_count"] for m in machines)
    good = sum(m["good_count"] for m in machines)

    bullets = [
        f"{len(machines)} machines on the {line} line made {good:,} good parts of {total:,}.",
        f"{stopped:.0f} minutes of downtime and {rejected} rejected "
        f"{_plural(rejected, 'part')}.",
    ]
    bullets += [
        f"{m['machine_id']} {m['name']}: OEE {_pct(m['oee'])}, "
        f"{m['downtime_minutes']:.0f} min down."
        for m in machines[:4]
    ]
    return Summary(
        title=f"{line} line on {day:%a %d %b}",
        bullets=bullets,
        follow_ups=["Give me the shift summary", "What needs reordering?"],
    )

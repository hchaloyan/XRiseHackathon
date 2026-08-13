"""The shift report: one day, assembled once, exported three ways.

This is not a second reporting system. It is the briefing the supervisor
already has on screen, plus the detail that did not fit there, serialised into
whichever format the next person downstream needs:

    PDF    to read or attach to an email
    Excel  to pivot, one sheet per section
    MIS    flat CSV, one row per metric, for loading into a plant system

Every figure comes from kpi_engine and every narrative from the insights cache.
Nothing here computes and nothing here generates: if the briefing has not been
generated for this day, the report ships the numbers and says the narrative was
not requested, rather than quietly triggering a ten-second model call inside a
file download.
"""

from __future__ import annotations

import csv
import io
from datetime import date, datetime

from app.services import kpi_engine

TIME_SAVED_MINUTES = 35  # see METHOD below


METHOD = (
    "Compiled automatically from machine data. The same report assembled by "
    f"hand in a spreadsheet takes about {TIME_SAVED_MINUTES} minutes: pulling "
    "counts per machine, working out availability and performance, chasing "
    "operator notes for the stoppages, and checking stock against reorder "
    "points."
)


def gather(day: date | None = None) -> dict:
    """Everything the report shows, computed. No model call."""
    from app.routers import insights as insights_router

    resolved = day or kpi_engine.latest_day()
    snapshot = kpi_engine.snapshot(resolved)
    facts = kpi_engine.insight_facts(resolved)

    # Read-only peek at the cache: whether a narrative exists is a property of
    # what the user has already asked for, and a download must not become a
    # generation.
    cached = insights_router._cache.get(resolved)

    return {
        "day": resolved,
        "generated_at": datetime.now(),
        "plant": snapshot["plant"],
        "machines": snapshot["machines"],
        "events": snapshot["events"],
        "inventory": snapshot["inventory"],
        "downtime_by_reason": facts["downtime_by_reason"],
        "defects_by_type": facts["defects_by_type"],
        "prior_oee": facts["prior_oee"],
        "oee_delta": facts["oee_delta"],
        "headline": cached.headline if cached else None,
        "narrative": cached.narrative if cached else None,
        "callouts": (
            [c.model_dump() for c in cached.callouts]
            if cached and cached.callouts
            else []
        ),
        "documents": _referenced_documents(snapshot["events"]),
        "method": METHOD,
        "time_saved_minutes": TIME_SAVED_MINUTES,
    }


def _referenced_documents(events: list[dict]) -> list[dict]:
    """SOPs covering the reason codes and defects seen on this day.

    Retrieved, not written: the report cites documents that exist and that
    genuinely cover the day's events, rather than a static appendix.
    """
    from app.services import root_cause as rc
    from app.services.knowledge_base import get_knowledge_base

    # One lookup per distinct code, not per event - a day with twelve jams
    # should not run twelve identical searches.
    seen_codes: list[dict] = []
    for event in events:
        code = event.get("reason_code") or event.get("defect_type")
        if code and code not in [c["code"] for c in seen_codes]:
            seen_codes.append({"code": code, "event": event})

    found: dict[str, dict] = {}
    try:
        kb = get_knowledge_base()
        for entry in seen_codes:
            event = entry["event"]
            query = rc.sop_query(
                {
                    "reason_code": event.get("reason_code"),
                    "defect_type": event.get("defect_type"),
                    "machine_type": event.get("machine_type", ""),
                }
            )
            for chunk in kb.search(query, top_k=1):
                found.setdefault(
                    chunk["doc_id"],
                    {
                        "doc_id": chunk["doc_id"],
                        "title": chunk["title"],
                        "section": chunk["section"],
                        "covers": [],
                    },
                )["covers"].append(entry["code"])
    except Exception as exc:
        print(f"[report] document lookup failed (non-fatal): {type(exc).__name__}: {exc}")

    return sorted(found.values(), key=lambda d: d["doc_id"])


def _pct(value: float | None) -> str:
    return "-" if value is None else f"{value * 100:.1f}%"


# ---------------------------------------------------------------- MIS (CSV)


def build_mis(day: date | None = None) -> bytes:
    """Flat metric/value rows. The shape a plant MIS ingests.

    Deliberately one row per metric rather than a wide table: an MIS import
    maps columns to fields, and a long format survives new metrics being added
    without the mapping breaking.
    """
    data = gather(day)
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(["report_date", "section", "entity", "metric", "value", "unit"])

    d = data["day"].isoformat()
    plant = data["plant"]
    for metric, value, unit in [
        ("oee", plant["oee"], "ratio"),
        ("availability", plant["availability"], "ratio"),
        ("performance", plant["performance"], "ratio"),
        ("quality", plant["quality"], "ratio"),
        ("scrap_rate", plant["scrap_rate"], "ratio"),
        ("downtime", plant["downtime_minutes"], "minutes"),
        ("good_count", plant["good_count"], "parts"),
        ("total_count", plant["total_count"], "parts"),
    ]:
        writer.writerow([d, "plant", "PLANT", metric, value, unit])

    for m in data["machines"]:
        for metric, value, unit in [
            ("oee", m["oee"], "ratio"),
            ("availability", m["availability"], "ratio"),
            ("performance", m["performance"], "ratio"),
            ("quality", m["quality"], "ratio"),
            ("scrap_rate", m["scrap_rate"], "ratio"),
            ("downtime", m["downtime_minutes"], "minutes"),
            ("good_count", m["good_count"], "parts"),
            ("total_count", m["total_count"], "parts"),
        ]:
            writer.writerow([d, "machine", m["machine_id"], metric, value, unit])

    for r in data["downtime_by_reason"]:
        writer.writerow([d, "downtime_reason", r["reason_code"], "minutes", r["minutes"], "minutes"])
        writer.writerow([d, "downtime_reason", r["reason_code"], "events", r["events"], "count"])

    for q in data["defects_by_type"]:
        writer.writerow([d, "defect", q["defect_type"], "parts", q["count"], "parts"])

    for item in data["inventory"]["items"]:
        writer.writerow([d, "inventory", item["part_id"], "on_hand", item["on_hand"], item["uom"]])
        writer.writerow([d, "inventory", item["part_id"], "days_of_cover", item["days_of_cover"], "days"])
        writer.writerow([d, "inventory", item["part_id"], "status", item["status"], "state"])

    return out.getvalue().encode("utf-8")


# ---------------------------------------------------------------- Excel


def build_xlsx(day: date | None = None) -> bytes:
    """One sheet per section, so each is pivotable on its own."""
    import pandas as pd

    data = gather(day)
    buffer = io.BytesIO()

    summary = pd.DataFrame(
        [
            ("Date", data["day"].isoformat()),
            ("Generated", data["generated_at"].strftime("%Y-%m-%d %H:%M")),
            ("OEE", _pct(data["plant"]["oee"])),
            ("Availability", _pct(data["plant"]["availability"])),
            ("Performance", _pct(data["plant"]["performance"])),
            ("Quality", _pct(data["plant"]["quality"])),
            ("Scrap rate", _pct(data["plant"]["scrap_rate"])),
            ("Downtime (min)", data["plant"]["downtime_minutes"]),
            ("Good parts", data["plant"]["good_count"]),
            ("Total parts", data["plant"]["total_count"]),
            ("Prior day OEE", _pct(data["prior_oee"])),
            ("Parts below reorder", data["inventory"]["parts_below_reorder"]),
            ("Headline", data["headline"] or "Briefing not generated for this day"),
            ("Narrative", data["narrative"] or ""),
            ("Method", data["method"]),
        ],
        columns=["Field", "Value"],
    )

    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        summary.to_excel(writer, sheet_name="Summary", index=False)
        pd.DataFrame(data["machines"]).to_excel(writer, sheet_name="Machines", index=False)
        pd.DataFrame(data["events"]).to_excel(writer, sheet_name="Events", index=False)
        pd.DataFrame(data["inventory"]["items"]).to_excel(
            writer, sheet_name="Materials", index=False
        )
        pd.DataFrame(data["downtime_by_reason"]).to_excel(
            writer, sheet_name="Downtime by reason", index=False
        )
        if data["defects_by_type"]:
            pd.DataFrame(data["defects_by_type"]).to_excel(
                writer, sheet_name="Defects", index=False
            )
        if data["documents"]:
            pd.DataFrame(
                [
                    {
                        "doc_id": doc["doc_id"],
                        "title": doc["title"],
                        "section": doc["section"],
                        "covers": ", ".join(doc["covers"]),
                    }
                    for doc in data["documents"]
                ]
            ).to_excel(writer, sheet_name="Referenced documents", index=False)

    return buffer.getvalue()


# ---------------------------------------------------------------- PDF


def build_pdf(day: date | None = None) -> bytes:
    """A page a supervisor can print or attach without editing."""
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_LEFT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import (
        PageBreak,
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
    )

    data = gather(day)
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        title=f"Shift report {data['day']}",
        author="MFGX AI",
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
    )

    styles = getSampleStyleSheet()
    h1 = ParagraphStyle("h1", parent=styles["Heading1"], fontSize=18, spaceAfter=2)
    h2 = ParagraphStyle("h2", parent=styles["Heading2"], fontSize=12, spaceBefore=12)
    body = ParagraphStyle("body", parent=styles["BodyText"], fontSize=9.5, leading=13.5)
    small = ParagraphStyle(
        "small", parent=body, fontSize=8, textColor=colors.HexColor("#666666"),
        alignment=TA_LEFT,
    )

    def table(rows, widths, header=True):
        t = Table(rows, colWidths=widths, repeatRows=1 if header else 0)
        style = [
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor("#222222")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("LINEBELOW", (0, 0), (-1, -2), 0.25, colors.HexColor("#DDDDDD")),
        ]
        if header:
            style += [
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("LINEBELOW", (0, 0), (-1, 0), 0.75, colors.HexColor("#333333")),
            ]
        t.setStyle(TableStyle(style))
        return t

    story: list = []
    story.append(Paragraph(f"Shift report — {data['day']:%A %d %B %Y}", h1))
    story.append(
        Paragraph(
            f"Generated {data['generated_at']:%d %b %Y %H:%M} · MFGX AI", small
        )
    )

    if data["headline"]:
        story.append(Spacer(1, 8))
        story.append(Paragraph(f"<b>{data['headline']}</b>", body))
    if data["narrative"]:
        story.append(Spacer(1, 4))
        story.append(Paragraph(data["narrative"], body))
    if not data["headline"] and not data["narrative"]:
        story.append(Spacer(1, 8))
        story.append(
            Paragraph(
                "<i>Narrative not generated for this day. Every figure below is "
                "computed from machine data and is unaffected.</i>",
                body,
            )
        )

    plant = data["plant"]
    story.append(Paragraph("Plant", h2))
    story.append(
        table(
            [
                ["OEE", "Availability", "Performance", "Quality", "Scrap", "Downtime"],
                [
                    _pct(plant["oee"]),
                    _pct(plant["availability"]),
                    _pct(plant["performance"]),
                    _pct(plant["quality"]),
                    _pct(plant["scrap_rate"]),
                    f"{plant['downtime_minutes']:.0f} min",
                ],
            ],
            widths=[28 * mm] * 6,
        )
    )

    if data["callouts"]:
        story.append(Paragraph("What needs attention", h2))
        for c in data["callouts"]:
            metric = f" — {c['metric']}" if c.get("metric") else ""
            story.append(
                Paragraph(
                    f"<b>{c['title']}</b> ({c['severity']}){metric}<br/>{c['detail']}",
                    body,
                )
            )
            story.append(Spacer(1, 4))

    story.append(Paragraph("Machines (worst OEE first)", h2))
    story.append(
        table(
            [["Machine", "Line", "OEE", "Scrap", "Downtime", "Good / Total"]]
            + [
                [
                    f"{m['machine_id']} {m['name'][:26]}",
                    m["line"],
                    _pct(m["oee"]),
                    _pct(m["scrap_rate"]),
                    f"{m['downtime_minutes']:.0f} min",
                    f"{m['good_count']} / {m['total_count']}",
                ]
                for m in data["machines"]
            ],
            widths=[62 * mm, 20 * mm, 18 * mm, 18 * mm, 22 * mm, 28 * mm],
        )
    )

    story.append(Paragraph("Downtime by reason", h2))
    story.append(
        table(
            [["Reason", "Minutes", "Events"]]
            + [
                [r["reason_code"], f"{r['minutes']:.0f}", str(r["events"])]
                for r in data["downtime_by_reason"]
            ],
            widths=[80 * mm, 30 * mm, 30 * mm],
        )
    )

    inv = data["inventory"]
    story.append(Paragraph("Materials", h2))
    story.append(
        Paragraph(
            f"{inv['parts_below_reorder']} of {inv['parts_tracked']} parts below "
            f"reorder point. {inv['soonest_description']} runs out first, about "
            f"{inv['soonest_days']} days left.",
            body,
        )
    )
    story.append(Spacer(1, 4))
    short = [i for i in inv["items"] if i["status"] != "ok"]
    if short:
        story.append(
            table(
                [["Part", "On hand", "Days left", "Action", "Order"]]
                + [
                    [
                        f"{i['part_id']} {i['description'][:34]}",
                        f"{i['on_hand']} {i['uom']}",
                        f"{i['days_of_cover']}",
                        i["status"].replace("_", " "),
                        f"{i['suggested_order_qty']} {i['uom']}",
                    ]
                    for i in short
                ],
                widths=[70 * mm, 24 * mm, 20 * mm, 28 * mm, 26 * mm],
            )
        )

    if data["events"]:
        story.append(PageBreak())
        story.append(Paragraph("Events", h2))
        story.append(
            table(
                [["Time", "Machine", "Type", "Detail"]]
                + [
                    [
                        str(e["start"])[11:16],
                        e["machine_id"],
                        e["reason_code"] or e["defect_type"] or "",
                        (
                            f"{e['duration_minutes']:.0f} min · {e['operator_note'] or ''}"
                            if e["kind"] == "downtime"
                            else f"{e['defect_count']} parts"
                        )[:78],
                    ]
                    for e in data["events"]
                ],
                widths=[16 * mm, 20 * mm, 34 * mm, 104 * mm],
            )
        )

    if data["documents"]:
        story.append(Paragraph("Referenced procedures", h2))
        story.append(
            table(
                [["Document", "Section", "Covers"]]
                + [
                    [d["doc_id"], d["section"][:40], ", ".join(d["covers"])[:44]]
                    for d in data["documents"]
                ],
                widths=[24 * mm, 66 * mm, 84 * mm],
            )
        )

    story.append(Spacer(1, 10))
    story.append(Paragraph(data["method"], small))

    doc.build(story)
    return buffer.getvalue()


BUILDERS = {
    "pdf": (build_pdf, "application/pdf", "pdf"),
    "xlsx": (build_xlsx, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "xlsx"),
    "mis": (build_mis, "text/csv", "csv"),
}

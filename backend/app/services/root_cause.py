"""Correlate events and assemble evidence FIRST, then call the model.

Everything in this module is pandas. The model's only job is to rank
hypotheses against evidence that was already gathered and counted here
(rule 1). A ranked cause with no supporting figure behind it is worth
nothing in front of manufacturing judges.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any

import pandas as pd

from app.services.data_loader import load

# How far either side of an event to look for things that co-occurred.
WINDOW = timedelta(hours=4)

# Free-text search terms per reason code / defect type, used to pull the
# relevant SOP sections. Keeps retrieval deterministic rather than depending
# on however the operator happened to phrase their note.
SOP_QUERIES = {
    "CHANGEOVER": "changeover procedure first-off approval setup time",
    "PM": "preventive maintenance schedule lubrication weekly",
    "MATERIAL_STARVE": "material starvation line-side replenishment reorder point",
    "SENSOR_FAULT": "sensor fault diagnosis recalibration proximity switch probe",
    "TOOL_BREAK": "tool breakage insert replacement carbide wear",
    "JAM": "jam clearing part stuck ejector sprue",
    "ROBOT_FAULT": "robot fault recovery gripper re-home overtravel",
    "BUILD_FAILURE": "build failure part lifted plate recoater levelling",
    "WELD_POROSITY": "weld porosity shielding gas flow contact tip",
    "SPATTER": "weld spatter voltage wire feed contact tip distance",
    "UNDERCUT": "weld undercut travel speed torch angle",
    "SINK_MARK": "sink mark holding pressure packing gate",
    "SHORT_SHOT": "short shot incomplete fill injection pressure venting",
    "FLASH": "flash parting line clamp tonnage torque",
    "WARP": "warp uneven cooling water circuits ejection",
    "CONTAMINATION": "contamination purge colour change regrind",
    "DIM_OOT": "dimensional out of tolerance work offsets first article",
    "BURR": "burr tool wear coolant concentration",
    "TOOL_MARK": "tool mark surface finish chatter",
    "SURFACE_FINISH": "surface finish chatter way lube spindle",
    "SCRATCH": "handling damage dunnage scratch",
    "MISSING_FASTENER": "missing fastener rivet feed track presence sensor",
    "MISALIGNMENT": "misalignment fixture clamp locating pins first-off",
}


def _machine_row(machine_id: str) -> dict[str, Any]:
    machines = load()["machines"].set_index("machine_id")
    row = machines.loc[machine_id]
    return {
        "machine_id": machine_id,
        "name": row["name"],
        "machine_type": row["machine_type"],
        "line": row["line"],
        "cell": row["cell"],
    }


def find_event(event_id: str) -> dict[str, Any] | None:
    """Locate a downtime or quality event by id and normalise its shape."""
    frames = load()

    downtime = frames["downtime_events"]
    hit = downtime[downtime["event_id"] == event_id]
    if not hit.empty:
        r = hit.iloc[0]
        return {
            "event_id": event_id,
            "kind": "downtime",
            "start": r["start"],
            "day": r["day"],
            "shift": r["shift"],
            "duration_minutes": round(float(r["duration_minutes"]), 1),
            "reason_code": r["reason_code"],
            "operator_note": r["operator_note"],
            "defect_type": None,
            "defect_count": None,
            **_machine_row(r["machine_id"]),
        }

    quality = frames["quality_events"]
    hit = quality[quality["event_id"] == event_id]
    if not hit.empty:
        r = hit.iloc[0]
        return {
            "event_id": event_id,
            "kind": "quality",
            "start": r["timestamp"],
            "day": r["day"],
            "shift": r["shift"],
            "duration_minutes": None,
            "reason_code": None,
            "operator_note": None,
            "defect_type": r["defect_type"],
            "defect_count": int(r["count"]),
            **_machine_row(r["machine_id"]),
        }

    return None


def _history(event: dict[str, Any]) -> dict[str, Any]:
    """How often has this happened before, on this machine and this line?"""
    frames = load()
    machines = frames["machines"][["machine_id", "line", "machine_type"]]

    if event["kind"] == "downtime":
        df = frames["downtime_events"].merge(machines, on="machine_id", how="left")
        same_kind = df[df["reason_code"] == event["reason_code"]]
        label = event["reason_code"]
        time_col = "start"  # quality events carry `timestamp`, downtime `start`
        minutes_on_machine = float(
            same_kind[same_kind["machine_id"] == event["machine_id"]]["duration_minutes"].sum()
        )
    else:
        df = frames["quality_events"].merge(machines, on="machine_id", how="left")
        same_kind = df[df["defect_type"] == event["defect_type"]]
        label = event["defect_type"]
        time_col = "timestamp"
        minutes_on_machine = 0.0

    on_machine = same_kind[same_kind["machine_id"] == event["machine_id"]]
    on_line = same_kind[same_kind["line"] == event["line"]]
    days = df["day"].nunique() or 1

    return {
        "label": label,
        "occurrences_on_machine": int(len(on_machine)),
        "occurrences_on_line": int(len(on_line)),
        "occurrences_plant": int(len(same_kind)),
        "window_days": int(days),
        "minutes_on_machine": round(minutes_on_machine, 1),
        # Recent operator notes are the closest thing to a maintenance log.
        # Deduplicated: the same note repeated adds no signal for the model,
        # it just crowds out the other evidence. Quality events carry no note,
        # so this is empty for defects.
        "recent_notes": (
            on_machine.sort_values(time_col, ascending=False)
            .get("operator_note", pd.Series(dtype=str))
            .dropna().drop_duplicates().head(4).tolist()
        ),
    }


def _nearby(event: dict[str, Any]) -> dict[str, Any]:
    """Other events on the same machine or line within +/- WINDOW.

    This is where the interesting correlations live: a MATERIAL_STARVE an
    hour before a JAM, or a CHANGEOVER immediately before a run of defects.
    """
    frames = load()
    machines = frames["machines"][["machine_id", "line"]]
    at = event["start"]
    lo, hi = at - WINDOW, at + WINDOW

    downtime = frames["downtime_events"].merge(machines, on="machine_id", how="left")
    near_dt = downtime[
        (downtime["start"] >= lo)
        & (downtime["start"] <= hi)
        & (downtime["event_id"] != event["event_id"])
        & (downtime["line"] == event["line"])
    ].sort_values("start")

    quality = frames["quality_events"].merge(machines, on="machine_id", how="left")
    near_qc = quality[
        (quality["timestamp"] >= lo)
        & (quality["timestamp"] <= hi)
        & (quality["event_id"] != event["event_id"])
        & (quality["line"] == event["line"])
    ].sort_values("timestamp")

    def offset(ts) -> str:
        minutes = (ts - at).total_seconds() / 60
        return f"{abs(minutes):.0f} min {'after' if minutes >= 0 else 'before'}"

    return {
        "downtime": [
            {
                "event_id": r.event_id,
                "machine_id": r.machine_id,
                "reason_code": r.reason_code,
                "duration_minutes": round(float(r.duration_minutes), 1),
                "operator_note": r.operator_note,
                "offset": offset(r.start),
                "same_machine": r.machine_id == event["machine_id"],
            }
            for r in near_dt.itertuples()
        ][:6],
        "quality": [
            {
                "event_id": r.event_id,
                "machine_id": r.machine_id,
                "defect_type": r.defect_type,
                "count": int(r.count),
                "offset": offset(r.timestamp),
                "same_machine": r.machine_id == event["machine_id"],
            }
            for r in near_qc.itertuples()
        ][:6],
    }


def _shift_context(event: dict[str, Any]) -> dict[str, Any]:
    """What the machine's day looked like around the event."""
    frames = load()
    day = event["day"]

    downtime = frames["downtime_events"]
    machine_day = downtime[
        (downtime["machine_id"] == event["machine_id"]) & (downtime["day"] == day)
    ]

    runs = frames["production_runs"]
    machine_runs = runs[
        (runs["machine_id"] == event["machine_id"]) & (runs["day"] == day)
    ]
    total = int(machine_runs["total_count"].sum())
    good = int(machine_runs["good_count"].sum())

    return {
        "day": day,
        "shift": event["shift"],
        "machine_downtime_minutes": round(float(machine_day["duration_minutes"].sum()), 1),
        "machine_downtime_events": int(len(machine_day)),
        "machine_total_count": total,
        "machine_good_count": good,
        "machine_scrap_rate": round((total - good) / total, 4) if total else 0.0,
        "changeover_earlier_today": bool(
            (
                (machine_day["reason_code"] == "CHANGEOVER")
                & (machine_day["start"] < event["start"])
            ).any()
        ),
    }


def _inventory_context(event: dict[str, Any]) -> dict[str, Any] | None:
    """Only relevant for starvation, but cheap enough to always compute."""
    frames = load()
    items = frames["inventory"]
    on_line = items[items["line"] == event["line"]].copy()
    if on_line.empty:
        return None

    on_line["days_of_cover"] = (on_line["on_hand"] / on_line["daily_usage"]).round(1)
    short = on_line[on_line["on_hand"] < on_line["reorder_point"]]

    return {
        "line": event["line"],
        "parts_below_reorder": [
            {
                "part_id": r.part_id,
                "description": r.description,
                "on_hand": int(r.on_hand),
                "reorder_point": int(r.reorder_point),
                "days_of_cover": float(r.days_of_cover),
            }
            for r in short.itertuples()
        ],
        "lowest_days_of_cover": float(on_line["days_of_cover"].min()),
    }


def sop_query(event: dict[str, Any]) -> str:
    """Deterministic retrieval terms for this event's SOP citations."""
    key = event["reason_code"] or event["defect_type"] or ""
    base = SOP_QUERIES.get(key, key.replace("_", " ").lower())
    return f"{base} {event['machine_type']}".strip()


def assemble(event_id: str) -> dict[str, Any] | None:
    """All evidence for one event. Pure pandas - no model has run yet."""
    event = find_event(event_id)
    if event is None:
        return None

    return {
        "event": event,
        "history": _history(event),
        "nearby": _nearby(event),
        "shift": _shift_context(event),
        "inventory": _inventory_context(event),
    }

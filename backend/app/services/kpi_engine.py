"""ALL arithmetic lives here. Pure pandas, zero LLM (CLAUDE.md rule 1).

Standard OEE, computed from time and counts rather than assumed:

    availability = run time / planned time
    performance  = (ideal cycle time x total count) / run time
    quality      = good count / total count
    OEE          = availability x performance x quality

Aggregation is weighted by production time, never an average of machine OEEs
-- averaging percentages across machines with different run times is the
classic way to put a wrong number on stage.
"""

from datetime import date, timedelta
from typing import Any, cast

import numpy as np
import pandas as pd

from app.services.data_loader import load

PLANNED_MINUTES_PER_SHIFT = 480  # 2 shifts/day, matches seed.py SHIFT_MINUTES


def _shift_frame() -> pd.DataFrame:
    """One row per machine-shift: planned/run minutes, ideal minutes, counts."""
    frames = load()
    runs = frames["production_runs"].merge(frames["machines"], on="machine_id", how="left")

    stopped = (
        frames["downtime_events"]
        .groupby(["machine_id", "day", "shift"])["duration_minutes"]
        .sum()
        .rename("downtime_minutes")
    )
    runs = runs.merge(stopped, on=["machine_id", "day", "shift"], how="left")
    runs["downtime_minutes"] = runs["downtime_minutes"].fillna(0.0)

    runs["planned_minutes"] = float(PLANNED_MINUTES_PER_SHIFT)
    runs["run_minutes"] = runs["planned_minutes"] - runs["downtime_minutes"]
    # What the run *should* have taken at ideal cycle time, in minutes.
    runs["ideal_minutes"] = runs["ideal_cycle_time"] * runs["total_count"] / 60
    return runs


def _rollup(df: pd.DataFrame) -> dict:
    """Weighted OEE over any slice of _shift_frame()."""
    planned = float(df["planned_minutes"].sum())
    run = float(df["run_minutes"].sum())
    ideal = float(df["ideal_minutes"].sum())
    good = int(df["good_count"].sum())
    total = int(df["total_count"].sum())
    if not planned or not run or not total:
        return dict(oee=0.0, availability=0.0, performance=0.0, quality=0.0,
                    scrap_rate=0.0, downtime_minutes=0.0, good_count=0, total_count=0)

    availability = run / planned
    performance = ideal / run
    quality = good / total
    return dict(
        oee=round(availability * performance * quality, 4),
        availability=round(availability, 4),
        performance=round(performance, 4),
        quality=round(quality, 4),
        scrap_rate=round((total - good) / total, 4),
        downtime_minutes=round(planned - run, 1),
        good_count=good,
        total_count=total,
    )


def latest_day() -> date:
    """Newest full day in the dataset. The dashboard's default (spec 6.0)."""
    return max(_shift_frame()["day"])


def plant(day: date) -> dict:
    frame = _shift_frame()
    return _rollup(frame[frame["day"] == day])


def by_machine(day: date) -> list[dict]:
    frame = _shift_frame()
    frame = frame[frame["day"] == day]
    rows = [
        {"machine_id": machine_id, "name": group["name"].iloc[0],
         "machine_type": group["machine_type"].iloc[0], "keywords": list(group["keywords"].iloc[0]),
         "line": group["line"].iloc[0], "cell": group["cell"].iloc[0], **_rollup(group)}
        for machine_id, group in frame.groupby("machine_id")
    ]
    return sorted(rows, key=lambda r: r["oee"])  # worst first -- that is what a supervisor opens for


def trend() -> list[dict]:
    """Plant OEE per day across the whole window, for the trend chart."""
    frame = _shift_frame()
    return [
        {"day": day, **_rollup(group)}
        for day, group in frame.groupby("day", sort=True)
    ]


def events(day: date) -> list[dict[str, Any]]:
    """Downtime + quality rows for one day, newest first. Each is expandable
    into root cause on the frontend (rule 7), so both kinds share one shape."""
    frames = load()
    # Name and type ride on every row so the table is searchable by what a
    # supervisor calls the asset, not just by M-33.
    assets = frames["machines"].set_index("machine_id")

    def about(machine_id: str) -> dict:
        row = assets.loc[machine_id]
        return {"machine_id": machine_id, "machine_name": row["name"],
                "machine_type": row["machine_type"], "line": row["line"]}

    downtime = frames["downtime_events"]
    downtime = downtime[downtime["day"] == day]
    quality = frames["quality_events"]
    quality = quality[quality["day"] == day]

    rows = [
        {"event_id": r.event_id, "kind": "downtime", **about(r.machine_id),
         "start": r.start, "shift": r.shift,
         "duration_minutes": round(r.duration_minutes, 1), "reason_code": r.reason_code,
         "operator_note": r.operator_note, "defect_type": None, "defect_count": None}
        for r in cast(Any, downtime.itertuples())
    ] + [
        {"event_id": r.event_id, "kind": "quality", **about(r.machine_id),
         "start": r.timestamp, "shift": r.shift,
         "duration_minutes": None, "reason_code": None, "operator_note": None,
         "defect_type": r.defect_type, "defect_count": int(r.count)}
        for r in cast(Any, quality.itertuples())
    ]
    return sorted(rows, key=lambda r: r["start"], reverse=True)


def inventory(day: date) -> dict:
    """Stock cover, and which lines are losing time to material starvation.

    A snapshot, not a ledger -- there is no receipt/issue history to replay,
    so days of cover is on-hand divided by average daily usage.
    """
    frames = load()
    items = frames["inventory"].copy()
    items["days_of_cover"] = (items["on_hand"] / items["daily_usage"]).round(1)
    items["below_reorder"] = items["on_hand"] < items["reorder_point"]

    # "Days of cover" is a stock-controller's phrase and it left supervisors
    # guessing. These three columns say the same thing in words a shift lead
    # can act on without translating anything.
    def _status(row) -> str:
        if row["below_reorder"]:
            return "reorder_now"
        if row["days_of_cover"] < 7:
            return "order_this_week"
        return "ok"

    items["status"] = items.apply(_status, axis=1)
    items["runs_out_on"] = [
        day + timedelta(days=int(cover)) for cover in items["days_of_cover"]
    ]
    # Enough to clear the reorder point with a week's usage behind it, rounded
    # up to a whole 5 so the number reads like something you would actually put
    # on a requisition.
    shortfall = (items["reorder_point"] * 2 - items["on_hand"]).clip(lower=0)
    weekly = items["daily_usage"] * 7
    items["suggested_order_qty"] = (
        np.ceil(pd.concat([shortfall, weekly], axis=1).max(axis=1) / 5) * 5
    ).astype(int)

    # The correlation worth putting on screen: short parts and stopped lines.
    downtime = frames["downtime_events"]
    starved = downtime[(downtime["day"] == day) & (downtime["reason_code"] == "MATERIAL_STARVE")]
    starved_lines = (
        starved.merge(frames["machines"][["machine_id", "line"]], on="machine_id", how="left")
        .groupby("line")["duration_minutes"].sum().round(1).to_dict()
    )

    short = items[items["below_reorder"]]
    soonest = items.sort_values("days_of_cover").iloc[0]
    return {
        "parts_tracked": len(items),
        "parts_below_reorder": len(short),
        "lowest_days_of_cover": float(items["days_of_cover"].min()),
        # The part that runs out first, named. "Lowest cover 4.4 days" told a
        # supervisor a number without telling them which part to chase.
        "soonest_part_id": str(soonest["part_id"]),
        "soonest_description": str(soonest["description"]),
        "soonest_days": float(soonest["days_of_cover"]),
        "soonest_runs_out_on": soonest["runs_out_on"],
        "starved_minutes_by_line": starved_lines,
        "items": items.sort_values("days_of_cover").to_dict("records"),
    }


def snapshot(day: date | None = None) -> dict:
    """Everything GET /api/kpis returns. One pass, one payload."""
    day = day or latest_day()
    return {"day": day, "plant": plant(day), "trend": trend(),
            "machines": by_machine(day), "events": events(day),
            "inventory": inventory(day)}


def downtime_by_reason(day: date) -> list[dict]:
    """Minutes lost per reason code on one day, worst first."""
    frames = load()
    downtime = frames["downtime_events"]
    downtime = downtime[downtime["day"] == day]
    if downtime.empty:
        return []
    grouped = (
        downtime.groupby("reason_code")
        .agg(minutes=("duration_minutes", "sum"), events=("event_id", "count"))
        .reset_index()
        .sort_values("minutes", ascending=False)
    )
    return [
        {"reason_code": r.reason_code, "minutes": round(float(r.minutes), 1),
         "events": int(r.events)}
        for r in cast(Any, grouped.itertuples())
    ]


def defects_by_type(day: date) -> list[dict]:
    """Defect counts per type on one day, worst first."""
    frames = load()
    quality = frames["quality_events"]
    quality = quality[quality["day"] == day]
    if quality.empty:
        return []
    grouped = (
        quality.groupby("defect_type")["count"].sum()
        .rename("defect_count")  # 'count' shadows the namedtuple method on itertuples
        .sort_values(ascending=False).reset_index()
    )
    return [
        {"defect_type": r.defect_type, "count": int(r.defect_count)}
        for r in cast(Any, grouped.itertuples())
    ]


def insight_facts(day: date | None = None) -> dict:
    """Pre-aggregated numbers for the KPI Insights narrative.

    Every figure the model is allowed to mention is computed here (rule 1).
    The model receives this dict rendered as text and writes prose only.
    """
    day = day or latest_day()
    today = plant(day)

    # Prior day from the trend series, for a direction of travel.
    series = trend()
    prior = None
    for i, point in enumerate(series):
        if point["day"] == day and i > 0:
            prior = series[i - 1]
            break

    machines = by_machine(day)  # already sorted worst OEE first
    inv = inventory(day)

    return {
        "day": day,
        "oee": today["oee"],
        "availability": today["availability"],
        "performance": today["performance"],
        "quality": today["quality"],
        "scrap_rate": today["scrap_rate"],
        "downtime_minutes": today["downtime_minutes"],
        "good_count": today["good_count"],
        "total_count": today["total_count"],
        "prior_day": prior["day"] if prior else None,
        "prior_oee": prior["oee"] if prior else None,
        "oee_delta": round(today["oee"] - prior["oee"], 4) if prior else None,
        "worst_machines": [
            {"machine_id": m["machine_id"], "name": m["name"], "line": m["line"],
             "oee": m["oee"], "downtime_minutes": m["downtime_minutes"],
             "scrap_rate": m["scrap_rate"]}
            for m in machines[:3]
        ],
        "downtime_by_reason": downtime_by_reason(day)[:5],
        "defects_by_type": defects_by_type(day)[:5],
        "parts_below_reorder": inv["parts_below_reorder"],
        "lowest_days_of_cover": inv["lowest_days_of_cover"],
        "starved_minutes_by_line": inv["starved_minutes_by_line"],
    }

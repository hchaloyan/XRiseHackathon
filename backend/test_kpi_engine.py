"""Smoke check for the KPI slice (spec 11). Run: python test_kpi_engine.py

Asserts the arithmetic holds together and that the three planted patterns are
actually findable -- if a seed change flattens them, root cause has nothing to
find and the demo produces generic filler.
"""

import pandas as pd
from fastapi.testclient import TestClient

from app.main import app
from app.services import kpi_engine
from app.services.data_loader import load


def test_oee_identity():
    for row in [kpi_engine.plant(kpi_engine.latest_day()), *kpi_engine.trend()]:
        product = row["availability"] * row["performance"] * row["quality"]
        assert abs(row["oee"] - product) < 1e-3, row
        assert 0 < row["availability"] <= 1, row
        assert 0 < row["quality"] <= 1, row
        assert 0 < row["performance"] < 1, "seed runs slower than ideal by design"


def test_plant_reconciles_with_machines():
    day = kpi_engine.latest_day()
    plant = kpi_engine.plant(day)
    machines = kpi_engine.by_machine(day)
    assert len(machines) == 15
    assert sum(m["total_count"] for m in machines) == plant["total_count"]
    assert sum(m["good_count"] for m in machines) == plant["good_count"]
    # Weighted, not averaged: the two differ, and the weighted one is correct.
    assert plant["oee"] != round(sum(m["oee"] for m in machines) / len(machines), 4)


def test_scrap_reconciles_across_tables():
    """Quality events must sum to the scrap implied by production runs, or
    root cause will correlate two tables that contradict each other."""
    frames = load()
    scrapped = (frames["production_runs"]["total_count"] - frames["production_runs"]["good_count"]).sum()
    assert scrapped == frames["quality_events"]["count"].sum()


def test_pattern_1_changeover_overrun_on_shift_b():
    # Bracket access, not df.shift -- that resolves to DataFrame.shift().
    downtime = load()["downtime_events"]
    changeover = downtime[downtime["reason_code"] == "CHANGEOVER"]
    planted = changeover[(changeover["machine_id"] == "M-22") & (changeover["shift"] == "B")]
    others = changeover.drop(planted.index)
    assert len(planted) >= 14, "every shift B across the window"
    assert planted["duration_minutes"].mean() > 1.5 * others["duration_minutes"].mean()


def test_pattern_2_defect_spike_follows_a_changeover():
    quality = load()["quality_events"]
    spike = quality[quality["machine_id"] == "M-31"]

    # Walk it the way root cause has to: find where the defects start, then the
    # last changeover before that. The machine has several, only one is the cause.
    onset = spike.loc[spike["defect_type"] == "WELD_POROSITY", "timestamp"].min()
    candidates = load()["downtime_events"].query(
        "machine_id == 'M-31' and reason_code == 'CHANGEOVER'"
    )
    changeover = candidates.loc[candidates["start"] < onset, "start"].max()
    assert (onset - changeover) < pd.Timedelta(hours=12), "cause must sit next to effect"

    after = spike[spike["timestamp"] > changeover]
    # The weld cell's own failure mode -- a defect the process can actually produce.
    assert set(after["defect_type"]) == {"WELD_POROSITY"}, "one type, so it is attributable"

    # Scrap rate per part, not per event -- days with no defects are real zeros,
    # and this is the figure the dashboard puts on screen.
    runs = load()["production_runs"].query("machine_id == 'M-31'")
    rate = lambda r: (r["total_count"] - r["good_count"]).sum() / r["total_count"].sum()
    assert rate(runs[runs["start"] > changeover]) > 3 * rate(runs[runs["start"] < changeover])


def test_pattern_3_silent_cycle_time_drift():
    days = sorted({row["day"] for row in kpi_engine.trend()})
    perf = [
        next(m["performance"] for m in kpi_engine.by_machine(day) if m["machine_id"] == "M-13")
        for day in (days[0], days[-1])
    ]
    assert perf[0] - perf[-1] > 0.15, "M-13 must visibly degrade"

    # Silent: on the worst day its availability is still at or above plant
    # level, so nothing in the downtime table explains the OEE drop.
    machines = kpi_engine.by_machine(days[-1])
    drifter = next(m for m in machines if m["machine_id"] == "M-13")
    assert drifter["availability"] >= kpi_engine.plant(days[-1])["availability"]
    assert drifter["performance"] == min(m["performance"] for m in machines)


def test_defects_match_the_process_that_made_them():
    """No SHORT_SHOT on a lathe. A judge from the floor would spot it."""
    frames = load()
    types = frames["machines"].set_index("machine_id")["machine_type"]
    allowed = {
        "Injection Molding": {"SHORT_SHOT", "FLASH", "SINK_MARK", "WARP", "CONTAMINATION"},
        "CNC Machining": {"DIM_OOT", "BURR", "SURFACE_FINISH", "TOOL_MARK"},
        "Robotic Welding": {"WELD_POROSITY", "UNDERCUT", "SPATTER", "MISALIGNMENT"},
        "Assembly": {"MISSING_FASTENER", "MISALIGNMENT", "SCRATCH"},
        "Additive Manufacturing": {"LAYER_DELAM", "WARP", "DIM_OOT", "POROSITY"},
        "Powder Coating": {"ORANGE_PEEL", "THIN_COAT", "CONTAMINATION", "SCRATCH"},
        "Parts Washing": {"RESIDUE", "WATER_SPOT", "CONTAMINATION"},
        "Packaging": {"LABEL_MISPLACED", "CARTON_CRUSH", "MISSING_ITEM"},
    }
    for row in frames["quality_events"].itertuples():
        assert row.defect_type in allowed[types[row.machine_id]], row


def test_machines_are_searchable_by_keyword():
    machines = kpi_engine.by_machine(kpi_engine.latest_day())
    haystack = {
        m["machine_id"]: " ".join([m["name"], m["machine_type"], *m["keywords"]]).lower()
        for m in machines
    }
    for term, expected in [("3d printing", 2), ("molder", 4), ("cnc", 4), ("welding", 1)]:
        hits = [mid for mid, text in haystack.items() if term in text]
        assert len(hits) == expected, f"{term} -> {hits}"


def test_inventory_flags_short_parts():
    inv = kpi_engine.inventory(kpi_engine.latest_day())
    assert inv["parts_tracked"] == 20
    assert 0 < inv["parts_below_reorder"] < inv["parts_tracked"], "some short, not all"
    assert inv["items"] == sorted(inv["items"], key=lambda i: i["days_of_cover"])
    for item in inv["items"]:
        assert item["below_reorder"] == (item["on_hand"] < item["reorder_point"])
        assert item["days_of_cover"] == round(item["on_hand"] / item["daily_usage"], 1)


def test_endpoint_returns_camel_case_200():
    body = TestClient(app).get("/api/kpis").json()
    assert body["plant"]["scrapRate"] >= 0
    assert body["day"] == str(kpi_engine.latest_day())
    assert len(body["trend"]) == 14
    assert {e["kind"] for e in body["events"]} == {"downtime", "quality"}
    assert all(e["durationMinutes"] is None for e in body["events"] if e["kind"] == "quality")
    # `count` shadows tuple.count in itertuples -- confirm the value survived.
    assert all(e["defectCount"] > 0 for e in body["events"] if e["kind"] == "quality")
    assert all(e["machineName"] for e in body["events"])
    assert body["inventory"]["partsBelowReorder"] > 0


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
            print(f"ok  {name}")

"""Append-only expansion of the generated dataset.

seed.py is run once and its output committed (CLAUDE.md). This script does not
replace it: it reads what seed.py produced and adds to it, so every row that
already existed keeps its id, its timestamps and its numbers.

    python data/seed_append.py          # show what would change
    python data/seed_append.py --write  # apply

What it adds, to reach the round numbers a demo is easier to present with:

    16 earlier days   -> 30 days of history, ending on the SAME last day
    3 machines        -> 15 machines across 5 lines (FINISHING, PACKAGING added)
    7 parts           -> 20 inventory lines

The window is extended BACKWARDS on purpose. Appending days after 2026-08-09
would move "latest", and with it the briefing that opens on load - a demo
rehearsed against a known day would suddenly be showing numbers nobody has
seen. Extending earlier gives the date picker somewhere to go while leaving the
opening screen exactly as it was.

One thing does change: the three new machines run across the whole window, so
PLANT-level roll-ups on existing days shift. That is what adding machines to a
plant means - per-machine figures, event ids and the three planted narratives
in seed.py are all untouched.

Re-running is safe. Rows are keyed by id and days already present are skipped.
"""

from __future__ import annotations

import json
import random
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import seed  # noqa: E402  - the profiles and taxonomies live there, not here

OUT = Path(__file__).resolve().parent / "generated"

# Separate stream from seed.py's RNG(42): the appended rows must not depend on
# how many times the original generator happened to draw.
RNG = random.Random(1015)

EXTRA_DAYS = 16  # 14 existing + 16 = 30

# Two new lines, three new machines. Finishing and packaging are the obvious
# gap in a plant that molds, machines and assembles but never paints or boxes.
NEW_MACHINES = [
    ("M-41", "Powder Coating Booth, Automatic", "Powder Coating", "FINISHING", "CELL-1"),
    ("M-42", "Aqueous Parts Washer, 3-Stage", "Parts Washing", "FINISHING", "CELL-2"),
    ("M-51", "Automatic Case Packer", "Packaging", "PACKAGING", "CELL-1"),
]

# The profiles for these process types live in seed.TYPE_PROFILE, alongside
# every other one. Keeping a second copy here is how the tests, the SOPs and
# the seeded defects quietly stop agreeing with each other.
NEW_PROFILES = {
    process: seed.TYPE_PROFILE[process]
    for process in ("Powder Coating", "Parts Washing", "Packaging")
}

NEW_NOTES = {
    ("Powder Coating", "CHANGEOVER"): [
        "Colour change, booth blown down and reclaim swapped",
        "Hook spacing reset for the larger bracket",
        "Powder change to RAL 7016, hopper purged",
    ],
    ("Powder Coating", "MATERIAL_STARVE"): [
        "Powder hopper empty, no tote staged",
        "Waiting on hangers back from stripping",
    ],
    ("Powder Coating", "PM"): [
        "Weekly PM, filters replaced and booth cleaned",
        "Cure oven thermocouple checked against reference",
    ],
    ("Powder Coating", "SENSOR_FAULT"): [
        "Oven zone thermocouple drifting, recalibrated",
        "Part-present eye blinded by overspray, cleaned",
    ],
    ("Powder Coating", "JAM"): [
        "Part dropped off the hook into the booth",
        "Conveyor chain snagged at the oven entry",
    ],
    ("Parts Washing", "PM"): [
        "Weekly PM, spray nozzles descaled",
        "Bath concentration checked and topped up",
    ],
    ("Parts Washing", "MATERIAL_STARVE"): [
        "Detergent concentrate ran out mid-batch",
        "No baskets returned from the machining cell",
    ],
    ("Parts Washing", "SENSOR_FAULT"): [
        "Bath temperature probe reading low, reseated",
        "Level float stuck, cleaned and tested",
    ],
    ("Parts Washing", "JAM"): [
        "Basket tipped in the transfer, parts recovered",
    ],
    ("Parts Washing", "CHANGEOVER"): [
        "Basket fixture changed for the smaller housing",
    ],
    ("Packaging", "JAM"): [
        "Carton jammed at the erector, cleared",
        "Label web snapped, re-threaded",
    ],
    ("Packaging", "MATERIAL_STARVE"): [
        "Carton blanks ran out, waiting on line side",
        "Label roll empty, no spare at the machine",
    ],
    ("Packaging", "CHANGEOVER"): [
        "Case size change, guides and program reset",
    ],
    ("Packaging", "PM"): [
        "Weekly PM, vacuum cups replaced",
    ],
    ("Packaging", "ROBOT_FAULT"): [
        "Palletiser gripper lost vacuum, re-homed",
    ],
}

NEW_INVENTORY = [
    ("RM-4001", "Polyester powder coat, RAL 7016 grey, 20kg box", "FINISHING", "BOX", 46, 30, 6),
    ("CN-4002", "Alkaline degreaser concentrate", "FINISHING", "L", 88, 60, 9),
    ("CN-4003", "Iron phosphate pretreatment", "FINISHING", "L", 51, 55, 7),
    ("HW-4004", "Coating hooks, zinc, 300mm", "FINISHING", "EA", 940, 500, 60),
    ("PK-5001", "Corrugated carton, 400x300x200", "PACKAGING", "EA", 2100, 1500, 260),
    ("PK-5002", "Pallet, heat-treated, 1200x1000", "PACKAGING", "EA", 74, 90, 12),
    ("PK-5003", "Product label roll, 100x75mm", "PACKAGING", "ROLL", 31, 20, 4),
]


def _load(name: str) -> list[dict]:
    return json.loads((OUT / f"{name}.json").read_text(encoding="utf-8"))


def _note(process: str, reason: str) -> str:
    pool = NEW_NOTES.get((process, reason)) or seed.NOTES.get((process, reason))
    if pool:
        return RNG.choice(pool)
    return f"{reason.replace('_', ' ').title()} cleared"


def _downtime(machine: dict, shift_start: datetime, counter: list[int]) -> list[dict]:
    """Ordinary downtime. None of seed.py's three planted narratives are
    reproduced here - those belong to the original window and repeating them
    would blunt the root-cause demo."""
    process = machine["machine_type"]
    profile = NEW_PROFILES.get(process) or seed.TYPE_PROFILE[process]
    events: list[dict] = []

    count = 0 if RNG.random() < 0.55 else (1 if RNG.random() < 0.85 else 2)
    offset = RNG.randint(20, 120)
    for _ in range(count):
        reason = RNG.choice(profile["reasons"])
        low, high = seed.REASON_DURATION[reason]
        minutes = RNG.randint(low, high)
        if offset + minutes > seed.SHIFT_MINUTES - 20:
            break
        start = shift_start + timedelta(minutes=offset)
        counter[0] += 1
        events.append({
            "event_id": f"DT-{counter[0]:04d}",
            "machine_id": machine["machine_id"],
            "start": start.isoformat(),
            "end": (start + timedelta(minutes=minutes)).isoformat(),
            "reason_code": reason,
            "operator_note": _note(process, reason),
        })
        offset += minutes + RNG.randint(45, 180)
    return events


def _shifts(machines: list[dict], days: list[datetime], runs: list[dict],
            downtime: list[dict], quality: list[dict],
            run_n: list[int], dt_n: list[int], q_n: list[int]) -> None:
    for day in days:
        for machine in machines:
            process = machine["machine_type"]
            profile = NEW_PROFILES.get(process) or seed.TYPE_PROFILE[process]
            for _, hour in seed.SHIFT_START_HOUR.items():
                shift_start = day.replace(hour=hour)
                shift_end = shift_start + timedelta(minutes=seed.SHIFT_MINUTES)

                events = _downtime(machine, shift_start, dt_n)
                downtime.extend(events)
                stopped = sum(
                    (datetime.fromisoformat(e["end"]) - datetime.fromisoformat(e["start"])).total_seconds() / 60
                    for e in events
                )

                run_minutes = max(seed.SHIFT_MINUTES - stopped, 60)
                cycle = machine["ideal_cycle_time"] * RNG.gauss(1.22, 0.06)
                total = int(run_minutes * 60 / cycle)
                rate = RNG.uniform(0.02, 0.05) if RNG.random() < 0.16 else 0.0
                defects = int(total * rate)

                run_n[0] += 1
                runs.append({
                    "run_id": f"RUN-{run_n[0]:04d}",
                    "machine_id": machine["machine_id"],
                    "start": shift_start.isoformat(),
                    "end": shift_end.isoformat(),
                    "good_count": total - defects,
                    "total_count": total,
                })

                # Same invariant as seed.py: quality events sum exactly to the
                # shortfall, so root cause can correlate the two tables without
                # the numbers contradicting each other.
                remaining = defects
                while remaining > 0:
                    take = remaining if remaining <= 25 else RNG.randint(12, remaining - 1)
                    q_n[0] += 1
                    quality.append({
                        "event_id": f"QC-{q_n[0]:04d}",
                        "machine_id": machine["machine_id"],
                        "defect_type": RNG.choice(profile["defects"]),
                        "count": take,
                        "timestamp": (shift_start + timedelta(minutes=RNG.randint(60, 460))).isoformat(),
                    })
                    remaining -= take
                assert shift_end > shift_start


def build() -> dict[str, list[dict]]:
    machines = _load("machines")
    runs = _load("production_runs")
    downtime = _load("downtime_events")
    quality = _load("quality_events")
    inventory = _load("inventory")

    known_ids = {m["machine_id"] for m in machines}
    existing_days = sorted({r["start"][:10] for r in runs})
    first_existing = datetime.fromisoformat(existing_days[0])
    last_existing = datetime.fromisoformat(existing_days[-1])

    def next_n(rows: list[dict], key: str, prefix: str) -> list[int]:
        used = [int(r[key].split("-")[-1]) for r in rows if r[key].startswith(prefix)]
        return [max(used) if used else 0]

    run_n = next_n(runs, "run_id", "RUN-")
    dt_n = next_n(downtime, "event_id", "DT-")
    q_n = next_n(quality, "event_id", "QC-")

    # 1. New machines, appended to the roster.
    added_machines: list[dict] = []
    for machine_id, name, process, line, cell in NEW_MACHINES:
        if machine_id in known_ids:
            continue
        low, high = NEW_PROFILES[process]["cycle"]
        added_machines.append({
            "machine_id": machine_id,
            "name": name,
            "machine_type": process,
            "keywords": NEW_PROFILES[process]["keywords"],
            "line": line,
            "cell": cell,
            "ideal_cycle_time": round(RNG.uniform(low, high), 1),
        })

    # 2. Earlier days for every machine, new and old.
    earlier = [
        first_existing - timedelta(days=n) for n in range(EXTRA_DAYS, 0, -1)
    ]
    _shifts(machines + added_machines, earlier, runs, downtime, quality, run_n, dt_n, q_n)

    # 3. The existing window for the NEW machines only - the old machines
    #    already have those days and must not be touched.
    already = [datetime.fromisoformat(d) for d in existing_days]
    if added_machines:
        _shifts(added_machines, already, runs, downtime, quality, run_n, dt_n, q_n)

    machines = machines + added_machines

    known_parts = {p["part_id"] for p in inventory}
    for part_id, description, line, uom, on_hand, reorder_point, daily_usage in NEW_INVENTORY:
        if part_id in known_parts:
            continue
        inventory.append({
            "part_id": part_id, "description": description, "line": line, "uom": uom,
            "on_hand": on_hand, "reorder_point": reorder_point, "daily_usage": daily_usage,
        })

    # Chronological order keeps the files readable in a diff and in a viewer.
    runs.sort(key=lambda r: (r["start"], r["machine_id"]))
    downtime.sort(key=lambda r: (r["start"], r["machine_id"]))
    quality.sort(key=lambda r: (r["timestamp"], r["machine_id"]))

    print(f"machines          {len(machines):5}  (+{len(added_machines)})")
    print(f"lines             {len({m['line'] for m in machines}):5}")
    print(f"days              {len({r['start'][:10] for r in runs}):5}  "
          f"{min(r['start'][:10] for r in runs)} .. {max(r['start'][:10] for r in runs)}")
    print(f"production_runs   {len(runs):5}")
    print(f"downtime_events   {len(downtime):5}")
    print(f"quality_events    {len(quality):5}")
    print(f"inventory         {len(inventory):5}")
    print(f"\nlast day unchanged: {last_existing.date()} -> "
          f"{max(r['start'][:10] for r in runs)}")

    return {
        "machines": machines,
        "production_runs": runs,
        "downtime_events": downtime,
        "quality_events": quality,
        "inventory": inventory,
    }


if __name__ == "__main__":
    data = build()
    if "--write" not in sys.argv:
        print("\nDry run. Pass --write to apply.")
        raise SystemExit(0)
    for name, rows in data.items():
        (OUT / f"{name}.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
    print("\nwritten to data/generated/")

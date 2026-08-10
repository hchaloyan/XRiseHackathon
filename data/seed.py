"""Generate the synthetic factory dataset. Run ONCE, commit the output.

Volume (spec 6.0): 3 lines x 4 machines = 12 machines, 14 days ending
"yesterday", 2 shifts/day, ~340 production runs, ~120 downtime events,
~90 quality events. Plus an inventory snapshot (CLAUDE.md capability 1
names inventory alongside OEE, scrap and downtime).

Machines carry a human name, a process type and search keywords, so a
supervisor can type "3d printing machine" or "molding press" and land on
the right asset instead of memorising M-33. Reason codes stay canonical --
a real MES has one taxonomy across the plant -- while operator notes and
defect types are specific to the process that produced them.

The three planted patterns (spec 6.1) are the whole point. Uniform random
data gives root-cause analysis nothing to find and the model produces
generic filler:

  1. Recurring CHANGEOVER overrun on one machine, concentrated on shift B.
  2. A quality defect spike beginning right after a specific changeover,
     so cause and effect must be correlated ACROSS two event tables.
  3. Silent cycle-time drift on one machine that depresses OEE without ever
     raising a downtime event.

A fourth, cheaper correlation ties inventory to downtime: the parts sitting
below their reorder point feed the lines that lose time to MATERIAL_STARVE.

Writes machines.json, production_runs.json, downtime_events.json,
quality_events.json and inventory.json into data/generated/.

Dates are frozen at generation time, not computed at read time -- the output
is committed, so the engine treats the newest day present as "today's report"
rather than assuming the demo happens on any particular date.
"""

import json
import random
from datetime import datetime, timedelta
from pathlib import Path

OUT = Path(__file__).resolve().parent / "generated"
RNG = random.Random(42)

DAYS = 14
LAST_DAY = datetime(2026, 8, 9)  # newest full day in the dataset
SHIFT_START_HOUR = {"A": 6, "B": 14}
SHIFT_MINUTES = 480

# Planted patterns (spec 6.1). Named, not magic strings scattered below.
CHANGEOVER_MACHINE = "M-22"  # 1: shift-B changeover overrun (CNC fixture setup)
SPIKE_MACHINE = "M-31"  # 2: defect spike after one specific changeover (weld cell)
SPIKE_DAY = 8  # day index the triggering changeover happens on
DRIFT_MACHINE = "M-13"  # 3: silent cycle-time drift, no downtime events

# machine_id, name, process type, line, cell. IDs are stable: the patterns
# above and the tests both key off them.
MACHINES = [
    ("M-11", "Injection Molding Press 110T", "Injection Molding", "MOLDING", "CELL-1"),
    ("M-12", "Injection Molding Press 220T", "Injection Molding", "MOLDING", "CELL-2"),
    ("M-13", "Injection Molding Press 350T", "Injection Molding", "MOLDING", "CELL-3"),
    ("M-14", "Injection Molding Press 500T", "Injection Molding", "MOLDING", "CELL-4"),
    ("M-21", "CNC Vertical Machining Center 3-Axis", "CNC Machining", "MACHINING", "CELL-1"),
    ("M-22", "CNC Horizontal Machining Center 4-Axis", "CNC Machining", "MACHINING", "CELL-2"),
    ("M-23", "CNC Turning Lathe 8-Inch Chuck", "CNC Machining", "MACHINING", "CELL-3"),
    ("M-24", "CNC Vertical Machining Center 5-Axis", "CNC Machining", "MACHINING", "CELL-4"),
    ("M-31", "Robotic Welding Cell 6-Axis", "Robotic Welding", "ASSEMBLY", "CELL-1"),
    ("M-32", "Automated Assembly and Riveting Station", "Assembly", "ASSEMBLY", "CELL-2"),
    ("M-33", "Industrial 3D Printer FDM Large-Format", "Additive Manufacturing", "ASSEMBLY", "CELL-3"),
    ("M-34", "Industrial 3D Printer SLS Powder-Bed", "Additive Manufacturing", "ASSEMBLY", "CELL-4"),
]

# Per process type: ideal cycle range (seconds/part), search keywords, the
# downtime reasons that can plausibly occur, and the defects it produces.
TYPE_PROFILE = {
    "Injection Molding": {
        "cycle": (28.0, 65.0),
        "keywords": ["injection molding", "molding press", "molder", "imm", "plastics", "tonnage"],
        "reasons": ["CHANGEOVER", "MATERIAL_STARVE", "JAM", "PM", "SENSOR_FAULT"],
        "defects": ["SHORT_SHOT", "FLASH", "SINK_MARK", "WARP", "CONTAMINATION"],
    },
    "CNC Machining": {
        "cycle": (110.0, 380.0),
        "keywords": ["cnc", "machining", "mill", "milling", "lathe", "turning", "metal cutting"],
        "reasons": ["CHANGEOVER", "TOOL_BREAK", "MATERIAL_STARVE", "PM", "SENSOR_FAULT"],
        "defects": ["DIM_OOT", "BURR", "SURFACE_FINISH", "TOOL_MARK"],
    },
    "Robotic Welding": {
        "cycle": (45.0, 90.0),
        "keywords": ["welding", "weld cell", "robot", "robotic", "mig", "fixture"],
        "reasons": ["CHANGEOVER", "ROBOT_FAULT", "MATERIAL_STARVE", "PM", "SENSOR_FAULT"],
        "defects": ["WELD_POROSITY", "UNDERCUT", "SPATTER", "MISALIGNMENT"],
    },
    "Assembly": {
        "cycle": (20.0, 40.0),
        "keywords": ["assembly", "riveting", "fastening", "station", "line side"],
        "reasons": ["CHANGEOVER", "JAM", "MATERIAL_STARVE", "PM", "ROBOT_FAULT"],
        "defects": ["MISSING_FASTENER", "MISALIGNMENT", "SCRATCH"],
    },
    "Additive Manufacturing": {
        "cycle": (900.0, 1500.0),
        "keywords": ["3d printing", "3d printer", "additive", "fdm", "sls", "powder bed",
                     "prototyping", "printer"],
        "reasons": ["BUILD_FAILURE", "MATERIAL_STARVE", "CHANGEOVER", "PM", "SENSOR_FAULT"],
        "defects": ["LAYER_DELAM", "WARP", "DIM_OOT", "POROSITY"],
    },
}

# Canonical reason codes -> duration range in minutes. One taxonomy plant-wide,
# the way an MES actually models it.
REASON_DURATION = {
    "CHANGEOVER": (15, 40),
    "TOOL_BREAK": (20, 75),
    "MATERIAL_STARVE": (10, 45),
    "JAM": (5, 30),
    "PM": (30, 90),
    "SENSOR_FAULT": (8, 35),
    "ROBOT_FAULT": (15, 60),
    "BUILD_FAILURE": (45, 150),
}

# Operator notes are where the process shows through. (process type, reason).
NOTES = {
    ("Injection Molding", "CHANGEOVER"): [
        "Mold swap to part 7742, first-off approved",
        "Tool change to variant B, purge complete",
        "Colour change, screw purged to clear",
    ],
    ("Injection Molding", "MATERIAL_STARVE"): [
        "Waiting on PP resin tote from warehouse",
        "Dryer hopper empty, no resin staged",
        "Masterbatch feeder ran dry",
    ],
    ("Injection Molding", "JAM"): [
        "Part stuck in cavity, ejector adjusted",
        "Sprue hung up in the chute",
        "Robot dropped part into the nest",
    ],
    ("Injection Molding", "PM"): [
        "Scheduled lubrication per SOP-002",
        "Weekly PM, hydraulic filters replaced",
    ],
    ("Injection Molding", "SENSOR_FAULT"): [
        "Cavity pressure transducer reading erratic",
        "Mold-close proximity switch reseated",
    ],
    ("CNC Machining", "CHANGEOVER"): [
        "Fixture change plus tool offsets reset",
        "Job change to part 5518, first article to CMM",
        "Soft jaws bored for the next job",
    ],
    ("CNC Machining", "TOOL_BREAK"): [
        "Carbide insert chipped, replaced from crib stock",
        "Broken tap extracted, hole re-tapped",
        "End mill worn early, swapped and re-offset",
    ],
    ("CNC Machining", "MATERIAL_STARVE"): [
        "Waiting on aluminium bar stock from saw",
        "Billet delivery short, no kanban card",
        "Upstream cell short, no WIP at the door",
    ],
    ("CNC Machining", "PM"): [
        "Weekly PM, way lube and coolant top-up",
        "Spindle warm-up cycle and geometry check",
    ],
    ("CNC Machining", "SENSOR_FAULT"): [
        "Tool-setter probe misreading, recalibrated",
        "Door interlock nuisance trip",
    ],
    ("Robotic Welding", "CHANGEOVER"): [
        "Weld fixture changed for the next assembly",
        "Programme change, torch path re-taught",
        "Fixture swap, clamp positions reset",
    ],
    ("Robotic Welding", "ROBOT_FAULT"): [
        "Torch collision detected, robot re-homed",
        "Wire feeder stalled, liner replaced",
        "Contact tip burned back, tip dressed",
    ],
    ("Robotic Welding", "MATERIAL_STARVE"): [
        "Waiting on stampings from the press shop",
        "Weld wire spool empty, no replacement staged",
    ],
    ("Robotic Welding", "PM"): [
        "Weekly PM, torch consumables replaced",
        "Shielding gas regulator serviced",
    ],
    ("Robotic Welding", "SENSOR_FAULT"): [
        "Seam-tracking sensor lost the joint",
        "Part-present sensor intermittent",
    ],
    ("Assembly", "CHANGEOVER"): [
        "Nest change for the next model",
        "Rivet tooling swapped, force curve re-taught",
    ],
    ("Assembly", "JAM"): [
        "Fastener jammed in the feeder bowl",
        "Conveyor jam cleared, no damage",
    ],
    ("Assembly", "MATERIAL_STARVE"): [
        "Rivet hopper empty, waiting on line side",
        "No sub-assemblies from the weld cell",
    ],
    ("Assembly", "PM"): [
        "Weekly PM, feeder bowl cleaned",
        "Press force calibration verified",
    ],
    ("Assembly", "ROBOT_FAULT"): [
        "Gripper failed to confirm part, re-homed",
        "Pick-and-place axis faulted on overtravel",
    ],
    ("Additive Manufacturing", "BUILD_FAILURE"): [
        "Build aborted, part lifted off the plate",
        "Layer shift detected mid-build, job scrapped",
        "Powder recoater struck a curled edge",
    ],
    ("Additive Manufacturing", "MATERIAL_STARVE"): [
        "Filament spool ran out mid-build",
        "Nylon powder hopper below minimum, build held",
    ],
    ("Additive Manufacturing", "CHANGEOVER"): [
        "Material change, nozzle purged and re-primed",
        "Build plate swapped and re-levelled",
    ],
    ("Additive Manufacturing", "PM"): [
        "Nozzle replaced and chamber filters cleaned",
        "Monthly PM, gantry belts tensioned",
    ],
    ("Additive Manufacturing", "SENSOR_FAULT"): [
        "Chamber thermocouple drifting, recalibrated",
        "Bed-levelling probe inconsistent",
    ],
}

# Consumables and raw material, tied to the line that draws them. daily_usage
# is what the engine turns into days of cover.
# part_id, description, line, uom, on_hand, reorder_point, daily_usage
INVENTORY = [
    ("RM-1001", "Polypropylene resin, natural, 25kg bag", "MOLDING", "BAG", 210, 150, 34),
    ("RM-1002", "ABS resin, black, 25kg bag", "MOLDING", "BAG", 96, 120, 22),
    ("RM-1003", "Colorant masterbatch, grey", "MOLDING", "KG", 340, 100, 11),
    ("CN-1004", "Mold release agent, aerosol", "MOLDING", "CAN", 62, 40, 4),
    ("RM-2001", "Aluminium bar stock 6061, 50mm", "MACHINING", "BAR", 128, 90, 17),
    ("RM-2002", "Steel billet 1045, 75mm", "MACHINING", "BAR", 41, 60, 9),
    ("TL-2003", "Carbide milling insert, CNMG 432", "MACHINING", "EA", 480, 200, 38),
    ("CN-2004", "Coolant concentrate, semi-synthetic", "MACHINING", "L", 155, 80, 6),
    ("RM-3001", "Weld wire ER70S-6, 0.9mm, 15kg spool", "ASSEMBLY", "SPOOL", 34, 45, 7),
    ("CN-3002", "Shielding gas, 75/25 argon-CO2", "ASSEMBLY", "CYL", 18, 12, 2),
    ("HW-3003", "Structural rivet, 6mm steel", "ASSEMBLY", "EA", 12400, 8000, 1450),
    ("RM-3004", "Nylon PA12 powder, additive grade", "ASSEMBLY", "KG", 58, 75, 9),
    ("RM-3005", "ABS filament, 1.75mm, 5kg spool", "ASSEMBLY", "SPOOL", 21, 15, 2),
]

SPIKE_DEFECT = "WELD_POROSITY"  # the weld cell's own failure mode, so it is attributable


def build_machines() -> list[dict]:
    out = []
    for machine_id, name, process, line, cell in MACHINES:
        profile = TYPE_PROFILE[process]
        lo, hi = profile["cycle"]
        out.append({
            "machine_id": machine_id,
            "name": name,
            "machine_type": process,
            # Search terms a supervisor would actually type. The machine name
            # alone does not match "3d printing machine" or "molder".
            "keywords": profile["keywords"],
            "line": line,
            "cell": cell,
            "ideal_cycle_time": round(RNG.uniform(lo, hi), 1),  # seconds per part
        })
    return out


def cycle_factor(machine_id: str, day_index: int) -> float:
    """Actual cycle time as a multiple of ideal. Above 1.0 means running slow."""
    if machine_id == DRIFT_MACHINE:
        # Pattern 3: 1.15x -> 1.55x across the window. Nothing else flags it.
        return 1.15 + 0.40 * (day_index / (DAYS - 1)) + RNG.uniform(-0.02, 0.02)
    return RNG.gauss(1.22, 0.06)


def defect_rate(machine_id: str, day_index: int) -> float:
    """Pattern 2: the spike machine degrades from the triggering changeover on."""
    if machine_id == SPIKE_MACHINE and day_index >= SPIKE_DAY:
        return RNG.uniform(0.055, 0.085)
    return RNG.uniform(0.02, 0.05) if RNG.random() < 0.16 else 0.0


def downtime_for_shift(machine: dict, day_index: int, shift: str, shift_start: datetime,
                       counter: list[int]) -> list[dict]:
    """Zero or more downtime events inside one machine-shift."""
    machine_id = machine["machine_id"]
    process = machine["machine_type"]
    events = []
    planned: list[tuple[str, int]] = []

    if machine_id == CHANGEOVER_MACHINE and shift == "B":
        # Pattern 1: every shift B, and it runs long. Baseline changeover is 15-40.
        planned.append(("CHANGEOVER", RNG.randint(50, 78)))
    if machine_id == SPIKE_MACHINE and day_index == SPIKE_DAY and shift == "A":
        # Pattern 2's trigger. Ordinary-looking event; the defects follow it.
        planned.append(("CHANGEOVER", RNG.randint(22, 34)))

    n_random = (1 if RNG.random() < 0.30 else 0) + (1 if RNG.random() < 0.05 else 0)
    if machine_id == DRIFT_MACHINE:
        n_random = 1 if RNG.random() < 0.10 else 0  # pattern 3 must stay silent
    for _ in range(n_random):
        code = RNG.choice(TYPE_PROFILE[process]["reasons"])
        lo, hi = REASON_DURATION[code]
        planned.append((code, RNG.randint(lo, hi)))

    offset = RNG.randint(5, 45)
    for code, minutes in planned:
        start = shift_start + timedelta(minutes=offset)
        note = RNG.choice(NOTES[(process, code)])
        if code == "CHANGEOVER" and minutes > 45:
            note = "Changeover ran long - fixture alignment reworked twice"
        counter[0] += 1
        events.append({
            "event_id": f"DT-{counter[0]:04d}",
            "machine_id": machine_id,
            "start": start.isoformat(),
            "end": (start + timedelta(minutes=minutes)).isoformat(),
            "reason_code": code,
            "operator_note": note,
        })
        offset += minutes + RNG.randint(30, 120)
        if offset > SHIFT_MINUTES - 20:
            break
    return events


def build() -> dict[str, list[dict]]:
    machines = build_machines()
    runs, downtime, quality = [], [], []
    dt_counter, q_counter = [0], [0]
    day_zero = LAST_DAY - timedelta(days=DAYS - 1)

    for day_index in range(DAYS):
        day = day_zero + timedelta(days=day_index)
        for machine in machines:
            machine_id = machine["machine_id"]
            defects_pool = TYPE_PROFILE[machine["machine_type"]]["defects"]
            for shift, hour in SHIFT_START_HOUR.items():
                shift_start = day.replace(hour=hour)
                shift_end = shift_start + timedelta(minutes=SHIFT_MINUTES)

                events = downtime_for_shift(machine, day_index, shift, shift_start, dt_counter)
                downtime.extend(events)
                stopped = sum(
                    (datetime.fromisoformat(e["end"]) - datetime.fromisoformat(e["start"])).total_seconds() / 60
                    for e in events
                )

                run_minutes = max(SHIFT_MINUTES - stopped, 60)
                cycle = machine["ideal_cycle_time"] * cycle_factor(machine_id, day_index)
                total = int(run_minutes * 60 / cycle)
                defects = int(total * defect_rate(machine_id, day_index))

                runs.append({
                    "run_id": f"RUN-{len(runs) + 1:04d}",
                    "machine_id": machine_id,
                    "start": shift_start.isoformat(),
                    "end": shift_end.isoformat(),
                    "good_count": total - defects,
                    "total_count": total,
                })

                # Quality events reconcile exactly with good_count, so root cause
                # can correlate the two tables without the numbers contradicting.
                remaining = defects
                while remaining > 0:
                    take = remaining if remaining <= 25 else RNG.randint(12, remaining - 1)
                    q_counter[0] += 1
                    quality.append({
                        "event_id": f"QC-{q_counter[0]:04d}",
                        "machine_id": machine_id,
                        "defect_type": (
                            SPIKE_DEFECT if machine_id == SPIKE_MACHINE and day_index >= SPIKE_DAY
                            else RNG.choice(defects_pool)
                        ),
                        "count": take,
                        "timestamp": (shift_start + timedelta(minutes=RNG.randint(60, 460))).isoformat(),
                    })
                    remaining -= take

    inventory = [
        {"part_id": part_id, "description": description, "line": line, "uom": uom,
         "on_hand": on_hand, "reorder_point": reorder_point, "daily_usage": daily_usage}
        for part_id, description, line, uom, on_hand, reorder_point, daily_usage in INVENTORY
    ]

    return {
        "machines": machines,
        "production_runs": runs,
        "downtime_events": downtime,
        "quality_events": quality,
        "inventory": inventory,
    }


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    for name, rows in build().items():
        (OUT / f"{name}.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
        print(f"{name}.json: {len(rows)} rows")

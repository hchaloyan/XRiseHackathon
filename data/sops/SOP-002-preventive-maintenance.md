---
doc_id: SOP-002
title: Preventive Maintenance Schedule and Lubrication
revision: 4.0
department: Maintenance
---

# Purpose and scope

Defines the weekly and monthly PM tasks for all twelve machines across the
MOLDING, MACHINING and ASSEMBLY lines. Downtime booked to PM is planned
downtime and should not appear outside the scheduled window.

Operator notes referencing "scheduled lubrication per SOP-002" point here.

# Weekly PM: Injection Molding (M-11 to M-14)

Performed Monday first shift. Budget 60 minutes per press.

1. Replace hydraulic filters. Record the differential pressure reading before
   removal; a rising trend week over week means the pump is degrading.
2. Check oil level and temperature. Oil above 55 C shortens seal life and
   drives inconsistent fill.
3. Grease tie bars and toggle pins. Dry toggles are a leading cause of
   mold-close proximity switch faults.
4. Inspect and reseat the mold-close proximity switch. Confirm the target gap.
5. Verify press force calibration against the last certified value.
6. Check water manifold for leaks and flow at each circuit.

# Weekly PM: CNC Machining (M-21 to M-24)

1. Way lube reservoir top-up and line check. Starved ways produce chatter,
   which shows up as SURFACE_FINISH rejects.
2. Coolant concentration check with a refractometer, top up with CN-2004 to
   the target ratio. Weak coolant accelerates insert wear and causes BURR.
3. Chip conveyor and coolant tank cleanout.
4. Spindle warm-up cycle followed by a geometry check on the 5-axis (M-24).
5. Tool-setter probe verification against the master gauge.

# Monthly PM: Assembly and Additive (M-31 to M-34)

1. Robotic welding cell M-31: service the shielding gas regulator, verify
   flow rate, inspect the torch liner and contact tip. Gas delivery problems
   are the root of most WELD_POROSITY findings.
2. Assembly station M-32: check rivet feed track alignment and clear debris
   from the hopper throat.
3. 3D printers M-33 and M-34: tension gantry belts, replace the nozzle on the
   FDM unit, clean chamber filters, recalibrate the chamber thermocouple.
4. M-34 powder handling: sieve reclaimed nylon, check recoater blade for nicks.

# Records

Every PM closes with a signed entry naming the technician, the machine, the
tasks completed and any parts consumed. An unsigned PM is treated as not done.

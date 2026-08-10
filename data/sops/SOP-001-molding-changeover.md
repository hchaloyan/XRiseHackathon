---
doc_id: SOP-001
title: Injection Molding Changeover and First-Off Approval
revision: 3.1
department: Molding
---

# Purpose and scope

Covers mold swaps, colour changes and material changes on the MOLDING line
presses M-11 (110T), M-12 (220T), M-13 (350T) and M-14 (500T). Changeover is
the single largest source of planned downtime on this line, so the target
times below are treated as standards, not estimates.

Target: 45 minutes for a mold swap, 20 minutes for a colour change on the
same material. Anything past 1.5x target is logged as CHANGEOVER downtime
with a note explaining the overrun.

# Mold swap procedure

1. Confirm the next job on the schedule and pull the mold from the rack.
   Verify the mold tag matches the part number on the work order.
2. Bring the press to setup mode. Barrel stays at temperature; do not cool
   unless the material is also changing.
3. Retract the ejector, open the platen, disconnect water lines and cap them.
   Uncapped lines are the most common source of a wet floor and a slip hazard.
4. Unclamp, lift with the hoist, and land the outgoing mold on the cart.
5. Mount the incoming mold. Torque clamps in a cross pattern to the value on
   the mold tag. Uneven clamping shows up later as FLASH along the parting line.
6. Reconnect water, restore ejector stroke limits, and re-zero mold protection.
7. Load the stored process for the part number. Never start from the previous
   job's process.

# Colour and material change

1. Empty the hopper and vacuum the throat. Residual pellets from the previous
   run are the usual cause of CONTAMINATION defects in the first hour.
2. Purge the screw with purging compound until the extrudate runs clean.
   Budget 8-15 shots on the 350T and 500T; the larger barrels hold more.
3. On a material change, verify the dryer has run the new resin for the full
   drying time before the first shot. Wet resin produces splay and SINK_MARK.
4. Stage the correct masterbatch (RM-1003 for grey) at the feeder and confirm
   the let-down ratio on the work order.

# First-off approval

No production runs until first-off is approved. Pull five consecutive shots
and check:

- Full fill on all cavities, no SHORT_SHOT
- No FLASH at the parting line or around ejector pins
- Critical dimensions within tolerance, measured not eyeballed
- Cosmetic surfaces free of SINK_MARK and drag marks

Log the approval against the work order. If the first-off fails twice, stop
and escalate to the process engineer rather than adjusting on the fly.

# Common causes of changeover overrun

- Mold not staged at the press before the previous run ended
- Water fittings seized, requiring a search for adapters
- Fixture or clamp positions reset by the prior shift and not documented
- First article sent to CMM without booking the queue slot in advance
